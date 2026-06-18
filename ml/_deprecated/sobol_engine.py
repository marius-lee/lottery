"""选号流水线 — 两层过滤 + HMM排序

随机采样全组合池 → 硬过滤(14条) → 负选择(7条) → HMM加权 → 3注

不预测。不学习。排除无效组合后纯随机。
"""

import random
import numpy as np
from collections import Counter

from ml.ssq_constants import (
    FILTER_SUM_LO, FILTER_SUM_HI, FILTER_SPAN_LO, FILTER_SPAN_HI,
    FILTER_AC_LO, FILTER_AC_HI, FILTER_ODD_MIN, FILTER_ODD_MAX,
    FILTER_BIG_MIN, FILTER_BIG_MAX, FILTER_PRIME_MIN, FILTER_PRIME_MAX,
    FILTER_REPEAT_MIN, FILTER_REPEAT_MAX,
    FILTER_TAIL_GROUPS_MIN, FILTER_TAIL_GROUPS_MAX,
    FILTER_ROUTE012_MIN_TYPES, FILTER_MAX_GAP_LO, FILTER_MAX_GAP_HI,
    FILTER_CONSEC_MIN, FILTER_DRAGON_MAX, FILTER_PHOENIX_MIN,
)

PRIMES = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31}


def hard_filter(reds, last_draw=None):
    """硬过滤(14条行业标准) — 剔除结构无效组合。"""
    R = sorted(reds)
    v = []

    s = sum(R)
    if not (FILTER_SUM_LO <= s <= FILTER_SUM_HI):
        v.append(f"和值{s}∉[{FILTER_SUM_LO},{FILTER_SUM_HI}]")

    span = R[5] - R[0]
    if not (FILTER_SPAN_LO <= span <= FILTER_SPAN_HI):
        v.append(f"跨度{span}∉[{FILTER_SPAN_LO},{FILTER_SPAN_HI}]")

    diffs = set()
    for i in range(6):
        for j in range(i + 1, 6):
            diffs.add(R[j] - R[i])
    ac = len(diffs) - 5
    if not (FILTER_AC_LO <= ac <= FILTER_AC_HI):
        v.append(f"AC值{ac}∉[{FILTER_AC_LO},{FILTER_AC_HI}]")

    n_odd = sum(1 for n in R if n % 2 == 1)
    if not (FILTER_ODD_MIN <= n_odd <= FILTER_ODD_MAX):
        v.append(f"奇数{n_odd}个∉[{FILTER_ODD_MIN},{FILTER_ODD_MAX}]")

    n_big = sum(1 for n in R if n >= 17)
    if not (FILTER_BIG_MIN <= n_big <= FILTER_BIG_MAX):
        v.append(f"大号{n_big}个∉[{FILTER_BIG_MIN},{FILTER_BIG_MAX}]")

    n_prime = sum(1 for n in R if n in PRIMES)
    if not (FILTER_PRIME_MIN <= n_prime <= FILTER_PRIME_MAX):
        v.append(f"质数{n_prime}个∉[{FILTER_PRIME_MIN},{FILTER_PRIME_MAX}]")

    if last_draw:
        prev_set = set(last_draw[1:7])
        n_repeat = len(set(R) & prev_set)
        if not (FILTER_REPEAT_MIN <= n_repeat <= FILTER_REPEAT_MAX):
            v.append(f"重号{n_repeat}个∉[{FILTER_REPEAT_MIN},{FILTER_REPEAT_MAX}]")

    n_tails = len({n % 10 for n in R})
    if not (FILTER_TAIL_GROUPS_MIN <= n_tails <= FILTER_TAIL_GROUPS_MAX):
        v.append(f"尾数组数{n_tails}∉[{FILTER_TAIL_GROUPS_MIN},{FILTER_TAIL_GROUPS_MAX}]")

    if len({n % 3 for n in R}) < FILTER_ROUTE012_MIN_TYPES:
        v.append(f"012路不足{FILTER_ROUTE012_MIN_TYPES}种")

    gaps = [R[i + 1] - R[i] for i in range(5)]
    max_gap = max(gaps)
    if not (FILTER_MAX_GAP_LO <= max_gap <= FILTER_MAX_GAP_HI):
        v.append(f"最大邻距{max_gap}∉[{FILTER_MAX_GAP_LO},{FILTER_MAX_GAP_HI}]")

    z1 = sum(1 for n in R if n <= 11)
    z2 = sum(1 for n in R if 12 <= n <= 22)
    z3 = sum(1 for n in R if n >= 23)
    if z1 == 0 or z2 == 0 or z3 == 0:
        v.append(f"三区不全({z1}-{z2}-{z3})")

    n_consec = sum(1 for i in range(5) if R[i + 1] - R[i] == 1)
    if n_consec < FILTER_CONSEC_MIN:
        v.append("无连号")

    if R[0] > FILTER_DRAGON_MAX:
        v.append(f"龙头{R[0]}>{FILTER_DRAGON_MAX}")
    if R[5] < FILTER_PHOENIX_MIN:
        v.append(f"凤尾{R[5]}<{FILTER_PHOENIX_MIN}")

    return len(v) == 0, v


def negative_filter(reds, last_draw=None):
    """负选择(7条) — 剔除千万人实证无效的选法。"""
    R = sorted(reds)
    v = []
    lucky = {6, 8, 9, 16, 18, 28}
    unlucky = {4, 13, 14}

    if last_draw:
        if not (set(R) & set(last_draw[1:7])):
            v.append("不含上期重号(赌徒谬误)")

    if not any(n >= 32 for n in R):
        v.append("无≥32号(生日偏差)")

    if not any(R[i + 1] - R[i] == 1 for i in range(5)):
        v.append("无连号(连号回避)")

    if len([n for n in R if n in lucky]) > 3:
        v.append("吉利号过多")

    if not any(n in unlucky for n in R):
        v.append("无不吉利号(4/13/14回避)")

    if not (2 <= sum(1 for n in R if n % 2 == 1) <= 4):
        v.append("奇偶极端")
    if not (2 <= sum(1 for n in R if n >= 17) <= 4):
        v.append("大小极端")

    return len(v) == 0, v


class PipelineEngine:
    """选号流水线 — 两层过滤 + HMM排序"""

    def __init__(self, hmm_model=None):
        self.hmm = hmm_model

    def generate(self, last_draw=None, hmm_inference=None):
        """随机采样全组合池 → 硬过滤 → 负选择 → 攒够3注脱节即停。"""
        stats = {"sampled": 0, "hard_pass": 0, "hard_fail": Counter(),
                 "negative_pass": 0, "negative_fail": Counter()}

        all_reds = list(range(1, 34))
        all_blue = list(range(1, 17))
        tickets = []

        while len(tickets) < 3:
            stats["sampled"] += 1
            reds = sorted(random.sample(all_reds, 6))
            blue = random.choice(all_blue)

            h_ok, h_v = hard_filter(reds, last_draw)
            if not h_ok:
                stats["hard_fail"][h_v[0]] += 1
                continue
            stats["hard_pass"] += 1

            n_ok, n_v = negative_filter(reds, last_draw)
            if not n_ok:
                stats["negative_fail"][n_v[0]] += 1
                continue
            stats["negative_pass"] += 1

            # 脱节: 与已选票重叠≤3
            ok = True
            for t in tickets:
                if len(set(reds) & set(t["reds"])) > 3:
                    ok = False
                    break
            if not ok:
                continue

            score = 1.0
            if hmm_inference is not None and self.hmm is not None:
                score = self._hmm_score(reds, blue, hmm_inference)

            tickets.append({"reds": reds, "blue": blue, "score": round(score, 3)})

        n = stats["sampled"]
        stats["hard_pass_rate"] = round(stats["hard_pass"] / n * 100, 1)
        stats["negative_pass_rate"] = round(
            stats["negative_pass"] / max(1, stats["hard_pass"]) * 100, 1
        ) if stats["hard_pass"] > 0 else 0
        stats["overall_rate"] = round(stats["negative_pass"] / n * 100, 1)

        return tickets, stats

    def _hmm_score(self, reds, blue, hmm_inference):
        probs = hmm_inference.get("state_probs", {})
        score = 0.0
        for k, weight in probs.items():
            if weight < 0.05:
                continue
            for pos in range(6):
                score += weight * self.hmm.B_red[pos, k, reds[pos] - 1]
            score += weight * self.hmm.B_blue[k, blue - 1] * 0.3
        return score
