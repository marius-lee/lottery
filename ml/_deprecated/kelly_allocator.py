"""Kelly Criterion 投注分配器 — 基于EV估计的最优注数决策.

Kelly公式 (Kelly 1956, 《A New Interpretation of Information Rate》):
  f* = (b·p - q) / b
  
  其中:
    b = 净赔率 (net odds) = (PRIZE / TICKET_PRICE) - 1
    p = 胜率
    q = 1 - p
  
  扩展: 多奖等嵌套Kelly (每个奖等独立计算, 取加权平均)
  
  参数 τ (温度/分数Kelly):
    f = τ · f*  (τ=0.25 保守, τ=0.5 中等, τ=1.0 激进)
    推荐 τ=0.25 对于彩票类负EV投注: 降低破产概率, 保留参与资格

用法:
  from ml.kelly_allocator import kelly_allocation
  result = kelly_allocation(ev_estimate, budget=100)
"""
from ml.ssq_constants import (
    TICKET_PRICE, PRIZE_1ST, PRIZE_2ND, PRIZE_3RD,
    PRIZE_4TH, PRIZE_5TH, PRIZE_6TH,
    PROB_1ST, PROB_2ND, PROB_3RD, PROB_4TH, PROB_5TH, PROB_6TH,
)


def _kelly_fraction(prob: float, prize: float, cost: float = TICKET_PRICE) -> float:
    """单奖等Kelly最优投注比例.
    
    f* = (b·p - q) / b  where b = prize/cost - 1, p=prob, q=1-p
    如果f* < 0, 返回 0 (不投).
    """
    if prob <= 0 or prize <= 0:
        return 0.0
    b = (prize / cost) - 1.0
    if b <= 0:
        return 0.0
    q = 1.0 - prob
    f = (b * prob - q) / b
    return max(0.0, f)


def kelly_allocation(
    ev_estimate: dict,
    budget: float = 100.0,
    tau: float = 0.25,
    max_tickets: int = 50,
    extra_red_lift: float = 1.0,
    extra_blue_lift: float = 1.0,
) -> dict:
    """基于Kelly公式的最优注数建议.
    
    Args:
        ev_estimate: 来自 prize_evaluator.evaluate_strategy_tickets 的EV估计
        budget: 可用预算 (元)
        tau: 分数Kelly系数 (0-1, 默认0.25保守)
        max_tickets: 最大注数上限
        extra_red_lift: 策略红球命中率提升系数 (vs 随机)
        extra_blue_lift: 策略蓝球命中率提升系数
        
    Returns:
        dict with optimal_n, expected_growth, fraction, breakdown by prize tier
    """
    # 各奖等策略概率 (从EV估计读取, 或退化为随机基线)
    avg_red = ev_estimate.get("avg_red_hits", 1.0909)
    blue_rate = ev_estimate.get("blue_hit_rate", 0.0625)
    red_lift = avg_red / 1.0909
    blue_lift = blue_rate / 0.0625

    # 策略调整后的各奖等概率
    # 简单线性缩放: P_strat = P_random * lift^(奖等敏感性)
    # 低奖等对lift不敏感, 高奖等指数敏感
    p_first_strat = PROB_1ST * (extra_red_lift ** 6) * (extra_blue_lift ** 1)
    p_second_strat = PROB_2ND * (extra_red_lift ** 6) * ((1 - blue_rate) / (1 - 0.0625))
    p_third_strat = PROB_3RD * (extra_red_lift ** 5) * (extra_blue_lift ** 1)
    p_fourth_strat = PROB_4TH * (extra_red_lift ** 4.5) * (1 + extra_blue_lift) / 2
    p_fifth_strat = PROB_5TH * (extra_red_lift ** 4) * (1 + extra_blue_lift) / 2
    p_sixth_strat = PROB_6TH * (extra_red_lift ** 1) * (extra_blue_lift ** 0.3)

    # 确保概率 ≤1
    p_first_strat = min(p_first_strat, 0.1)
    p_second_strat = min(p_second_strat, 0.2)

    # 各奖等独立Kelly
    tiers = [
        ("一等奖", p_first_strat, PRIZE_1ST),
        ("二等奖", p_second_strat, PRIZE_2ND),
        ("三等奖", p_third_strat, PRIZE_3RD),
        ("四等奖", p_fourth_strat, PRIZE_4TH),
        ("五等奖", p_fifth_strat, PRIZE_5TH),
        ("六等奖", p_sixth_strat, PRIZE_6TH),
    ]

    breakdown = {}
    total_fraction = 0.0
    for name, prob, prize in tiers:
        f_star = _kelly_fraction(prob, prize)
        breakdown[name] = {
            "prob": round(prob, 10),
            "prize": prize,
            "kelly_f": round(f_star, 8),
        }
        total_fraction += f_star

    # 应用分数Kelly + 上限
    weighted_fraction = tau * total_fraction
    # 转换注数: f = n * TICKET_PRICE / budget → n = f * budget / TICKET_PRICE
    optimal_n = int(weighted_fraction * budget / TICKET_PRICE)
    optimal_n = max(0, min(optimal_n, max_tickets))

    # 期望对数增长率
    # E[log wealth growth] = ∫ log(1 + f·(b-1)) dP
    # 近似: G(f) = Σ p_i log(1 + f·(prize_i/TICKET_PRICE - 1))
    def expected_growth(f_star_val):
        if f_star_val <= 0:
            return 0.0
        g = 0.0
        for name, prob, prize in tiers:
            b = prize / TICKET_PRICE - 1.0
            g += prob * math.log(max(1e-10, 1 + f_star_val * b))
        return g

    import math
    g_optimal = expected_growth(weighted_fraction)
    g_n_tickets = expected_growth(optimal_n * TICKET_PRICE / budget) if budget > 0 else 0.0

    return {
        "ok": True,
        "budget": budget,
        "ticket_price": TICKET_PRICE,
        "tau": tau,
        "kelly_fraction": round(weighted_fraction, 6),
        "optimal_n": optimal_n,
        "expected_log_growth": round(g_optimal, 6),
        "growth_per_draw": round(g_optimal, 8),
        "recommendation": (
            f"投 {optimal_n} 注 (预算{budget}元, τ={tau})"
            if optimal_n > 0 else "不推荐投注 (负EV)"
        ),
        "breakdown": breakdown,
        "red_lift": round(red_lift, 4),
        "blue_lift": round(blue_lift, 4),
        "note": (
            "Kelly最优用于连续正EV场景; 彩票为负EV, "
            "分数Kelly(τ<1)控制破产概率, τ=0.25为保守推荐"
        ),
    }


def kelly_simple(red_lift: float = 1.0, blue_lift: float = 1.0,
                 budget: float = 100.0, tau: float = 0.25) -> dict:
    """简化Kelly接口: 仅需红蓝lift参数."""
    return kelly_allocation(
        ev_estimate={"avg_red_hits": 1.0909 * red_lift, "blue_hit_rate": 0.0625 * blue_lift},
        budget=budget, tau=tau,
        extra_red_lift=red_lift, extra_blue_lift=blue_lift,
    )


# ── 预计算参考表 ──
def reference_table():
    """生成Kelly参考表: 不同red_lift/blue_lift下的最优注数."""
    lifts = [1.0, 1.1, 1.2, 1.5, 2.0, 3.0, 5.0, 10.0]
    rows = []
    for rl in lifts:
        for bl in lifts:
            if rl == 1.0 and bl == 1.0:
                continue  # 基线无意义
            r = kelly_simple(red_lift=rl, blue_lift=bl)
            if r["optimal_n"] > 0:
                rows.append({
                    "red_lift": rl, "blue_lift": bl,
                    "n": r["optimal_n"],
                    "f": r["kelly_fraction"],
                    "growth": r["growth_per_draw"],
                })
    return sorted(rows, key=lambda x: -x["n"])
