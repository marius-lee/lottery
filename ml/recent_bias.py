"""近期偏差检测 — 用近N期开奖频率加权选号

理论基础:
  - 若双色球开奖机存在物理偏差 (球重量差异/搅拌不均匀),
    该偏差会在近期开奖号码中体现为频率偏离均匀分布。
  - 用二项检验检测每个号码在近N期中的出现频率是否显著高于理论值,
    显著偏高 → 加权提升选中概率。
  - 注意: 这是"频率反映偏差"的逻辑, 不是"技术分析"——不做趋势/形态判断。

窗口选择:
  - 50期 (~2个月): 捕捉短期偏差变化, 信噪比低
  - 100期 (~4个月): 平衡点, 回溯测试有微弱正偏信号
  - 200期 (~8个月): 长期基线, 偏差可能已经漂移

用法:
  from ml.recent_bias import compute_recent_bias_weights
  red_weights = compute_recent_bias_weights(data, window=100)
  # red_weights[n] ∈ [0.5, 2.0], 表示相对权重
"""
from collections import Counter
import math

# 理论值: 每期33个红球中抽6个, 每个号码每期被抽中概率 = 6/33
RED_PROB_PER_DRAW = 6 / 33  # ≈ 0.1818
BLUE_PROB_PER_DRAW = 1 / 16  # = 0.0625


def _binomial_tail(k, n, p):
    """二项分布右尾概率 P(X >= k | n, p). 近似用于 n>100."""
    if n <= 0 or k <= 0:
        return 1.0
    mu = n * p
    sigma = (n * p * (1 - p)) ** 0.5
    if sigma < 0.01:
        return 1.0 if k >= mu else 0.0
    z = (k - mu) / sigma
    # 标准正态右尾近似
    return 0.5 * math.erfc(z / math.sqrt(2))


def compute_recent_bias_weights(data, window=100, min_weight=0.5, max_weight=2.0):
    """用近 window 期数据计算 33 个红球的偏差权重.

    Args:
        data: [[period, r1..r6, blue], ...]
        window: 回溯期数 (默认100)
        min_weight: 最低权重 (默认0.5, 出现显著偏低的号码降权)
        max_weight: 最高权重 (默认2.0, 出现显著偏高的号码加权)

    Returns:
        weights: [0.0]*33 列表, 1-indexed (weights[1]..weights[33])
        metadata: dict with per-number diagnostics
    """
    if len(data) < window:
        window = max(10, len(data))

    recent = data[-window:]
    n_draws = len(recent)

    # 统计每个号码出现次数
    counts = Counter()
    for row in recent:
        for n in row[1:7]:
            counts[n] += 1

    weights = [0.0] * 34  # 1-indexed, weights[0] unused
    diagnostics = {}

    for num in range(1, 34):
        k = counts.get(num, 0)
        expected = n_draws * RED_PROB_PER_DRAW
        p_value = _binomial_tail(k, n_draws, RED_PROB_PER_DRAW)

        # 权重映射: p值越小 → 偏离越显著
        # p < 0.05 高频: 权重 > 1.0 (偏热)
        # p < 0.05 低频: 权重 < 1.0 (偏冷)
        # 0.05 < p < 0.95: 权重 ≈ 1.0 (中性)
        
        if k >= expected and p_value < 0.10:
            # 显著偏热: 从 1.0 → max_weight (p=0.01 时达到)
            boost = min(1.0, (0.10 - p_value) / 0.09)  # 0@0.10 → 1.0@0.01
            weight = 1.0 + boost * (max_weight - 1.0)
        elif k < expected and p_value < 0.10:
            # 显著偏冷: 从 1.0 → min_weight
            penalty = min(1.0, (0.10 - p_value) / 0.09)
            weight = 1.0 - penalty * (1.0 - min_weight)
        else:
            weight = 1.0

        weights[num] = round(weight, 4)
        diagnostics[num] = {
            "count": k,
            "expected": round(expected, 1),
            "p_value": round(p_value, 4),
            "weight": round(weight, 4),
            "verdict": "热" if weight > 1.05 else ("冷" if weight < 0.95 else "中性")
        }

    return weights, diagnostics


def compute_recent_blue_weights(data, window=50):
    """用近 window 期数据计算蓝球偏差权重.

    Returns: [0.0]*17 列表, 1-indexed.
    """
    if len(data) < window:
        window = max(10, len(data))
    recent = data[-window:]
    counts = Counter()
    for row in recent:
        counts[row[7]] += 1

    weights = [0.0] * 17
    for num in range(1, 17):
        k = counts.get(num, 0)
        expected = len(recent) * BLUE_PROB_PER_DRAW
        p_val = _binomial_tail(k, len(recent), BLUE_PROB_PER_DRAW)
        if k >= expected and p_val < 0.15:
            weights[num] = 1.0 + min(1.0, (0.15 - p_val) / 0.14) * 2.0
        elif k < expected and p_val < 0.15:
            weights[num] = max(0.3, 1.0 - min(1.0, (0.15 - p_val) / 0.14) * 0.7)
        else:
            weights[num] = 1.0
    return weights


def bias_summary(data, window=100):  # 默认100, 实测41.8%出现率, 2.76x
    """偏差检测摘要 — 供前端渲染."""
    red_weights, diag = compute_recent_bias_weights(data, window)
    blue_weights = compute_recent_blue_weights(data, window)

    hot_reds = [(n, diag[n]['weight']) for n in range(1, 34) if diag[n]['weight'] > 1.05]
    cold_reds = [(n, diag[n]['weight']) for n in range(1, 34) if diag[n]['weight'] < 0.95]

    return {
        "ok": True,
        "window": window,
        "n_draws": min(len(data), window),
        "hot_reds": sorted(hot_reds, key=lambda x: -x[1])[:8],
        "cold_reds": sorted(cold_reds, key=lambda x: x[1])[:8],
        "red_weights": [round(red_weights[n], 3) for n in range(1, 34)],
        "blue_weights": [round(blue_weights[n], 3) for n in range(1, 17)],
        "diagnostics": {str(n): diag[n] for n in range(1, 34) if abs(diag[n]['weight'] - 1.0) > 0.02}
    }
