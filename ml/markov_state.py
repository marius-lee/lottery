"""马尔可夫状态转移 — 以最近1期开奖状态预测下一期宏观特征

理论基础:
  - 不预测具体号码，而是将每期开奖编码为"状态"（大号比例、奇偶比、跨度区间）。
  - 统计状态 A → 状态 B 的转移概率矩阵。
  - 给定最近一期的状态，找出概率最高的下一状态，该状态对应的
    号码特征（如"大号偏多"）转化为号码加权。

与 transfer_entropy 区别:
  - transfer_entropy: 微观的 A号码→B号码 时序因果量 (pairwise)
  - markov_state: 宏观的 全局状态→全局状态 转移 (holistic)

用法:
  from ml.markov_state import compute_markov_weights
  red_w, diag = compute_markov_weights(data, window=300)
"""
import math
from collections import Counter, defaultdict


# ═══ 状态编码 ═══

def _encode_state(reds):
    """将六码编码为 3 维离散状态 (big_ratio, odd_ratio, span_bucket).

    big_ratio: 0(0个大号)=0, 1(1-2个)=1, 2(3-4个)=2, 3(5-6个)=3
    odd_ratio: 同 big_ratio 编码
    span_bucket: 0(≤12)=0, 1(13-18)=1, 2(19-25)=2, 3(≥26)=3
    """
    s = sorted(reds)
    big = sum(1 for n in s if n >= 17)
    odd = sum(1 for n in s if n % 2 == 1)
    span = s[-1] - s[0]
    # 编码
    if big <= 1:
        br = 1
    elif big <= 3:
        br = 2
    else:
        br = 3
    if odd <= 1:
        oo = 1
    elif odd <= 3:
        oo = 2
    else:
        oo = 3
    if span <= 12:
        sb = 0
    elif span <= 18:
        sb = 1
    elif span <= 25:
        sb = 2
    else:
        sb = 3
    return (br, oo, sb)  # 3×3×4 = 36 种状态


def _state_feature(state):
    """从状态码反推加权特征.

    Returns (big_bias: float, odd_bias: float, span_bias: float)
    - big_bias > 0 → 偏向大号
    - odd_bias > 0 → 偏向奇数
    - span_bias > 0 → 偏向大跨度
    中性状态返回 (0, 0, 0) — 不加权。
    """
    br, oo, sb = state
    # 中性基线: br=2 (3-4大), oo=2 (3-4奇), sb=2 (19-25)
    big_bias = (br - 2) * 0.25   # [-0.25, 0.25]
    odd_bias = (oo - 2) * 0.20   # [-0.20, 0.20]
    span_bias = (sb - 2) * 0.15  # [-0.30, 0.15]
    return big_bias, odd_bias, span_bias


def compute_markov_weights(data, window=300, min_weight=0.6, max_weight=2.0):
    """基于马尔可夫状态转移计算号码权重.

    Args:
        data: [[period, r1..r6, blue], ...] 按时间升序
        window: 回溯期数

    Returns:
        weights: [0.0]*34 (1-indexed)
        diag: 诊断信息
    """
    if not data or len(data) < 2:
        return [1.0] * 34, {"error": "insufficient_data"}

    recent = data[-window:]

    # 构建转移计数矩阵: {(state_from, state_to): count}
    transitions = defaultdict(int)
    state_counts = defaultdict(int)
    for i in range(len(recent) - 1):
        s_from = _encode_state(recent[i][1:7])
        s_to = _encode_state(recent[i + 1][1:7])
        transitions[(s_from, s_to)] += 1
        state_counts[s_from] += 1

    # 当前最新一期状态
    current = _encode_state(recent[-1][1:7])

    # 预测下一状态: 找 P(current → next) 最高的 next
    candidates = []
    for (s_from, s_to), count in transitions.items():
        if s_from == current:
            prob = count / state_counts[s_from] if state_counts[s_from] > 0 else 0
            candidates.append((s_to, prob, count))

    candidates.sort(key=lambda x: -x[1])

    diag = {
        "n_periods": len(recent),
        "n_states": len(state_counts),
        "current_state": list(current),
        "top_transitions": [],
    }

    # 取概率最高的一个目标状态，计算特征偏差
    weights = [1.0] * 34
    if candidates and candidates[0][1] > 0.15:  # 概率 > 15% 才有效
        top_next = candidates[0][0]
        prob = candidates[0][1]
        big_bias, odd_bias, span_bias = _state_feature(top_next)

        diag["predicted_state"] = list(top_next)
        diag["confidence"] = round(prob, 3)

        for num in range(1, 34):
            w = 1.0
            # 大号加权/降权
            if big_bias != 0:
                if num >= 17:
                    w += big_bias
                else:
                    w -= big_bias
            # 奇数加权/降权
            if odd_bias != 0:
                if num % 2 == 1:
                    w += odd_bias
                else:
                    w -= odd_bias
            # 跨度不直接作用于单个号码，跳过 (跨度在 Stage 2 过滤)
            weights[num] = max(min_weight, min(max_weight, w))

        for cand in candidates[:5]:
            diag["top_transitions"].append({
                "to_state": list(cand[0]),
                "probability": round(cand[1], 3),
                "n_obs": cand[2],
            })
    else:
        diag["predicted_state"] = None
        diag["confidence"] = 0
        # 没有足够强的转移模式 → 中性权重
        diag["note"] = "no_strong_transition"

    diag["n_hot"] = sum(1 for n in range(1, 34) if weights[n] > 1.1)
    diag["hot"] = sorted(
        [(n, round(weights[n], 3)) for n in range(1, 34) if weights[n] > 1.1],
        key=lambda x: -x[1])[:8]

    return weights, diag
