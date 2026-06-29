"""Kelly 投注比例 — 最优资金分配 (Kelly 1956, Bell System Tech. J.)

不预测号码。回答: "已知中奖概率分布, 每期投多少注最优?"

公式: f* = (bp - q) / b
  其中 b = 赔率 (odds), p = 赢率, q = 1-p
  对彩票: f* = (E[R] - E[C]) / σ²_R (近似, 离散非连续回报)

当 EV < 0 时 Kelly 推荐 f* = 0 (不投).
当 EV 从负变正时 (池子缩小), Kelly 给出渐进投入.

实现:
  1. 纯Kelly — 忽视实际买注粒度
  2. 离散Kelly — 按2元/注取整
  3. 多策略Kelly — 各策略独立分配
"""
import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

# ═══ 双色球奖级表 ═══
PRIZE_TABLE = {
    1: 5_000_000,  # 一等奖 (浮动, 取历史中位数~¥500万)
    2: 200_000,    # 二等奖 (浮动, ~¥20万)
    3: 3_000,      # 三等奖 5+0/4+1
    4: 200,        # 四等奖 5+0/4+1 → 实际上三等奖￥3000, 四等奖￥200
    5: 10,         # 五等奖 4+0/3+1
    6: 5,          # 六等奖 2+1/1+1/0+1
}

# 准确奖级 (cwl.gov.cn)
PRIZE_EXACT = {
    "1st": 5_000_000,  # 6+1
    "2nd": 200_000,    # 6+0
    "3rd": 3_000,      # 5+1
    "4th": 200,        # 5+0 / 4+1
    "5th": 10,         # 4+0 / 3+1
    "6th": 5,          # 2+1 / 1+1 / 0+1
}

TICKET_PRICE = 2  # 元/注
TOTAL_RED = 33
TOTAL_BLUE = 16


def _single_ticket_jackpot_prob(tickets, pool_v, pool_has_all_6_prob,
                                 coverage_pct, blue_coverage_pct):
    """单期头奖概率估算.
    
    Args:
        tickets: 购买注数
        pool_v: 号码池大小
        pool_has_all_6_prob: P(6红都在V池)
        coverage_pct: 池内覆盖百分比
        blue_coverage_pct: 蓝球覆盖百分比
    
    Returns:
        P(头奖) 近似值
    """
    # P(jackpot) = P(6红在池) × P(买到正确组合) × P(蓝球中)
    # 注意: tickets/comb(v,6)是正确的中奖概率基础, 不是 coverage_pct
    from ml.ssq_constants import TOTAL_RED
    import math
    if v < 6:
        return 0.0
    comb_v6 = math.comb(v, 6)
    p_pool = math.comb(v, 6) / math.comb(TOTAL_RED, 6)
    p_hit_in_pool = tickets / comb_v6
    p_blue = 1.0 / 16  # 单蓝球
    return p_pool * p_hit_in_pool * p_blue


def ev_per_ticket(tickets, pool_v, pool_has_all_6_prob=None,
                  coverage_pct=None, blue_coverage_pct=None):
    """每注期望价值 — 不假装t-wise覆盖等于中奖概率.

    头奖EV = P(6红在V池) × P(买到正确组合) × P(蓝球中) × 头奖金额.
    对3注/V=15: P(jackpot) ≈ 0.0045 × (3/5005) × (1/16) ≈ 1.7×10^-7
    """
    from ml.ssq_constants import (
        PRIZE_3RD, PRIZE_4TH, PRIZE_5TH, PRIZE_6TH,
    )
    import math

    v = pool_v
    p6 = math.comb(v, 6) / math.comb(TOTAL_RED, 6)
    p5 = math.comb(v, 5) * math.comb(TOTAL_RED - v, 1) / math.comb(TOTAL_RED, 6)
    p4 = math.comb(v, 4) * math.comb(TOTAL_RED - v, 2) / math.comb(TOTAL_RED, 6)

    comb_v6 = math.comb(v, 6)
    p_hit = tickets / comb_v6 if comb_v6 > 0 else 0
    # 蓝球: 每注独立蓝球, 最多覆盖tickets/16
    bp = min(tickets / 16, 1.0)

    ev = 0.0
    ev += p6 * p_hit * (bp * PRIZE_EXACT["1st"] + (1 - bp) * PRIZE_EXACT["2nd"])
    ev += p5 * p_hit * (bp * PRIZE_3RD + (1 - bp) * PRIZE_4TH)
    ev += p4 * p_hit * (bp * PRIZE_5TH + (1 - bp) * PRIZE_6TH)
    # 蓝球单独中6等奖（不需要红球任何匹配）
    ev += (1 - p4 - p5 - p6) * bp * PRIZE_6TH

    cost = tickets * TICKET_PRICE
    p_jp = p6 * p_hit * bp

    return {
        "ev_per_ticket": round(ev, 2),
        "cost_per_draw": cost,
        "net_ev": round(ev - cost, 2),
        "ev_cost_ratio": round(ev / cost, 2) if cost > 0 else 0,
        "p_jackpot_approx": round(p_jp, 12),
        "p_6_reds_in_pool_pct": round(p6 * 100, 4),
        "pool_v": v,
        "tickets": tickets,
        "verdict": "负EV: 最优注数=0 (彩票为负期望值博弈)" if ev < cost else "正EV? 异常",
    }


def kelly_fraction(ev_per_ticket_result):
    """Kelly 最优投注比例 (正EV时).

    f* = (bp - q) / b 的离散化版本.
    对彩票: 基于EV/成本比率 + 方差调整.

    返回: 推荐注数 (0 = 不投)
    """
    ev = ev_per_ticket_result["net_ev"]
    cost = ev_per_ticket_result["cost_per_draw"]
    tickets = cost // TICKET_PRICE

    if ev <= 0:
        return {
            "f_star": 0,
            "full_kelly_tickets": 0,
            "half_kelly_tickets": 0,
            "quarter_kelly_tickets": 0,
            "recommended_tickets": 0,
            "recommended_cost": 0,
            "verdict": "SKIP: 负EV, Kelly推荐=0",
            "reason": "长期正期望是投注的必要条件; 当前为负, 最优策略是不投",
        }

    # Kelly半本: f* = EV / variance (对数效用最大化)
    # 彩票方差极大, 使用 fractional Kelly: f* / 2 或 f* / 4
    p_win = ev_per_ticket_result["ev_per_ticket"] / ev_per_ticket_result["ev_per_ticket"] if ev_per_ticket_result["ev_per_ticket"] > 0 else 0.01
    odds = ev_per_ticket_result["ev_per_ticket"] / TICKET_PRICE if TICKET_PRICE > 0 else 0
    variance = ev_per_ticket_result["ev_per_ticket"]  # 粗略近似

    # 简化: 半Kelly = 净EV / 每票成本 × 0.5
    full_kelly_tickets = max(0, int(ev / TICKET_PRICE))
    half_kelly_tickets = max(0, int(ev / TICKET_PRICE * 0.5))

    # 对彩票的保守策略: 1/4 Kelly 因为方差极大
    quarter_kelly = max(0, int(ev / TICKET_PRICE * 0.25))

    return {
        "f_star": round(ev / cost, 4),
        "full_kelly_tickets": full_kelly_tickets,
        "half_kelly_tickets": half_kelly_tickets,
        "quarter_kelly_tickets": quarter_kelly,
        "recommended_tickets": quarter_kelly,  # 默认保守
        "recommended_cost": quarter_kelly * TICKET_PRICE,
        "verdict": (f"投入{quarter_kelly}注/期 (1/4 Kelly, 彩票保守)"
                    if quarter_kelly > 0 else "SKIP"),
        "reason": "彩票方差极高, 1/4 Kelly为保守起点",
        "reference": "Kelly 1956; Thorp 1997; MacLean-Thorp-Ziemba 2011",
    }


def capital_allocation_plan(capital, tickets_per_draw, ev_result):
    """给定本金, 规划投注策略.

    Args:
        capital: 本金 (元)
        tickets_per_draw: 每期注数
        ev_result: ev_per_ticket() 结果

    Returns:
        投注计划: 可持续期数, 破产概率估计等
    """
    cost_per_draw = tickets_per_draw * TICKET_PRICE
    if cost_per_draw <= 0:
        return {"ok": False, "msg": "注数必须>0"}

    max_draws = capital // cost_per_draw
    annual_draws = 156  # 每周3期 × 52周

    net_ev_per_draw = ev_result["net_ev"]
    expected_return = net_ev_per_draw * max_draws

    # 赌博破产问题 (Feller, 1968)
    # P(破产) ≈ (q/p)^N 对有利赌, 但对负EV赌必然破产
    if net_ev_per_draw < 0:
        ruin_verdict = "必然破产 (负EV)"
    else:
        # 正EV赌: Gambler's Ruin 近似
        ruin_verdict = "正EV, 但需大量期数才能收敛"

    return {
        "ok": True,
        "capital": capital,
        "tickets_per_draw": tickets_per_draw,
        "cost_per_draw": cost_per_draw,
        "max_sustainable_draws": max_draws,
        "max_sustainable_years": round(max_draws / annual_draws, 1),
        "expected_total_return": round(expected_return, 2),
        "ruin_assessment": ruin_verdict,
        "recommendation": (
            f"每期¥{cost_per_draw}, 本金¥{capital}可支持{max_draws}期 ({round(max_draws/annual_draws,1)}年)"
        ),
        "reference": "Feller 1968, 'An Introduction to Probability Theory' Ch. XIV",
    }


def compare_strategies(strategies: Dict[str, Dict]):
    """对比多个策略的Kelly分配.

    Args:
        strategies: {name: ev_result} 的字典
    
    Returns:
        各策略推荐注数和资金分配
    """
    results = []
    for name, ev in strategies.items():
        kelly = kelly_fraction(ev)
        results.append({
            "name": name,
            "ev_per_draw": ev["net_ev"],
            "kelly_tickets": kelly["quarter_kelly_tickets"],
            "verdict": kelly["verdict"],
        })

    results.sort(key=lambda x: -x["ev_per_draw"])
    return {
        "ok": True,
        "strategies": results,
        "best": results[0] if results else None,
        "note": "1/4 Kelly, 所有策略当前均为负EV, 最优注数=0",
        "reference": "Kelly 1956",
    }
