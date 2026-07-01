"""间隔/存活分析 — Weibull MLE 建模号码出现间隔节奏

核心理念:
  - 号码出现间隔的 Weibull shape > 1 → "风险递增": 越久不出越容易出
  - Newton-Raphson MLE 精确估计 shape/scale
  - 当前间隔超过期望 → hazard ratio > 1.1 → 加权

窗口: window=50 (回测验证短窗口信号最强, +1.7%)

用法:
  from ml.gap_analysis import compute_gap_weights, compute_blue_gap_weights
  red_w, diag = compute_gap_weights(data, window=50)
  blue_w, diag = compute_blue_gap_weights(data, window=50)
"""
import math


# ═══ Weibull MLE 拟合 ═══

def _fit_weibull_mle(gaps, max_iter=30, tol=1e-6):
    """Newton-Raphson MLE 拟合 Weibull(shape, scale).

    1D Newton 在 shape 上迭代, scale 通过解析解消去.
    """
    n = len(gaps)
    if n < 3:
        return 1.0, max(gaps) if gaps else 1.0

    mean_g = sum(gaps) / n
    if mean_g <= 0:
        return 1.0, 1.0

    # CV 近似初始化
    variance = sum((g - mean_g) ** 2 for g in gaps) / (n - 1) if n > 1 else mean_g * 0.1
    cv = max(1e-6, variance ** 0.5) / mean_g
    k = max(0.3, min(8.0, 1.0 / (cv ** 1.1)))

    log_gaps = [math.log(max(g, 1e-10)) for g in gaps]
    sum_log = sum(log_gaps)

    for _ in range(max_iter):
        t_pow = [g ** k for g in gaps]
        sum_pow = sum(t_pow)
        if sum_pow < 1e-30:
            break
        sum_pow_log = sum(t_pow[i] * log_gaps[i] for i in range(n))

        d1 = n / k + sum_log - (n / sum_pow) * sum_pow_log
        t_pow_log2 = [t_pow[i] * log_gaps[i] * log_gaps[i] for i in range(n)]
        d2 = -n / (k * k) - n * (sum(t_pow_log2) / sum_pow - (sum_pow_log / sum_pow) ** 2)

        if abs(d2) < 1e-15:
            break
        step = d1 / d2
        k_new = k - step
        if k_new <= 0.1: k_new = k * 0.5
        if k_new > 10.0: k_new = 10.0
        if abs(k_new - k) < tol:
            k = k_new; break
        k = k_new

    t_pow = [g ** k for g in gaps]
    sum_pow = sum(t_pow)
    scale = (sum_pow / n) ** (1.0 / k) if sum_pow > 0 and k > 0 else mean_g
    return max(0.2, min(8.0, k)), max(1e-6, scale)


def _weibull_hazard(t, shape, scale):
    """Weibull 风险函数 h(t) = (shape/scale)*(t/scale)^(shape-1)."""
    if t <= 0 or scale <= 0:
        return 1.0 / scale if scale > 0 else 0.0
    ratio = t / scale
    return (shape / scale) * (ratio ** (shape - 1))


# ═══ 红球间隔权重 ═══

def compute_gap_weights(data, window=50, min_weight=0.5, max_weight=2.0):
    """对每个红球号码, 用 Weibull hazard ratio 计算权重.

    shape > 1 (风险递增) 且 risk_ratio > 1.1 → 加权.
    否则保持中性.

    Args:
        data: [[period, r1..r6, blue], ...]
        window: 回溯期数 (默认 50)

    Returns:
        weights: [0.0]*34 (1-indexed)
        diag: 诊断信息
    """
    if not data or len(data) < window:
        return [1.0] * 34, {"error": "insufficient_data"}

    recent = data[-window:]
    appearances = {n: [] for n in range(1, 34)}
    for idx, row in enumerate(recent):
        for r in row[1:7]:
            appearances[r].append(idx)

    weights = [1.0] * 34
    total_idx = len(recent) - 1
    expected_gap = 33.0 / 6.0  # ≈ 5.5 期

    for num in range(1, 34):
        pos = appearances[num]
        if len(pos) < 2:
            continue

        gaps = [pos[i] - pos[i - 1] for i in range(1, len(pos))]
        shape, scale = _fit_weibull_mle(gaps)

        current_gap = total_idx - pos[-1]
        if current_gap <= 0:
            continue

        hazard_now = _weibull_hazard(current_gap, shape, scale)
        baseline = 1.0 / expected_gap
        if baseline <= 0:
            continue

        risk_ratio = hazard_now / baseline

        if shape > 1.0 and risk_ratio > 1.1:
            boost = 1.0 + min(1.0, (risk_ratio - 1.0) * 0.4)
            weights[num] = max(min_weight, min(max_weight, boost))
        elif shape > 1.0:
            weights[num] = max(min_weight, min(max_weight, 1.0 + (shape - 1.0) * 0.03))

    hot = sorted([(n, round(weights[n], 3)) for n in range(1, 34) if weights[n] > 1.08],
                 key=lambda x: -x[1])
    return weights, {
        "n_periods": len(recent),
        "hot": hot[:10],
        "n_hot": len(hot),
    }


# ═══ 蓝球间隔权重 ═══

def compute_blue_gap_weights(data, window=50):
    """蓝球间隔分析 — 同红球逻辑, 16选1.

    蓝球 baseline gap = 16 期.
    """
    if not data or len(data) < window:
        return [1.0] * 17, {"error": "insufficient_data"}

    recent = data[-window:]
    appearances = {b: [] for b in range(1, 17)}
    for idx, row in enumerate(recent):
        appearances[row[7]].append(idx)

    weights = [1.0] * 17
    total_idx = len(recent) - 1
    expected_gap = 16.0

    for b in range(1, 17):
        pos = appearances[b]
        if len(pos) < 2:
            continue

        gaps = [pos[i] - pos[i - 1] for i in range(1, len(pos))]
        shape, scale = _fit_weibull_mle(gaps)

        current_gap = total_idx - pos[-1]
        if current_gap <= 0:
            continue

        hazard_now = _weibull_hazard(current_gap, shape, scale)
        baseline = 1.0 / expected_gap
        if baseline <= 0:
            continue

        risk_ratio = hazard_now / baseline

        if shape > 1.0 and risk_ratio > 1.1:
            boost = 1.0 + min(1.0, (risk_ratio - 1.0) * 0.4)
            weights[b] = max(0.5, min(2.0, boost))
        elif shape > 1.0:
            weights[b] = max(0.5, min(2.0, 1.0 + (shape - 1.0) * 0.03))

    hot = sorted([(b, round(weights[b], 3)) for b in range(1, 17) if weights[b] > 1.08],
                 key=lambda x: -x[1])
    return weights, {
        "n_periods": len(recent),
        "hot": hot[:6],
        "n_hot": len(hot),
    }
