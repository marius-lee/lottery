"""实验框架 — 策略统计显著性检验 + 置信区间

核心思路: 对每个策略做置换检验，判断其回测命中率是否
显著优于随机基线（期望红球命中=1.09, 蓝球=0.0625）。
"""
import math
import random
from collections import defaultdict
from server import db


def run_significance_test(n_permutations=1000):
    """对所有有回测数据的策略做置换检验。

    H0: 策略命中率 = 随机基线
    H1: 策略命中率 > 随机基线

    Returns:
        dict with per-strategy p-values, confidence intervals, and verdict.
    """
    all_data = db.load_draws()
    if not all_data or len(all_data) < 100:
        return {"ok": False, "msg": f"数据不足，当前{len(all_data)}期，需要≥100期"}

    N = len(all_data)
    RED_BASELINE = 1.09  # 6*6/33 数学期望

    # 1. 收集各策略的原始回测结果
    records = db.load_performance_log(limit=500)
    strat_hits = defaultdict(list)
    for r in records:
        strat_hits[r["strategy"]].append(r["red_hits"])

    # 2. 对每个策略做置换检验
    results = {}
    for name, hits in strat_hits.items():
        if len(hits) < 10:
            continue
        obs_mean = sum(hits) / len(hits)
        obs_std = _std(hits)

        # Permutation: 随机生成期望下的"命中"样本
        # 每次随机从6个红球中抽取，理论每期命中 = 6*6/33 ≈ 1.09
        count_better = 0
        n_perm = min(n_permutations, 10000)
        for _ in range(n_perm):
            sim_hits = _simulate_random_draws(len(hits))
            sim_mean = sum(sim_hits) / len(sim_hits)
            if sim_mean >= obs_mean:
                count_better += 1

        p_value = (count_better + 1) / (n_perm + 1)  # +1 for conservative estimate

        # 95% CI via bootstrap
        ci_low, ci_high = _bootstrap_ci(hits, n_bootstrap=2000)

        bonf_alpha = 0.05 / max(1, len(strat_hits))
        results[name] = {
            "n": len(hits),
            "mean_hit": round(obs_mean, 3),
            "std": round(obs_std, 3),
            "ci_95": [round(ci_low, 3), round(ci_high, 3)],
            "p_value": round(p_value, 4),
            "significant": p_value < bonf_alpha,
            "bonferroni_threshold": round(bonf_alpha, 6),
            "verdict": _verdict(p_value, bonf_alpha, obs_mean),
        }

    return {
        "ok": True,
        "baseline": RED_BASELINE,
        "permutations": n_permutations,
        "strategies": results,
    }


def _std(vals):
    m = sum(vals) / len(vals)
    return math.sqrt(sum((v - m)**2 for v in vals) / (len(vals) - 1))


def _bootstrap_ci(data, n_bootstrap=2000):
    """Bootstrap 95% 置信区间 (percentile method)"""
    n = len(data)
    means = []
    for _ in range(n_bootstrap):
        sample = [random.choice(data) for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = int(n_bootstrap * 0.025)
    hi = int(n_bootstrap * 0.975)
    return means[lo], means[hi]


def _simulate_random_draws(k):
    """模拟 k 次随机抽取的红球命中数。每次相当于从33个球中随机抽6个，
    然后与实际开奖比对。理论分布：超几何 H(33, 6, 6) 取均值 ≈ 1.09"""
    # 接近实际的离散分布: P(0)=26.7%, P(1)=43.8%, P(2)=24.6%, P(3)=4.6%, P(4)=0.3%
    probs = [0.267, 0.438, 0.246, 0.046, 0.003, 0.0, 0.0]
    cum = []
    s = 0
    for p in probs:
        s += p
        cum.append(s)
    cum[-1] = 1.0  # ensure total = 1

    hits = []
    for _ in range(k):
        r = random.random()
        for i, c in enumerate(cum):
            if r <= c:
                hits.append(i)
                break
    return hits


def _verdict(p_value, bonf_alpha, obs_mean):
    """用Bonferroni校正阈值判定 (Fisher 0.05仅为约定，非教条)
    来源: Bonferroni 1936; Fisher 1925 §43"""
    if p_value < 0.001:
        return "strong"       # 强证据：通过最严标准
    if p_value < bonf_alpha:
        return "significant"  # 通过Bonferroni校正
    if p_value < 0.05:
        return "uncorrected"  # 未校正显著，多重比较下不可靠
    if obs_mean > 1.2:
        return "promising"    # 方向对但统计不显著
    return "not_significant"
