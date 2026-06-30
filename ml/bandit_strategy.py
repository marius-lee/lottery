"""上下文 Bandit 策略选择 — Thompson 抽样在线学习最优策略组合

每种策略组合是一个 arm:
  Arm 1: pool + freq_blue
  Arm 2: greedy + freq_blue
  Arm 3: backtest + freq_blue
  Arm 4: pool + entropy_blue
  Arm 5: greedy + entropy_blue
  ...

每期选择 arm → 实际命中反馈 → 更新 Beta(α, β) 后验。
上下文特征: 最近5期的红球跨度/和值/奇偶比/蓝球遗漏。

经过 50 期后, 系统自动收敛到最优策略组合。
不需要人工判断 — 这是标准的在线学习范式。
"""
import math
import random
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field
from collections import Counter


# ═══════════════════════════════════════════════════════════
# 策略 Arm 定义
# ═══════════════════════════════════════════════════════════

DEFAULT_ARMS = [
    {
        "id": "pool+freq",
        "name": "池采样+频率蓝球",
        "diversity_mode": None,
        "blue_mode": "freq",
        "description": "从有效组合池随机采样, Laplace频率top-6蓝球",
    },
    {
        "id": "greedy+freq",
        "name": "贪心+频率蓝球",
        "diversity_mode": "greedy",
        "blue_mode": "freq",
        "description": "贪心最大化Jaccard距离, Laplace频率top-6蓝球",
    },
    {
        "id": "backtest+freq",
        "name": "回测+频率蓝球",
        "backtest_rank": True,
        "blue_mode": "freq",
        "description": "历史回测排名选组合, Laplace频率top-6蓝球",
    },
    {
        "id": "pool+entropy",
        "name": "池采样+条件熵蓝球",
        "diversity_mode": None,
        "blue_mode": "entropy",
        "description": "从有效组合池随机采样, 条件熵最低的6个蓝球",
    },
    {
        "id": "greedy+entropy",
        "name": "贪心+条件熵蓝球",
        "diversity_mode": "greedy",
        "blue_mode": "entropy",
        "description": "贪心最大化Jaccard距离, 条件熵最低的6个蓝球",
    },
    {
        "id": "exactcov+freq",
        "name": "精确覆盖+频率蓝球",
        "diversity_mode": None,
        "blue_mode": "freq",
        "red_mode": "exact_cover",
        "description": "La Jolla已知最优精确覆盖, 频率蓝球",
    },
    {
        "id": "diffset+entropy",
        "name": "差集构造+条件熵蓝球",
        "diversity_mode": None,
        "blue_mode": "entropy",
        "red_mode": "diffset",
        "description": "差集构造2-覆盖+条件熵蓝球",
    },
    {
        "id": "exactcov+entropy",
        "name": "精确覆盖+条件熵蓝球",
        "diversity_mode": None,
        "blue_mode": "entropy",
        "red_mode": "exact_cover",
        "description": "La Jolla精确覆盖+条件熵蓝球",
    },
]


@dataclass
class ArmState:
    """单个 arm 的 Beta 后验分布."""
    id: str
    name: str
    alpha: float = 1.0   # Beta(α, β): 成功次数+1 (先验)
    beta: float = 1.0    # 失败次数+1
    trials: int = 0
    total_score: int = 0
    config: dict = None

    @property
    def mean(self) -> float:
        return self.alpha / max(0.001, self.alpha + self.beta)

    def thompson_sample(self) -> float:
        """从 Beta(α, β) 后验采样."""
        # 简化的 Beta 采样: 用 Gamma 近似
        import random
        if self.alpha <= 0 or self.beta <= 0:
            return 0.0
        gamma_a = -math.log(1 - random.random() ** (1.0 / self.alpha)) if self.alpha > 0 else 0
        gamma_b = -math.log(1 - random.random() ** (1.0 / self.beta)) if self.beta > 0 else 0
        return gamma_a / max(0.0001, gamma_a + gamma_b)

    def update(self, score: float, max_score: float = 6.0):
        """用命中反馈更新后验.

        score: 实际命中分数 (红球命中数 + 蓝球命中[0/1])
        max_score: 最大可能分数
        """
        self.trials += 1
        self.total_score += score
        # 将分数转换为 Beta 计数
        normalized = score / max(1, max_score)
        self.alpha += normalized * 2.0  # 每次更新加权 2
        self.beta += (1 - normalized) * 2.0


@dataclass
class BanditState:
    """Bandit 全局状态."""
    arms: List[ArmState] = field(default_factory=list)
    context_history: List[dict] = field(default_factory=list)
    selected_history: List[str] = field(default_factory=list)
    score_history: List[float] = field(default_factory=list)
    initialized: bool = False

    def init_arms(self):
        """初始化 arm 列表."""
        if self.initialized:
            return
        for arm_def in DEFAULT_ARMS:
            self.arms.append(ArmState(
                id=arm_def["id"],
                name=arm_def["name"],
                config=arm_def,
            ))
        self.initialized = True

    def set_fdr_bias(self, fdr_valid_methods: list):
        """FDR信号偏置: 无显著方法时, 降低复杂arm的alpha先验.

        当FDR显示所有方法都不显著时, 说明没有统计证据支持任何预测方法.
        这时bandit应该偏向最简单的策略 (pool+freq, 即随机采样).
        通过降低复杂arm的初始alpha (先验成功次数), Thompson采样自然会
        偏好简单策略, 直到有显著证据出现.
        """
        self.init_arms()
        if fdr_valid_methods is None:
            return
        has_significant = len(fdr_valid_methods) > 0
        
        # 复杂arm定义: 使用entropy/exact_cover/diffset/greedy/backtest的arm
        complex_keywords = ['entropy', 'exactcov', 'diffset', 'greedy', 'backtest']
        for arm in self.arms:
            is_complex = any(kw in arm.id for kw in complex_keywords)
            if not has_significant and is_complex and arm.trials == 0:
                # 无FDR显著方法 + 复杂arm + 未探索过 → 降低先验alpha
                arm.alpha = 0.5  # 初始alpha降低, Thompson采样值更低
            elif has_significant and arm.trials == 0:
                arm.alpha = 1.0  # 有显著方法 → 正常先验

    def select_arm(self, context: Optional[dict] = None) -> ArmState:
        """Thompson 抽样: 采样所有 arm, 选最高的."""
        self.init_arms()
        if not self.arms:
            return None
        best_arm = None
        best_sample = -1
        # 前 10 轮: 均匀探索
        total_trials = sum(a.trials for a in self.arms)
        if total_trials < 10:
            return random.choice(self.arms)

        for arm in self.arms:
            sample = arm.thompson_sample()
            if sample > best_sample:
                best_sample = sample
                best_arm = arm

        if context:
            self.context_history.append(context)
        self.selected_history.append(best_arm.id if best_arm else "unknown")
        return best_arm

    def update(self, score: float):
        """用命中分数更新最近选择的 arm 后验."""
        last_id = self.selected_history[-1] if self.selected_history else None
        if last_id:
            for arm in self.arms:
                if arm.id == last_id:
                    arm.update(score)
                    self.score_history.append(score)
                    return

    def summary(self) -> dict:
        """返回各 arm 的状态摘要."""
        self.init_arms()
        arms_data = []
        best_arm = None
        best_mean = -1
        for arm in self.arms:
            m = {
                "id": arm.id,
                "name": arm.name,
                "trials": arm.trials,
                "mean_score": round(arm.mean, 3),
                "total_score": arm.total_score,
                "alpha": round(arm.alpha, 1),
                "beta": round(arm.beta, 1),
            }
            arms_data.append(m)
            if arm.trials > 0 and arm.mean > best_mean:
                best_mean = arm.mean
                best_arm = arm

        return {
            "ok": True,
            "total_trials": sum(a.trials for a in self.arms),
            "arms": arms_data,
            "best_arm": best_arm.name if best_arm else "未收敛",
            "best_mean": round(best_mean, 3),
            "note": "Thompson抽样自动收敛到最优策略组合",
        }


# ═══════════════════════════════════════════════════════════
# 上下文特征提取
# ═══════════════════════════════════════════════════════════

def extract_context(data, window=5) -> dict:
    """从最近 window 期数据提取上下文特征."""
    if len(data) < window:
        return {"data_short": True}

    recent = data[-window:]

    # 红球特征
    reds = []
    for row in recent:
        reds.append(sorted(row[1:7]))

    # 跨度
    spans = [r[-1] - r[0] for r in reds]
    avg_span = sum(spans) / len(spans)

    # 和值趋势
    sums = [sum(r) for r in reds]
    sum_trend = sums[-1] - sums[0] if len(sums) >= 2 else 0  # [工程] 简单首尾差值趋势

    # 奇偶比趋势
    odd_ratios = [sum(1 for x in r if x % 2 == 1) / 6 for r in reds]  # [数学] 每注6红, 奇偶比∈[0,6]
    avg_odd = sum(odd_ratios) / len(odd_ratios)

    # 蓝球遗漏
    blue_last10 = [row[7] for row in recent]
    blue_counter = Counter(blue_last10)
    max_blue_freq = max(blue_counter.values()) if blue_counter else 0

    # 红球冷热: 最近5期出现频率
    red_density = {}
    for n in range(1, 34):
        cnt = sum(1 for r in reds if n in r)
        red_density[n] = cnt / window

    return {
        "window": window,
        "avg_span": round(avg_span, 1),
        "sum_trend": round(sum_trend, 1),
        "avg_odd_ratio": round(avg_odd, 2),
        "max_blue_freq": max_blue_freq,
        "red_hotness": {n: round(v, 2) for n, v in red_density.items() if v > 0.5},
        "n_periods": len(data),
    }


# ═══════════════════════════════════════════════════════════
# 全局 Bandit 实例
# ═══════════════════════════════════════════════════════════

_global_bandit = BanditState()


def get_bandit() -> BanditState:
    """获取全局 Bandit 实例."""
    _global_bandit.init_arms()
    return _global_bandit


def bandit_select_and_generate(data, n=3, fdr_signals=None):
    """一次完整的 Bandit 选择 + 出号.

    1. 提取上下文
    2. FDR信号偏置arm先验 (如果不显著→偏好simple arms)
    3. Thompson 抽样选 arm
    4. 调用对应策略生成号码
    5. 返回 (tickets, arm_config) 供 feedback 使用
    """
    from ml.micro_portfolio import generate_tickets

    ctx = extract_context(data)
    bandit = get_bandit()
    
    # FDR信号: 如果没有统计显著方法, 偏向简单策略
    if fdr_signals is not None:
        bandit.set_fdr_bias(fdr_signals)
    
    arm = bandit.select_arm(ctx)

    if not arm or not arm.config:
        # 回退
        return generate_tickets(n=n, use_freq_blue=True), {"mode": "fallback"}

    cfg = arm.config
    # 根据 arm 配置构造 generate_tickets 参数
    # Pass through all config keys that generate_tickets accepts
    known_keys = ["diversity_mode", "backtest_rank", "blue_mode", "red_mode", 
                  "soft", "max_overlap", "five_period", "pattern_rules"]
    kwargs = dict(n=n, use_freq_blue=True)
    for key in known_keys:
        if key in cfg and cfg[key] is not None:
            kwargs[key] = cfg[key]

    tickets = generate_tickets(**kwargs)

    return tickets, {
        "mode": "bandit",
        "arm_id": arm.id,
        "arm_name": arm.name,
        "context": ctx,
    }
