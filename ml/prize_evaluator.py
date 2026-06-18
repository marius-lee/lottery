"""一等奖评估 + EV计算框架

评估策略生成号码的中奖概率 vs 随机基线。
所有概率来自超几何分布 + 策略回测数据。
"""
import math
import numpy as np
from collections import Counter
from ml.ssq_constants import (
    TOTAL_RED, TOTAL_BLUE, PICK_RED,
    RED_EXPECTED_HITS, BLUE_HIT_PROB,
    PROB_3RD, PROB_4TH, PROB_5TH, PROB_6TH,
    PROB_1ST, PROB_2ND,
    PRIZE_3RD, PRIZE_4TH, PRIZE_5TH, PRIZE_6TH,
    PRIZE_1ST, PRIZE_2ND,
    TICKET_PRICE,
)


def random_baseline(n_tickets):
    """随机选号的理论基线。

    返回:
        {
            "n_tickets": N,
            "exp_red_hits_per_ticket": 1.0909,
            "blue_hit_rate_per_ticket": 0.0625,
            "p_first_prize": P(至少1注中6+1),  # 这是上限，因随机票可能重复
            "ev_per_ticket": 期望回报/注,
            "ev_ratio": EV / 票价,
        }
    """
    # 一等奖: P(至少1注6+1) ≈ 1 - (1 - 1/17721088)^N
    p_first = 1 - (1 - PROB_1ST) ** n_tickets

    # EV: 仅固定奖 + 一等奖期望
    ev_fixed = (PROB_3RD * PRIZE_3RD + PROB_4TH * PRIZE_4TH +
                PROB_5TH * PRIZE_5TH + PROB_6TH * PRIZE_6TH)
    ev_first = PROB_1ST * PRIZE_1ST
    ev_second = PROB_2ND * PRIZE_2ND
    ev_per_ticket = ev_fixed + ev_first + ev_second

    return {
        "n_tickets": n_tickets,
        "exp_red_hits_per_ticket": round(RED_EXPECTED_HITS, 4),
        "blue_hit_rate_per_ticket": round(BLUE_HIT_PROB, 4),
        "p_first_prize": p_first,
        "p_first_prize_pct": round(p_first * 100, 8),
        "ev_per_ticket": round(ev_per_ticket, 4),
        "ev_ratio": round(ev_per_ticket / TICKET_PRICE, 4),
        "cost": n_tickets * TICKET_PRICE,
        "expected_return": round(n_tickets * ev_per_ticket, 2),
    }


def evaluate_strategy_tickets(tickets, backtest_red_hits, backtest_blue_hits):
    """评估策略生成票集的中奖概率和期望收益。

    Args:
        tickets: [{reds: [int], blue: int}, ...]  策略生成的号码
        backtest_red_hits: [float, ...]  回测场均红球命中数 (每注)
        backtest_blue_hits: [float, ...]  回测蓝球命中率 (每注)

    返回:
        dict with coverage metrics, EV, and lift vs random
    """
    n = len(tickets)
    if n == 0:
        return {"error": "no tickets"}

    avg_red = np.mean(backtest_red_hits) if backtest_red_hits else RED_EXPECTED_HITS
    avg_blue = np.mean(backtest_blue_hits) if backtest_blue_hits else BLUE_HIT_PROB

    # ── 红球覆盖率 ──
    # 多少注包含 ≥k 个与开奖号码匹配的红球？
    # 使用超几何分布估计: P(hit=k) = C(6,k)*C(27,6-k)/C(33,6)
    # 策略提升: 将均值从1.0909提升到实际avg_red, 重新分配概率质量
    red_probs_random = _hypergeometric_red_probs()
    red_probs_strat = _shift_probs_to_mean(red_probs_random, avg_red)

    # ── 蓝球覆盖率 ──
    # 策略蓝球命中率
    blue_rate = avg_blue

    # ── 各奖等概率 ──
    # P(一等奖|策略) = P(6红) * P(蓝球中)
    # 其中 P(6红) 由 backtest 直方图估计 (若数据充足) 或 shift后的超几何
    prize_probs_strat = _compute_prize_probs(red_probs_strat, blue_rate)
    prize_probs_random = _compute_prize_probs(red_probs_random, BLUE_HIT_PROB)

    # ── EV计算 ──
    ev_strat_per_ticket = sum(
        p * prize for p, prize in [
            (prize_probs_strat["first"], PRIZE_1ST),
            (prize_probs_strat["second"], PRIZE_2ND),
            (prize_probs_strat["third"], PRIZE_3RD),
            (prize_probs_strat["fourth"], PRIZE_4TH),
            (prize_probs_strat["fifth"], PRIZE_5TH),
            (prize_probs_strat["sixth"], PRIZE_6TH),
        ]
    )

    # ── lift vs random ──
    base = random_baseline(n)

    return {
        "n_tickets": n,
        "cost": n * TICKET_PRICE,
        # 策略指标
        "avg_red_hits": round(avg_red, 4),
        "blue_hit_rate": round(blue_rate, 4),
        "red_lift": round(avg_red / RED_EXPECTED_HITS, 4),
        "blue_lift": round(blue_rate / BLUE_HIT_PROB, 4),
        # 各奖等概率 (策略 vs 随机)
        "p_first_prize_strat": prize_probs_strat["first"],
        "p_first_prize_random": base["p_first_prize"],
        "p_any_prize_strat": prize_probs_strat["any"],
        "p_any_prize_random": 1 - PROB_6TH,
        # 策略 lift
        "first_prize_lift": round(
            prize_probs_strat["first"] / base["p_first_prize"], 4
        ) if base["p_first_prize"] > 0 else float('inf'),
        "ev_lift": round(ev_strat_per_ticket / base["ev_per_ticket"], 4),
        # EV
        "ev_per_ticket": round(ev_strat_per_ticket, 4),
        "ev_random_per_ticket": base["ev_per_ticket"],
        "expected_return": round(n * ev_strat_per_ticket, 2),
        "return_rate": round(ev_strat_per_ticket / TICKET_PRICE, 4),
    }


def _hypergeometric_red_probs():
    """超几何分布: P(命中k个红球), k=0..6"""
    probs = {}
    for k in range(7):
        # C(6,k) * C(27,6-k) / C(33,6)
        numer = math.comb(PICK_RED, k) * math.comb(TOTAL_RED - PICK_RED, PICK_RED - k)
        denom = math.comb(TOTAL_RED, PICK_RED)
        probs[k] = numer / denom
    return probs


def _shift_probs_to_mean(base_probs, target_mean):
    """调整概率分布使期望命中数从1.0909偏移到target_mean。

    方法: 将概率质量从低命中向高命中线性偏移。
    保持 sum = 1 且所有值 ≥ 0。
    """
    shifted = dict(base_probs)
    current_mean = sum(k * p for k, p in shifted.items())
    delta = target_mean - current_mean

    if abs(delta) < 1e-6:
        return shifted

    # 简单方法: 成比例缩放各k的权重
    # 向k>mean的区间转移概率
    weight = {}
    for k in range(7):
        if delta > 0:
            weight[k] = 1.0 + delta * (k - current_mean) * 0.5
        else:
            weight[k] = 1.0 + delta * (k - current_mean) * 0.5
        weight[k] = max(0.01, weight[k])

    total_w = sum(weight[k] * base_probs[k] for k in range(7))
    for k in range(7):
        shifted[k] = weight[k] * base_probs[k] / total_w

    return shifted


def _compute_prize_probs(red_probs, blue_rate):
    """由红球命中分布和蓝球命中率计算各奖等概率。

    red_probs: {k: P(命中k红)}
    blue_rate: P(蓝球命中)

    奖等规则:
      一等奖 6+1: P(6红) * P(蓝中)
      二等奖 6+0: P(6红) * P(蓝不中)
      三等奖 5+1: P(5红) * P(蓝中)
      四等奖 5+0 或 4+1: P(5红)*P(蓝不中) + P(4红)*P(蓝中)
      五等奖 4+0 或 3+1: P(4红)*P(蓝不中) + P(3红)*P(蓝中)
      六等奖 蓝中: P(蓝中) - sum(蓝中且中更高奖)
    """
    p_blue = blue_rate
    p_no_blue = 1 - blue_rate

    p_first = red_probs.get(6, 0) * p_blue
    p_second = red_probs.get(6, 0) * p_no_blue
    p_third = red_probs.get(5, 0) * p_blue
    p_fourth = red_probs.get(5, 0) * p_no_blue + red_probs.get(4, 0) * p_blue
    p_fifth = red_probs.get(4, 0) * p_no_blue + red_probs.get(3, 0) * p_blue
    # 六等奖 = 蓝球中 减去 蓝球中且中更高奖
    p_sixth_blue = p_blue - (p_first + p_third + red_probs.get(4, 0) * p_blue + red_probs.get(3, 0) * p_blue)

    return {
        "first": p_first,
        "second": p_second,
        "third": p_third,
        "fourth": p_fourth,
        "fifth": p_fifth,
        "sixth": max(0, p_sixth_blue),
        "any": p_first + p_second + p_third + p_fourth + p_fifth + max(0, p_sixth_blue),
    }
