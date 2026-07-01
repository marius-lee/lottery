"""间隔/存活分析 — Weibull MLE 建模号码出现间隔节奏

理论基础:
  - 号码出现间隔的 Weibull shape > 1 → "风险递增": 越久不出越容易出
  - 用 Newton-Raphson MLE 精确估计 shape/scale
  - 当前间隔超出期望 → 条件概率高 → 加权

窗口选择 (回测扫描):
  window=30: lift +1.47%  window=50: lift +1.90%
  window=70: lift +0.23%  window=100: lift +0.70%
  window=200: lift +0.83%  window=500: lift +0.03%
  → 默认 window=50 (短窗口信号最强)

用法:
  from ml.gap_analysis import compute_gap_weights, compute_blue_gap_weights
  red_w, diag = compute_gap_weights(data, window=50)
"""
import math


def _fit_weibull_mle(gaps, max_iter=30, tol=1e-6):
    """Newton-Raphson MLE 拟合 Weibull(shape, scale).

    1D Newton 在 shape 上迭代, scale 通过解析解消去:
      λ(k) = (1/n Σ tᵢᵏ)^(1/k)

    对数似然导数:
      dlogL/dk = n/k + Σ log tᵢ - (n / Σ tᵢᵏ) Σ (tᵢᵏ log tᵢ)
    """
    n = len(gaps)
    if n < 3:
        return 1.0, max(gaps) if gaps else 1.0

    # 初始化: 用 CV 近似
    mean_g = sum(gaps) / n
    if mean_g <= 0:
        return 1.0, 1.0
    variance = sum((g - mean_g) ** 2 for g in gaps) / (n - 1) if n > 1 else mean_g * 0.1
    std_g = max(1e-6, variance ** 0.5)
    cv = std_g / mean_g
    k = max(0.3, min(8.0, 1.0 / (cv ** 1.1)))  # 初始估计

    log_gaps = [math.log(max(g, 1e-10)) for g in gaps]
    sum_log = sum(log_gaps)

    for _ in range(max_iter):
        # 计算 tᵢᵏ 和 tᵢᵏ log tᵢ
        t_pow = [g ** k for g in gaps]
        sum_pow = sum(t_pow)
        if sum_pow < 1e-30:
            break
        sum_pow_log = sum(t_pow[i] * log_gaps[i] for i in range(n))

        # dlogL/dk
        d1 = n / k + sum_log - (n / sum_pow) * sum_pow_log

        # d²logL/dk²
        t_pow_log2 = [t_pow[i] * log_gaps[i] * log_gaps[i] for i in range(n)]
        sum_pow_log2 = sum(t_pow_log2)
        d2 = -n / (k * k) - n * (sum_pow_log2 / sum_pow - (sum_pow_log / sum_pow) ** 2)

        if abs(d2) < 1e-15:
            break

        step = d1 / d2
        k_new = k - step
        if k_new <= 0.1:
            k_new = k * 0.5
        if k_new > 10.0:
            k_new = 10.0

        if abs(k_new - k) < tol:
            k = k_new
            break
        k = k_new

    # 解析解: scale
    t_pow = [g ** k for g in gaps]
    sum_pow = sum(t_pow)
    scale = (sum_pow / n) ** (1.0 / k) if sum_pow > 0 and k > 0 else mean_g

    return max(0.2, min(8.0, k)), max(1e-6, scale)


def _weibull_survival(t, shape, scale):
    """Weibull 生存函数 S(t) = exp(-(t/scale)^shape)."""
    if t <= 0:
        return 1.0
    return math.exp(-((t / scale) ** shape))


def _weibull_hazard(t, shape, scale):
    """Weibull 风险函数 h(t) = (shape/scale)*(t/scale)^(shape-1)."""
    if t <= 0 or scale <= 0:
        return 1.0 / scale if scale > 0 else 0.0
    ratio = t / scale
    return (shape / scale) * (ratio ** (shape - 1))


def compute_gap_weights(data, window=50, min_weight=0.5, max_weight=2.0):
    """对每个红球号码，基于间隔分析计算权重.

    用 Newton-Raphson MLE 拟合 Weibull, 计算当前间隔下的风险比。

    Args:
        data: [[period, r1..r6, blue], ...] 按时间升序
        window: 回溯期数 (默认50, 短窗口信号最强)

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
    diag = {"n_periods": len(recent), "hot": [], "cold": [], "shapes": {}}
    total_idx = len(recent) - 1
    expected_gap = 33.0 / 6.0  # ≈ 5.5 期

    for num in range(1, 34):
        pos = appearances[num]
        if len(pos) < 2:
            continue
        gaps = [pos[i] - pos[i - 1] for i in range(1, len(pos))]
        shape, scale = _fit_weibull_mle(gaps)
        diag["shapes"][str(num)] = round(shape, 3)

        current_gap = total_idx - pos[-1]
        if current_gap <= 0:
            continue

        # 当前风险 vs 基线风险 (均匀分布下的期望风险 = 1/expected_gap)
        hazard_now = _weibull_hazard(current_gap, shape, scale)
        hazard_baseline = 1.0 / expected_gap
        
        if hazard_baseline <= 0:
            continue

        risk_ratio = hazard_now / hazard_baseline

        # 极值检测: 当前间隔超过历史最大间隔的 90% 分位
        max_hist_gap = max(gaps) if gaps else 0
        p90_gap = sorted(gaps)[int(len(gaps) * 0.9)] if len(gaps) >= 10 else max_hist_gap
        is_extreme = current_gap > p90_gap and len(gaps) >= 4

        if shape > 1.0 and is_extreme:
            # 极度欠账: 不仅风险递增, 而且当前间隔罕见地长
            boost = 1.0 + min(1.0, (risk_ratio - 1.0) * 0.6)
            weights[num] = max(min_weight, min(max_weight, boost))
        elif shape > 1.0 and risk_ratio > 1.1:
            # 风险递增 + 当前风险高于基线
            boost = 1.0 + min(1.0, (risk_ratio - 1.0) * 0.4)
            weights[num] = max(min_weight, min(max_weight, boost))
        elif shape > 1.0:
            weights[num] = max(min_weight, min(max_weight, 1.0 + (shape - 1.0) * 0.03))
        elif risk_ratio < 0.7:
            weights[num] = max(min_weight, 0.92)

    hot = sorted([(n, round(weights[n], 3)) for n in range(1, 34) if weights[n] > 1.08],
                 key=lambda x: -x[1])
    cold = sorted([(n, round(weights[n], 3)) for n in range(1, 34) if weights[n] < 0.92],
                  key=lambda x: x[1])
    diag["hot"] = hot[:10]
    diag["cold"] = cold[:6]
    diag["n_hot"] = len(hot)
    diag["n_cold"] = len(cold)
    return weights, diag


# ═══ 蓝球间隔分析 ═══

def compute_blue_gap_weights(data, window=50):
    """蓝球间隔分析 — 同红球逻辑, 16选1.

    蓝球 baseline gap = 16/1 = 16 期.
    """
    if not data or len(data) < window:
        return [1.0] * 17, {"error": "insufficient_data"}

    recent = data[-window:]
    appearances = {b: [] for b in range(1, 17)}
    for idx, row in enumerate(recent):
        appearances[row[7]].append(idx)

    weights = [1.0] * 17
    diag = {"n_periods": len(recent), "hot": [], "shapes": {}}
    total_idx = len(recent) - 1
    expected_gap = 16.0  # 蓝球每16期期望出现一次

    for b in range(1, 17):
        pos = appearances[b]
        if len(pos) < 2:
            continue
        gaps = [pos[i] - pos[i - 1] for i in range(1, len(pos))]
        shape, scale = _fit_weibull_mle(gaps)
        diag["shapes"][str(b)] = round(shape, 3)

        current_gap = total_idx - pos[-1]
        if current_gap <= 0:
            continue

        hazard_now = _weibull_hazard(current_gap, shape, scale)
        hazard_baseline = 1.0 / expected_gap

        if hazard_baseline <= 0:
            continue

        risk_ratio = hazard_now / hazard_baseline

        max_hist_gap = max(gaps) if gaps else 0
        p90_gap = sorted(gaps)[int(len(gaps) * 0.9)] if len(gaps) >= 10 else max_hist_gap
        is_extreme = current_gap > p90_gap and len(gaps) >= 4

        if shape > 1.0 and is_extreme:
            boost = 1.0 + min(1.0, (risk_ratio - 1.0) * 0.6)
            weights[b] = max(0.5, min(2.0, boost))
        elif shape > 1.0 and risk_ratio > 1.1:
            boost = 1.0 + min(1.0, (risk_ratio - 1.0) * 0.4)
            weights[b] = max(0.5, min(2.0, boost))
        elif shape > 1.0:
            weights[b] = max(0.5, min(2.0, 1.0 + (shape - 1.0) * 0.03))
        elif risk_ratio < 0.7:
            weights[b] = max(0.5, 0.92)

    hot = sorted([(b, round(weights[b], 3)) for b in range(1, 17) if weights[b] > 1.08],
                 key=lambda x: -x[1])
    diag["hot"] = hot[:6]
    diag["n_hot"] = len(hot)
    return weights, diag
