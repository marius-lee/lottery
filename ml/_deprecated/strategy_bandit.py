"""策略级 Multi-Armed Bandit — UCB/Thompson自适应权重调整.

将每种过滤组合视为一个"臂"(arm), 用Bandit算法动态调整权重,
替代静态加权平均。

UCB (Upper Confidence Bound):
  - 每个臂的得分 = 经验均值 + 探索奖励
  - 探索奖励 ∝ sqrt(log(总尝试) / 当前尝试)
  - 自动平衡 exploitation (高均值臂) vs exploration (少尝试臂)

Thompson Sampling:
  - 每个臂维护 Beta(α, β) 后验分布
  - 每步采样 → 选最大采样值的臂
  - α = 命中次数 + 1, β = 未命中次数 + 1
  - 已有 bias_engine.py 的 thompson_sample, 此处用于策略级

用法:
  from ml.strategy_bandit import StrategyBandit, run_strategy_bandit
"""
import math
import random
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class ArmState:
    """单个策略臂的状态."""
    name: str
    pulls: int = 0               # 尝试次数
    red_hits: int = 0            # 累计红球命中数
    blue_hits: int = 0           # 累计蓝球命中数
    ucb_score: float = 0.5       # 当前UCB分数
    ts_alpha: float = 1.0        # Thompson Beta(α, β) α
    ts_beta: float = 1.0         # Thompson Beta(α, β) β
    weight: float = 1.0          # 归一化权重


class StrategyBandit:
    """策略级多臂老虎机.
    
    每个"臂"是一个过滤配置组合。通过历史绩效自适应调整权重。
    """
    
    def __init__(self, arms: List[str], method: str = 'ucb'):
        self.arms: Dict[str, ArmState] = {}
        for name in arms:
            self.arms[name] = ArmState(name=name)
        self.method = method  # 'ucb' or 'thompson'
        self.total_pulls = 0
        
    def select(self, top_k: int = 3) -> List[str]:
        """选择top-k个臂 (根据当前UCB/Thompson分数)."""
        if self.method == 'ucb':
            self._update_ucb()
            ranked = sorted(self.arms.values(), key=lambda a: -a.ucb_score)
        else:  # thompson
            self._thompson_sample()
            ranked = sorted(self.arms.values(), key=lambda a: -a.weight)
        
        return [a.name for a in ranked[:top_k]]
    
    def reward(self, name: str, red_hits: int, blue_hit: int):
        """记录一次出票结果.
        
        Args:
            name: 策略名
            red_hits: 本注红球命中数 (0-6)
            blue_hit: 本注蓝球命中 (0 or 1)
        """
        if name not in self.arms:
            return
        arm = self.arms[name]
        arm.pulls += 1
        arm.red_hits += red_hits
        arm.blue_hits += blue_hit
        self.total_pulls += 1
        
        # 更新Thompson先验
        # 归一化命中率: red/6 ∈ [0,1], blue ∈ {0,1}
        reward = red_hits / 6.0 + blue_hit * 0.3  # 蓝球权重较低
        arm.ts_alpha += reward * 0.5
        arm.ts_beta += (1.0 - reward) * 0.5
    
    def _update_ucb(self):
        """更新所有臂的UCB分数."""
        if self.total_pulls == 0:
            for arm in self.arms.values():
                arm.ucb_score = 0.5
            return
        
        for arm in self.arms.values():
            if arm.pulls == 0:
                arm.ucb_score = float('inf')  # 从未尝试 → 强制探索
                continue
            
            # 经验均值
            avg_hit = arm.red_hits / (arm.pulls * 6.0)  # 每球命中率
            # 探索奖励
            exploration = math.sqrt(2.0 * math.log(self.total_pulls + 1) / arm.pulls)
            # UCB
            arm.ucb_score = avg_hit + exploration
        
        # 归一化
        scores = [a.ucb_score for a in self.arms.values() if not math.isinf(a.ucb_score)]
        if not scores:
            return
        min_s, max_s = min(scores), max(scores)
        rng = max_s - min_s if max_s > min_s else 1.0
        for arm in self.arms.values():
            if not math.isinf(arm.ucb_score):
                arm.ucb_score = (arm.ucb_score - min_s) / rng
    
    def _thompson_sample(self):
        """Thompson抽样: 从后验采样."""
        for arm in self.arms.values():
            # Beta(α, β): 用Gamma方法
            sample = random.betavariate(arm.ts_alpha, arm.ts_beta)
            arm.weight = sample
        
        # 软最大归一化
        total = sum(a.weight for a in self.arms.values())
        if total > 0:
            for arm in self.arms.values():
                arm.weight /= total
    
    def get_weights(self) -> Dict[str, float]:
        """返回当前归一化权重 {strategy_name: weight}."""
        if self.method == 'ucb':
            self._update_ucb()
            scores = {a.name: a.ucb_score for a in self.arms.values()}
        else:
            self._thompson_sample()
            scores = {a.name: a.weight for a in self.arms.values()}
        
        total = sum(v for v in scores.values() if not math.isinf(v))
        if total > 0:
            return {k: round(v / total, 4) for k, v in scores.items() if not math.isinf(v)}
        n = len(scores)
        return {k: round(1.0 / n, 4) for k in scores}
    
    def state(self) -> dict:
        """当前Bandit状态报告."""
        weights = self.get_weights()
        arms_info = []
        for arm in self.arms.values():
            avg_hit = arm.red_hits / (arm.pulls * 6.0) if arm.pulls > 0 else 0.0
            arms_info.append({
                "name": arm.name,
                "pulls": arm.pulls,
                "avg_hit_rate": round(avg_hit, 4),
                "weight": weights.get(arm.name, 0.0),
                "ucb_score": round(arm.ucb_score, 4) if not math.isinf(arm.ucb_score) else "unexplored",
            })
        
        arms_info.sort(key=lambda a: -a["weight"])
        return {
            "method": self.method,
            "total_pulls": self.total_pulls,
            "n_arms": len(self.arms),
            "arms": arms_info,
            "top_arms": [a["name"] for a in arms_info[:5]],
        }


def run_strategy_bandit(widget_bandit: bool = True) -> dict:
    """便捷入口: 初始化策略Bandit, 加载回测数据预热.
    
    过滤组合作为arms:
      - Baseline: 无过滤
      - Color-Block9: 三色+方块9
      - Soft-Filter: 软过滤
      - Full-Filters: 全过滤
      - Greedy-Diversity: 贪心多样性
      - 等...
    """
    from server import db
    data = db.load_draws()
    
    # 定义策略臂 (与A/B实验预设对齐)
    arm_names = [
        "Baseline-Random",
        "Soft-Filter",
        "Color-Block9", 
        "Full-Filters",
        "Greedy-MaxOverlap",
        "Author-Zhang",
        "Author-Peng",
        "Author-JiangJialin",
        "Ensemble",
    ]
    
    bandit = StrategyBandit(arm_names, method='ucb')
    
    # 预热: 加载回测数据
    backtest = db.load_backtest_results()
    for row in backtest:
        name = row.get("strategy", "")
        if name in arm_names:
            avg_hit = row.get("avg_red_hit", 0.0)
            test_count = row.get("test_count", 1)
            # 近似模拟回报
            for _ in range(test_count):
                bandit.reward(name, int(avg_hit), 0)
    
    return {
        "ok": True,
        **bandit.state(),
        "recommendation": f"Top arm: {bandit.state()['top_arms'][0] if bandit.state()['top_arms'] else 'none'}",
    }
