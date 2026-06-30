"""
策略实时监控 — SPRT + Kelly + EV 三位一体

从 prediction_log 读取实际命中数据，通过三个引擎独立分析：

1. SPRT (Wald 1945): 实时检测策略是否偏离随机基线
2. Kelly (1956): 基于实际命中率的最优投注比例
3. EV Calculator: 诚实展示每元投入的期望回报
"""
import math
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from ml.sprt import SPRTState, expected_sample_size
from ml.kelly import ev_per_ticket, TICKET_PRICE


def _load_hit_history(window=50):
    from server import db
    # 读取已兑奖的预测 (actual_reds_json IS NOT NULL), 按开奖期倒序
    conn = db.get_db()
    rows = conn.execute("""
        SELECT red_hits, blue_hit FROM prediction_log
        WHERE actual_reds_json IS NOT NULL AND red_hits >= 0
        ORDER BY period DESC
        LIMIT ?
    """, (window,)).fetchall()
    conn.close()
    red_hits = [r[0] for r in rows if r[0] is not None]
    blue_hits = [bool(r[1]) for r in rows if r[1] is not None]
    return red_hits, blue_hits


def _load_claim_history():
    from server.auto_claim import get_claims_summary
    try:
        return get_claims_summary()
    except Exception:
        return {"total_claimed": 0, "hit_distribution": {}, "strategy_stats": []}


def sprt_check(red_hits=None, blue_hits=None, pool_v=15, pool_blue=6):
    if red_hits is None or blue_hits is None:
        red_hits, blue_hits = _load_hit_history(50)

    red_state = SPRTState()
    if red_hits and len(red_hits) >= 5:
        p_null_red = 1.0 - (math.comb(15,0)*math.comb(18,6) + math.comb(15,1)*math.comb(18,5) +
                             math.comb(15,2)*math.comb(18,4)) / math.comb(33,6)
        p_alt_red = min(p_null_red * 1.15, 0.999)
        for h in red_hits:
            red_state.update(h >= 3, p_alt_red, p_null_red)

    blue_state = SPRTState()
    if blue_hits and len(blue_hits) >= 5:
        p_null_blue = pool_blue / 16
        p_alt_blue = min(p_null_blue * 1.2, 0.999)
        for h in blue_hits:
            blue_state.update(h, p_alt_blue, p_null_blue)

    r = red_state.summary()
    b = blue_state.summary()

    has_signal = (red_state.status == "significant" or blue_state.status == "significant")

    return {
        "ok": True,
        "red_sprt": r,
        "blue_sprt": b,
        "red_summary": _interpret_sprt(r, "red"),
        "blue_summary": _interpret_sprt(b, "blue"),
        "has_signal": has_signal,
        "verdict": ("检测到统计信号" if has_signal else "策略与随机基线无差异"),
        "red_samples": red_state.n,
        "blue_samples": blue_state.n,
        "red_history": red_state.history[-30:] if red_state.history else [],
        "blue_history": blue_state.history[-30:] if blue_state.history else [],
    }


def _interpret_sprt(state, label):
    if state["status"] == "significant":
        return label + "偏离随机 (p<0.05)"
    elif state["status"] == "not_significant":
        return label + "未偏离基线"
    else:
        return label + "数据积累中 (" + str(state["n"]) + "期)"


def kelly_analysis(tickets=3, pool_v=15, pool_blue=6):
    ev = ev_per_ticket(tickets, pool_v)
    cost_per_draw = tickets * TICKET_PRICE

    rand_6th = 1.0 / 17.0
    boosted_6th = pool_blue / 16.0

    return {
        "ok": True,
        "ev_analysis": ev,
        "cost_per_draw": cost_per_draw,
        "blue_lift": round(boosted_6th / rand_6th, 1),
        "verdict": "负EV" if ev["net_ev"] < 0 else "正EV",
    }


def monitor_panel(tickets=3, pool_v=15, pool_blue=6):
    red_hits, blue_hits = _load_hit_history(50)
    claims = _load_claim_history()

    hit_stats = {
        "red": {
            "mean": round(sum(red_hits)/len(red_hits), 2) if red_hits else 0,
            "max": max(red_hits) if red_hits else 0,
            "n": len(red_hits),
            "expected": round(6 * pool_v / 33, 2),
            "lift": round((sum(red_hits)/len(red_hits))/(6*pool_v/33), 2) if red_hits else 1.0,
            "note": "" if red_hits else "(等待开奖数据积累)"
        },
        "blue": {
            "rate": round(sum(1 for h in blue_hits if h)*100.0/max(len(blue_hits),1), 1),
            "expected": round(pool_blue*100.0/16, 1),
            "n": len(blue_hits),
            "lift": round((sum(1 for h in blue_hits if h)*100.0/max(len(blue_hits),1))/(pool_blue*100.0/16), 2) if blue_hits else 1.0,
            "note": "" if blue_hits else "(等待开奖数据积累)"
        },
    }

    sprt = sprt_check(red_hits, blue_hits, pool_v, pool_blue)
    kelly = kelly_analysis(tickets, pool_v, pool_blue, capital)

    red_lift = hit_stats["red"]["lift"]
    blue_lift = hit_stats["blue"]["lift"]
    if red_lift > 1.05 or blue_lift > 1.05:
        health = "高于基线" if sprt["has_signal"] else "偏高未达显著性"
    elif red_lift < 0.95 or blue_lift < 0.95:
        health = "低于基线"
    else:
        health = "与随机基线无差异"

    # Kelly 推荐注数 (离散化)
    kp = kelly
    kp_ok = kp.get("ok", False)
    recommended_n = kp.get("tickets_per_draw", tickets)

    return {
        "ok": True,
        "hit_stats": hit_stats,
        "sprt": sprt,
        "kelly": kelly,
        "claims_summary": claims,
        "status": {
            "health": health,
            "has_signal": sprt["has_signal"],
            "ev_verdict": kelly["verdict"],
            "tickets": tickets,
            "recommended_tickets": recommended_n,
            "cost_per_draw": tickets * TICKET_PRICE,
            "cost_per_draw": kp.get("cost_per_draw", 0),
            "sustainable_years": kp.get("max_sustainable_years", 0) if kp_ok else 0,
        },
        "note": "组合数学 + 统计决策理论的诚实评估。不预测号码。",
    }
