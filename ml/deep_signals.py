"""深度信号注入 — 将SPRT/Kelly/FDR/变点检测结果反哺generate_tickets()

之前这些模块只做"报告"不做"决策"。现在整合为六个决策信号,
在每期出号时自动读取并影响行为。

信号清单:
  1. SPRT信号     → has_signal: 偏离基线时加大注数
  2. Kelly信号    → recommended_n: 最优注数
  3. FDR信号      → valid_methods: 过滤掉FDR不显著的方法
  4. 变点信号     → data_window: 只用变点后的数据
  5. NIST偏倚信号 → biased: 号码池加权方向
  6. 轮次表信号   → wheel_table: 已知最优轮次表
"""
from typing import Dict, List, Optional, Any


def collect_signals(data, tickets=3, capital=5000) -> Dict[str, Any]:
    """收集六路信号, 返回一个统一决策字典.

    generate_tickets() 读取此字典自动调整行为, 无需人工干预.
    """
    signals = {
        "sprt_has_signal": False,
        "sprt_verdict": "",
        "kelly_recommended_n": tickets,
        "kelly_verdict": "",
        "fdr_valid_methods": [],
        "changepoint_window": None,
        "nist_biased": False,
        "wheel_v": 15,
        "wheel_t": 4,
    }

    # 1. SPRT
    try:
        from ml.sprt import SPRTState
        from ml.monitor import _load_hit_history
        red_hits, blue_hits = _load_hit_history(50)
        if red_hits and len(red_hits) >= 5:
            import math
            pool_v = 15  # 回退: 偏差检测不可用时使用默认值
            p_null_red = 1.0 - (math.comb(15,0)*math.comb(18,6) + math.comb(15,1)*math.comb(18,5) +
                                 math.comb(15,2)*math.comb(18,4)) / math.comb(33,6)
            p_alt_red = min(p_null_red * 1.15, 0.999)
            red_state = SPRTState()
            for h in red_hits:
                red_state.update(h >= 3, p_alt_red, p_null_red)
            signals["sprt_has_signal"] = (red_state.status == "significant")
            signals["sprt_verdict"] = red_state.status
    except Exception:
        pass

    # 2. Kelly
    try:
        from ml.kelly import ev_per_ticket, capital_allocation_plan
        ev = ev_per_ticket(tickets)
        plan = capital_allocation_plan(capital, tickets, ev)
        if plan.get("ok"):
            signals["kelly_recommended_n"] = max(1, plan.get("tickets_per_draw", tickets))
            signals["kelly_verdict"] = plan.get("ruin_assessment", "")
    except Exception:
        pass

    # 3. FDR
    try:
        from ml.fdr import benjamini_hochberg, per_method_pvalues
        from ml.ensemble_aggregator import score_all_methods
        methods = score_all_methods(data)
        pvals = per_method_pvalues(data, methods)
        fdr_result = benjamini_hochberg(pvals, q=0.05)
        # 提取显著的方法名 (去除 #号码后缀)
        significant = list(set(
            item["name"].split("#")[0] 
            for item in fdr_result.get("significant", [])
        ))
        signals["fdr_valid_methods"] = significant
    except Exception:
        pass

    # 4. 变点检测
    try:
        from ml.changepoint import online_changepoint, detect_recent_window
        window = detect_recent_window(data)
        signals["changepoint_window"] = window
    except Exception:
        pass

    # 5. NIST
    try:
        from ml.nist_tests import run_nist_suite
        report = run_nist_suite(data)
        signals["nist_biased"] = report.has_bias
    except Exception:
        pass

    # 6. 已知轮次表 (combinatorial_math 已有)
    #   无需额外调用, 由 exact_cover 在红球模式时自动引用

    return signals
