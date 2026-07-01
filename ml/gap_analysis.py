"""间隔/存活分析 — 用号码出现间隔节奏建模下次出现概率

理论基础:
  - 两个号码可以有相同的近期频率，但节奏完全不同：
    号码A: 隔一期出一期 (规律波动)
    号码B: 连出五期后沉寂五十期 (过冷)
  - 对每个号码，统计其历史出现间隔的分布，用 Weibull 建模。
  - 当前间隔越长 (即"多久没出")，在 Weibull 分布下越"欠账"，
    下次出现的条件概率越高 → 加权。

与 recent_bias 互补:
  - recent_bias: 看"近期出了几次" (密度)
  - gap_analysis: 看"距离上次出现多久" (节奏)

用法:
  from ml.gap_analysis import compute_gap_weights
  red_w, diag = compute_gap_weights(data, window=200)
"""
import math


def _fit_weibull(gaps):
    """用样本均值和变异系数反推 Weibull(shape, scale)."""
    if len(gaps) < 3:
        shape = 1.0
        scale = max(gaps) if gaps else 1.0
        return shape, scale
    n = len(gaps)
    mean_gap = sum(gaps) / n
    if mean_gap <= 0:
        return 1.0, 1.0
    variance = sum((g - mean_gap) ** 2 for g in gaps) / (n - 1) if n > 1 else mean_gap * 0.1
    std_gap = max(0.001, variance ** 0.5)
    cv = std_gap / mean_gap
    if cv < 0.01:
        shape = 5.0
    elif cv > 2.0:
        shape = 0.5
    else:
        shape = max(0.5, min(5.0, 1.0 / (cv ** 1.1)))
    # Gamma(1+1/shape) 近似
    gamma_vals = {0.5: 2.0, 0.6: 1.505, 0.7: 1.266, 0.8: 1.133,
                  0.9: 1.052, 1.0: 1.0, 1.2: 0.941, 1.5: 0.903,
                  2.0: 0.886, 3.0: 0.893, 4.0: 0.906, 5.0: 0.918}
    gamma_approx = gamma_vals.get(round(shape, 1), 0.9)
    scale = mean_gap / gamma_approx if gamma_approx > 0 else mean_gap
    return shape, max(1e-6, scale)


def compute_gap_weights(data, window=200, min_weight=0.5, max_weight=2.0):
    """对每个红球号码，基于间隔分析计算权重.

    Args:
        data: [[period, r1..r6, blue], ...] 按时间升序
        window: 回溯期数

    Returns:
        weights: [0.0]*34, weights[n] 是号码 n 的权重 (1-indexed)
        diag: 诊断信息
    """
    if not data:
        return [1.0] * 34, {"error": "no_data"}

    recent = data[-window:]
    appearances = {n: [] for n in range(1, 34)}
    for idx, row in enumerate(recent):
        for r in row[1:7]:
            appearances[r].append(idx)

    weights = [1.0] * 34
    diag = {"n_periods": len(recent), "hot": [], "cold": [], "shape_by_num": {}}
    total_idx = len(recent) - 1
    expected_gap = 33.0 / 6.0  # ≈ 5.5

    for num in range(1, 34):
        pos = appearances[num]
        if len(pos) < 2:
            continue
        gaps = [pos[i] - pos[i - 1] for i in range(1, len(pos))]
        shape, scale = _fit_weibull(gaps)
        diag["shape_by_num"][str(num)] = round(shape, 3)

        current_gap = total_idx - pos[-1]
        if current_gap <= 0:
            continue

        gap_ratio = current_gap / expected_gap

        if shape > 1.0 and gap_ratio > 1.0:
            # 风险递增 + 超过期望间隔 → 加权
            boost = min(2.0, 1.0 + (shape - 1.0) * min(gap_ratio - 1.0, 5.0) * 0.15)
            weights[num] = max(min_weight, min(max_weight, boost))
        elif shape > 1.0:
            weights[num] = max(min_weight, min(max_weight, 1.0 + (shape - 1.0) * 0.05))
        elif gap_ratio > 3.0:
            # 间隔远超期望 → 轻微降权
            weights[num] = max(min_weight, 1.0 - min(0.3, (gap_ratio - 3.0) * 0.1))

    hot = sorted(
        [(n, round(weights[n], 3)) for n in range(1, 34) if weights[n] > 1.1],
        key=lambda x: -x[1])
    cold = sorted(
        [(n, round(weights[n], 3)) for n in range(1, 34) if weights[n] < 0.9],
        key=lambda x: x[1])
    diag["hot"] = hot[:8]
    diag["cold"] = cold[:8]
    diag["n_hot"] = len(hot)
    diag["n_cold"] = len(cold)
    return weights, diag
