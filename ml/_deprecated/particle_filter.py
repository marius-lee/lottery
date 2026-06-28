"""粒子滤波器 — 追踪红球号码冷→热/热→冷状态的贝叶斯推断.

Sequential Monte Carlo (SMC) with Bootstrap Particle Filter (Gordon+1993):
  - 每个号码维护 N 个粒子, 代表"潜在真实出现概率"的分布
  - 状态方程: p_t = p_{t-1} + ε_t  (随机游走, ε ~ N(0, σ²))
  - 观测方程: y_t ~ Bernoulli(p_t)  (每期出现/未出现)
  - 重采样: 系统重采样 (Systematic Resampling), 避免粒子退化

vs CUSUM:
  - CUSUM 检测均值漂移何时发生 (突变点检测)
  - 粒子滤波 估计当前状态值 (连续追踪)
  - 两者互补: CUSUM 告警 → 粒子滤波确认当前状态

用法:
  from ml.particle_filter import ParticleFilter, run_particle_filter
  pf = ParticleFilter(N=1000, sigma=0.02)
  pf.update(observations)  # 逐期更新
  hotness = pf.posterior_mean()  # {num: posterior_prob}
"""
import math
import random
from typing import List, Dict, Optional, Tuple
from collections import defaultdict


class ParticleFilter:
    """号码出现概率的粒子滤波追踪器.
    
    Args:
        N: 粒子数 (默认1000, 平衡精度和速度)
        sigma: 状态噪声标准差 (默认0.02, 约2%的期际概率变化)
        prior_mean: 先验均值 (默认 1/33 ≈ 0.0303)
        prior_std: 先验标准差 (默认 0.01)
    """
    
    def __init__(self, N: int = 1000, sigma: float = 0.02,
                 prior_mean: float = 1.0/33, prior_std: float = 0.01):
        self.N = N
        self.sigma = sigma
        self.prior_mean = prior_mean
        self.prior_std = prior_std
        self.particles: Dict[int, List[float]] = {}  # {num: [N floats]}
        self.ess_history: Dict[int, List[float]] = defaultdict(list)  # Effective Sample Size
        self.mean_history: Dict[int, List[float]] = defaultdict(list)
        
    def _init_particles(self, num: int):
        """初始化一个号码的粒子集: N(prior_mean, prior_std)."""
        # 截断到 [0.001, 0.3]
        particles = []
        for _ in range(self.N):
            p = random.gauss(self.prior_mean, self.prior_std)
            p = max(0.001, min(p, 0.3))
            particles.append(p)
        self.particles[num] = particles
    
    def _propagate(self, particles: List[float]) -> List[float]:
        """状态传播: p_t = p_{t-1} + ε, ε ~ N(0, σ²)."""
        new_particles = []
        for p in particles:
            p_new = p + random.gauss(0, self.sigma)
            p_new = max(0.001, min(p_new, 0.3))
            new_particles.append(p_new)
        return new_particles
    
    def _compute_weights(self, particles: List[float], observed: bool) -> List[float]:
        """重要性权重: w_i = P(y | p_i) = p_i if y=1 else (1-p_i)."""
        weights = []
        for p in particles:
            w = p if observed else (1.0 - p)
            weights.append(w)
        # 归一化
        total = sum(weights)
        if total > 0:
            weights = [w / total for w in weights]
        else:
            weights = [1.0 / len(weights)] * len(weights)
        return weights
    
    def _effective_sample_size(self, weights: List[float]) -> float:
        """有效样本量 ESS = 1 / Σ w_i²."""
        sum_sq = sum(w * w for w in weights)
        return 1.0 / sum_sq if sum_sq > 0 else 0.0
    
    def _systematic_resample(self, particles: List[float], weights: List[float]) -> List[float]:
        """系统重采样 (Systematic Resampling) — 计算高效, 方差低."""
        N = len(particles)
        new_particles = []
        # 累积权重
        cumsum = []
        s = 0.0
        for w in weights:
            s += w
            cumsum.append(s)
        
        # 系统抽样
        u0 = random.random() / N
        j = 0
        for i in range(N):
            u = u0 + i / N
            while j < N and cumsum[j] < u:
                j += 1
            if j >= N:
                j = N - 1
            new_particles.append(particles[j])
        
        return new_particles
    
    def update(self, observations: Dict[int, bool]):
        """用一期观测更新所有号码的粒子.
        
        Args:
            observations: {num: True if appeared, False otherwise}
        """
        for num in range(1, 34):
            if num not in self.particles:
                self._init_particles(num)
            
            particles = self.particles[num]
            observed = observations.get(num, False)
            
            # 1. 传播
            particles = self._propagate(particles)
            
            # 2. 加权
            weights = self._compute_weights(particles, observed)
            
            # 3. ESS检查
            ess = self._effective_sample_size(weights)
            self.ess_history[num].append(ess)
            
            # 4. 重采样 (当ESS < N/2时触发, 防止退化)
            if ess < self.N * 0.5:
                particles = self._systematic_resample(particles, weights)
            
            self.particles[num] = particles
            
            # 记录后验均值
            mean = sum(particles) / len(particles)
            self.mean_history[num].append(mean)
    
    def update_batch(self, data: List[List[int]], window: Optional[int] = None):
        """批量更新历史数据.
        
        Args:
            data: 来自 db.load_draws() 的原始数据
            window: 只处理最近window期 (None=全部)
        """
        subset = data[-window:] if window else data
        for row in subset:
            reds = set(row[1:7])
            obs = {n: (n in reds) for n in range(1, 34)}
            self.update(obs)
    
    def posterior_mean(self) -> Dict[int, float]:
        """返回每个号码的后验出现概率均值."""
        return {
            n: sum(self.particles.get(n, [self.prior_mean])) / max(len(self.particles.get(n, [self.prior_mean])), 1)
            for n in range(1, 34)
        }
    
    def posterior_std(self) -> Dict[int, float]:
        """返回每个号码的后验标准差."""
        result = {}
        for n in range(1, 34):
            pts = self.particles.get(n, [self.prior_mean])
            if len(pts) < 2:
                result[n] = self.prior_std
            else:
                mean = sum(pts) / len(pts)
                var = sum((p - mean) ** 2 for p in pts) / (len(pts) - 1)
                result[n] = math.sqrt(var)
        return result
    
    def hotness_scores(self) -> List[float]:
        """归一化热号评分 [0,1] × 33.
        
        热号 = 后验均值 > 先验均值, 且后验标准差小 (高置信).
        """
        means = self.posterior_mean()
        stds = self.posterior_std()
        scores = []
        for n in range(1, 34):
            # Z-score: 与先验的差异, 除以不确定性
            m = means.get(n, self.prior_mean)
            s = stds.get(n, self.prior_std)
            z = (m - self.prior_mean) / max(s, 0.001)
            # 截断到合理范围
            z_clipped = max(-3.0, min(z, 3.0))
            # sigmoid 映射到 [0,1]
            score = 1.0 / (1.0 + math.exp(-z_clipped))
            scores.append(score)
        return scores
    
    def state_classification(self) -> Dict[int, str]:
        """将每个号码分类为热/温/冷状态.
        
        热号 (Hot): 后验均值 > prior_mean + 1σ
        温号 (Warm): prior_mean - 1σ ≤ 后验均值 ≤ prior_mean + 1σ
        冷号 (Cold): 后验均值 < prior_mean - 1σ
        """
        means = self.posterior_mean()
        stds = self.posterior_std()
        classes = {}
        for n in range(1, 34):
            m = means.get(n, self.prior_mean)
            s = stds.get(n, self.prior_std)
            upper = self.prior_mean + s
            lower = self.prior_mean - s
            if m > upper:
                classes[n] = "Hot"
            elif m < lower:
                classes[n] = "Cold"
            else:
                classes[n] = "Warm"
        return classes


def run_particle_filter(window: int = 200) -> dict:
    """便捷入口: 运行粒子滤波并返回热号评分 + 状态分类.
    
    Returns:
        dict with hotness_scores, state_classification, posterior_means, ess_stats
    """
    from server.db import load_draws
    data = load_draws()
    
    pf = ParticleFilter(N=1000, sigma=0.02)
    pf.update_batch(data, window=window)
    
    scores = pf.hotness_scores()
    classes = pf.state_classification()
    means = pf.posterior_mean()
    
    # 有效样本量统计
    ess_stats = {}
    for n in range(1, 34):
        ess_list = pf.ess_history.get(n, [])
        ess_stats[n] = round(sum(ess_list) / len(ess_list), 1) if ess_list else 0.0
    
    # 按评分排序
    ranked = sorted(
        [(n, round(scores[n-1], 4), classes[n], round(means[n], 4))
         for n in range(1, 34)],
        key=lambda x: -x[1]
    )
    
    return {
        "ok": True,
        "window": window,
        "n_particles": pf.N,
        "sigma": pf.sigma,
        "hot_numbers": [{"num": n, "score": s, "state": c, "posterior_mean": m}
                       for n, s, c, m in ranked if c == "Hot"],
        "cold_numbers": [{"num": n, "score": s, "state": c, "posterior_mean": m}
                        for n, s, c, m in ranked if c == "Cold"],
        "all_scores": [{"num": n, "score": s, "state": c} for n, s, c, _ in ranked],
        "ess_avg": round(sum(ess_stats.values()) / max(len(ess_stats), 1), 1),
    }
