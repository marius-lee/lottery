"""位置条件概率模型 — 6×33 Laplace 概率矩阵

每个号码在 6 个排序位置上出现的频率不同。
构建 P[pos][num] 矩阵，出号时按位置加权采样。

检验: 卡方检验各位置的号码分布 vs 均匀分布。
"""
import math
from collections import Counter


def compute_position_weights(data, window=200, smooth=0.5):
    """构建位置概率矩阵。

    Args:
        data: [[period, r1..r6, blue], ...]  红球已排序
        window: 回溯期数
        smooth: Laplace 平滑系数

    Returns:
        pos_probs: [7][34] list (1-indexed, pos 1-6)
        diagnostics: dict
    """
    recent = data[-window:] if len(data) > window else data
    n = len(recent)

    # 计数: pos_counts[pos][num]
    pos_counts = [[0.0] * 34 for _ in range(7)]  # pos 1-6
    for row in recent:
        reds = sorted(row[1:7])
        for p in range(1, 7):
            pos_counts[p][reds[p - 1]] += 1.0

    # Laplace 平滑 + 归 一化
    pos_probs = [[0.0] * 34 for _ in range(7)]
    chi2_stats = {}
    for p in range(1, 7):
        total = n + smooth * 33
        expected = n / 33.0  # 均匀分布每号码期望次数
        chi2 = 0.0
        for num in range(1, 34):
            prob = (pos_counts[p][num] + smooth) / total
            pos_probs[p][num] = round(prob, 6)
            # 卡方贡献
            observed = pos_counts[p][num]
            if expected > 0:
                chi2 += (observed - expected) ** 2 / expected
        # 自由度 = 32
        chi2_stats[p] = {"chi2": round(chi2, 2), "dof": 32}

    # 偏热/偏冷诊断: 对每个位置, top-8 偏离最大的号码
    hot_by_pos = {}
    for p in range(1, 7):
        baseline = 1.0 / 33.0
        devs = [(num, pos_probs[p][num] - baseline) for num in range(1, 34)
                if pos_probs[p][num] > baseline * 1.1]
        devs.sort(key=lambda x: -x[1])
        hot_by_pos[f"pos{p}"] = [(num, round(d, 4)) for num, d in devs[:5]]

    return pos_probs, {
        "window": n,
        "chi2_by_pos": chi2_stats,
        "hot_by_pos": hot_by_pos,
    }


def sample_position_weighted(pos_probs, exclude=None, n=6):
    """按位置加权采样 6 个红球（无放回）。

    Returns: sorted list of 6 numbers
    """
    import random
    exclude = exclude or set()
    chosen = []

    for p in range(1, 7):
        # 候选: 未选的号码, 按 pos_probs[p] 加权
        cands = [num for num in range(1, 34) if num not in exclude and num not in chosen]
        if not cands:
            # fallback: pick any unpicked
            remaining = [num for num in range(1, 34) if num not in chosen]
            cands = remaining or list(range(1, 34))

        ws = [pos_probs[p][c] for c in cands]
        total = sum(ws)
        if total <= 0:
            pick = random.choice(cands)
        else:
            r = random.random() * total
            cum = 0.0
            pick = cands[0]
            for c, w in zip(cands, ws):
                cum += w
                if r < cum:
                    pick = c
                    break

        chosen.append(pick)

    # 确保 6 个且必须排序(因为位置概率模型基于排序后的位置)
    while len(chosen) < 6:
        remaining = [num for num in range(1, 34) if num not in chosen]
        if not remaining:
            remaining = list(range(1, 34))
        chosen.append(random.choice(remaining))
    return sorted(chosen[:6])
