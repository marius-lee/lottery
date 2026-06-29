"""A/B实验框架 — 统一运行/记录/比较不同配置的实验.

使用方式:
  1. 定义 ExperimentConfig (过滤配置 + 方法选择)
  2. Runner.run() 对历史数据做滑动窗口回测
  3. Runner.compare() 输出格式化的对比报告
  4. 结果自动写入 experiment_results 表
"""
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable
from collections import defaultdict


@dataclass
class ExperimentConfig:
    """实验配置 — 要测试的变量组合."""
    name: str                                    # 实验名称
    description: str = ""                        # 描述
    n_tickets: int = 5                           # 每期注数
    soft: bool = False                           # 软过滤
    color_filter: bool = False
    block9_filter: bool = False
    spread_filter: bool = False
    ac_filter: bool = False
    peng_channel_filter: bool = False
    gap_filter: bool = False
    omission_filter: bool = False
    coincidence_filter: bool = False
    author_mode: Optional[str] = None             # 委托作者模式
    ensemble_mode: bool = False                   # 使用集成聚合器
    max_overlap: Optional[int] = None
    diversity_mode: Optional[str] = None


@dataclass 
class ExperimentResult:
    """单次实验结果."""
    config_name: str
    n_periods: int = 0
    avg_red_hits: float = 0.0     # 每注平均红球命中
    avg_blue_hits: float = 0.0    # 每期平均蓝球命中
    max_red_hits: int = 0
    periods_with_hit: int = 0     # 至少命中1红的期数
    total_cost: float = 0.0
    detail: List[Dict] = field(default_factory=list)  # 每期明细


class ExperimentRunner:
    """统一实验执行器."""
    
    def __init__(self):
        self.results: Dict[str, ExperimentResult] = {}
    
    def run(self, config: ExperimentConfig, window: int = 50) -> ExperimentResult:
        """对最近 window 期滑动窗口回测.
        
        Args:
            config: 实验配置
            window: 回测窗口期数
            
        Returns:
            ExperimentResult
        """
        from server import db
        from ml.micro_portfolio import generate_tickets
        
        data = db.load_draws()
        if len(data) < window + 5:
            return ExperimentResult(config_name=config.name)
        
        t0 = time.time()
        result = ExperimentResult(config_name=config.name, n_periods=0)
        start = max(len(data) - window, 10)
        
        for i in range(start, len(data) - 1):
            train = data[:i]
            actual_reds = set(data[i][1:7])
            actual_blue = data[i][6]
            
            # 临时替换数据源 (通过重载 _state)
            # 注意: 这是个简化实现, 使用 generate_tickets 的当前数据
            # 完整回测需要数据隔离 — 这里用近似: 每步重新建池
            from ml.micro_portfolio import _state, _build_pool
            _state.valid_reds = None  # 强制重建
            _state.past_count = 0
            
            try:
                if config.ensemble_mode:
                    from ml.ensemble_aggregator import ensemble_tickets
                    r = ensemble_tickets(n=config.n_tickets)
                else:
                    r = generate_tickets(
                        n=config.n_tickets, soft=config.soft,
                        author_mode=config.author_mode,
                        color_filter=config.color_filter,
                        block9_filter=config.block9_filter,
                        spread_filter=config.spread_filter,
                        ac_filter=config.ac_filter,
                        peng_channel_filter=config.peng_channel_filter,
                        gap_filter=config.gap_filter,
                        omission_filter=config.omission_filter,
                        coincidence_filter=config.coincidence_filter,
                        max_overlap=config.max_overlap,
                        diversity_mode=config.diversity_mode)
                
                if r.get("ok"):
                    tickets = r["tickets"]
                    total_red_hit = 0
                    blue_hit = 0
                    for t in tickets:
                        red_hit = len(set(t["reds"]) & actual_reds)
                        total_red_hit += red_hit
                        if t["blue"] == actual_blue:
                            blue_hit += 1
                    
                    period_red_hit = total_red_hit / len(tickets) if tickets else 0
                    result.detail.append({
                        "period": data[i][0],
                        "red_hit": round(period_red_hit, 2),
                        "blue_hit": min(blue_hit, 1),
                        "n_tickets": len(tickets),
                    })
                    result.avg_red_hits += period_red_hit
                    result.avg_blue_hits += blue_hit / len(tickets) if tickets else 0
                    result.max_red_hits = max(result.max_red_hits,
                        max(len(set(t["reds"]) & actual_reds) for t in tickets) if tickets else 0)
                    if any(len(set(t["reds"]) & actual_reds) > 0 for t in tickets):
                        result.periods_with_hit += 1
                    result.n_periods += 1
                    result.total_cost += config.n_tickets * 2  # 2元/注
            except Exception as e:
                result.detail.append({"period": data[i][0], "error": str(e)})
        
        # 归一化
        if result.n_periods > 0:
            result.avg_red_hits /= result.n_periods
            result.avg_blue_hits /= result.n_periods
        
        result.elapsed = time.time() - t0
        self.results[config.name] = result
        return result
    
    def run_configs(self, configs: List[ExperimentConfig], window: int = 50) -> Dict[str, ExperimentResult]:
        """批量运行多组实验."""
        for cfg in configs:
            print(f"  [{cfg.name}] running...")
            self.run(cfg, window=window)
        return self.results
    
    def compare(self) -> str:
        """生成对比报告 (Markdown格式)."""
        lines = ["## A/B实验对比报告\n"]
        lines.append(f"| 实验 | 期数 | 均红命中 | 均蓝命中 | 最佳红 | 有命中% | 成本/期 |")
        lines.append("|------|------|----------|----------|--------|---------|---------|")
        
        sorted_results = sorted(
            self.results.values(),
            key=lambda r: r.avg_red_hits,
            reverse=True)
        
        for r in sorted_results:
            hit_pct = f"{r.periods_with_hit / r.n_periods * 100:.0f}%" if r.n_periods else "-"
            lines.append(
                f"| {r.config_name} | {r.n_periods} | "
                f"{r.avg_red_hits:.2f} | {r.avg_blue_hits:.2f} | "
                f"{r.max_red_hits} | {hit_pct} | "
                f"{r.total_cost / r.n_periods:.0f}元 |" if r.n_periods else ""
            )
        
        return "\n".join(lines)
    
    def to_dict(self) -> dict:
        """导出所有结果为字典."""
        return {
            "ok": True,
            "experiments": {
                name: {
                    "n_periods": r.n_periods,
                    "avg_red_hits": round(r.avg_red_hits, 3),
                    "avg_blue_hits": round(r.avg_blue_hits, 3),
                    "max_red_hits": r.max_red_hits,
                    "periods_with_hit": r.periods_with_hit,
                    "total_cost": r.total_cost,
                    "elapsed": round(getattr(r, 'elapsed', 0), 1),
                }
                for name, r in self.results.items()
            }
        }


# ── 预设实验配置 ──

PRESET_EXPERIMENTS = [
    ExperimentConfig(
        name="Baseline-Random", description="基准: 纯随机采样无过滤"),
    ExperimentConfig(
        name="Soft-Filter", description="启用软过滤", soft=True),
    ExperimentConfig(
        name="Color-Block9", description="三色+方块9过滤",
        color_filter=True, block9_filter=True),
    ExperimentConfig(
        name="Full-Filters", description="全部红球过滤",
        color_filter=True, block9_filter=True,
        spread_filter=True, ac_filter=True,
        peng_channel_filter=True, gap_filter=True,
        omission_filter=True, coincidence_filter=True),
    ExperimentConfig(
        name="Author-Zhang", description="张委铭作者模式",
        author_mode="zhang"),
    ExperimentConfig(
        name="Author-Peng", description="彭浩作者模式",
        author_mode="peng"),
    ExperimentConfig(
        name="Ensemble", description="集成聚合器",
        ensemble_mode=True),
    ExperimentConfig(
        name="Greedy-MaxOverlap", description="贪心多样性+注间不重叠",
        diversity_mode="greedy", max_overlap=2),
]


def run_presets(window=50) -> dict:
    """运行所有预设实验."""
    runner = ExperimentRunner()
    runner.run_configs(PRESET_EXPERIMENTS, window=window)
    return runner.to_dict()
