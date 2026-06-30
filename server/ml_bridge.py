"""ML门面 — 微投资组合 + Mandel覆盖 + 一等奖EV评估

已删除:
  - XGBoost/LSTM/高级统计/Sirius/Thompson/GPT 桥接函数
  - OOT 验证 / 高级模型回测
  - luck_mode='blend' (运气规则, 已移除 — 与贪心冲突, 效果不显著)
  - bundle_a/bundle_b (捆绑投注, 已移除 — Lift≠未来, 操作链太长)

归档备份: docs/deprecated-backend-backup/ml_bridge.py
"""
from server import db

def generate_covering(v=15, t=4):
    """生成 Stefan Mandel 覆盖设计票集。"""
    all_data = db.load_draws()
    total = len(all_data) or 1
    ml_red = {}
    for n in range(1, 34):
        cnt = sum(1 for r in all_data if n in r[1:7])
        ml_red[n] = cnt / total
    ml_blue = {}
    for n in range(1, 17):
        cnt = sum(1 for r in all_data if r[7] == n)
        ml_blue[n] = cnt / total
    from ml.covering_design import generate_candidate_set, build_covering_tickets, lottery_ev_calculator
    hot = generate_candidate_set(ml_red, size=v)
    result = build_covering_tickets(hot, t=t)
    if result["ok"]:
        result["ev_analysis"] = lottery_ev_calculator(
            result["tickets"], hot, ml_blue, result.get("estimated_coverage_pct", 50))
    return result

# ============ 微投资组合 (3注优化) ============

def micro_3_tickets(n=3, soft=False, luck_mode='off', max_overlap=None,
                    diversity_mode=None, five_period=False, backtest_rank=False,
                    pattern_rules=False, author_mode=None, use_freq_blue=False,
                    blue_mode="freq", red_mode="pool", strategy_mode=None,
                    v_override=None, t=4):
    """从号码池不放回随机采样 n 注。"""
    from ml.micro_portfolio import generate_tickets
    return generate_tickets(n=n, soft=soft, luck_mode=luck_mode,
                            max_overlap=max_overlap, diversity_mode=diversity_mode,
                            five_period=five_period, backtest_rank=backtest_rank,
                            pattern_rules=pattern_rules,
                            author_mode=author_mode,
                            use_freq_blue=use_freq_blue,
                            blue_mode=blue_mode,
                            red_mode=red_mode,
                            strategy_mode=strategy_mode,
                            v_override=v_override, t=t, multi_period=multi_period)

def run_backtest(k=15, window=50):
    """运行全量回测, 返回各方法 recall@K."""
    from ml.ensemble_aggregator import run_full_backtest
    return run_full_backtest(k=k, window=window)

def get_backtest_results(limit=20):
    """获取最近回测结果."""
    return db.load_backtest_results(limit=limit)

def get_strategy_weights():
    """获取当前策略权重."""
    weights, perf = db.load_strategy_weights()
    return {"ok": True, "weights": weights, "perf": perf}

# ============ 偏差检测状态 ============

def bias_status_api():
    """偏差检测状态 — 信号级别 + 动态v + 热号 + 偏差排名.

    GET /api/bias/status
    """
    try:
        from ml.bias_v_selector import auto_v
        result = auto_v()
        return {
            "ok": True,
            "v": result.v,
            "signal_level": result.signal_level,
            "signal_level_cn": {
                "strong": "强信号",
                "moderate": "中等信号",
                "weak": "弱信号",
                "none": "无信号",
            }.get(result.signal_level, "未知"),
            "fdr_count": result.fdr_count,
            "hpd_count": result.hpd_count,
            "time_stable_count": result.time_stable_count,
            "reasoning": result.reasoning,
            "top_numbers": result.top_numbers[:result.v],
            "top_deviations": [
                {"num": n, "deviation": round(result.deviation_scores.get(n, 0), 1)}
                for n in result.top_numbers[:16]
            ],
            "v_options": [
                {"v": 10, "label": "强信号 (v=10)", "active": result.v == 10},
                {"v": 13, "label": "中信号 (v=13)", "active": result.v == 13},
                {"v": 16, "label": "弱信号 (v=16)", "active": result.v == 16},
                {"v": 15, "label": "纯覆盖 (v=15)", "active": result.v == 15 and result.signal_level == "none"},
            ],
        }
    except Exception as e:
        return {"ok": False, "msg": str(e)}


# ── 已归档的API (模块迁移至 ml/_deprecated/) ──

def fdr_filter(method_scores=None):
    """FDR筛选 — 已归档."""
    return {"ok": False, "msg": "FDR已归档至 ml/_deprecated/fdr_method_selector.py — 5方法无需多重比较校正"}

def entropy_hotness():
    """熵值选号 — 已归档."""
    return {"ok": False, "msg": "熵值模块已归档至 ml/_deprecated/entropy_selector.py — 无独立验证"}

def run_experiments(window=50):
    """A/B实验 — 已归档."""
    return {"ok": False, "msg": "实验模块待重建 — 当前无活跃实验预设"}

def advanced_generate(n=3, soft=False, budget=100.0):
    """智能引擎 — 简化为 ensemble_draw."""
    return ensemble_draw(n=n)

def integration_status_api():
    """引擎集成状态."""
    from ml.engine_integration import integration_status
    return integration_status()

def get_rule_status():
    """返回硬过滤规则状态。"""
    from ml.micro_portfolio import rule_status
    return rule_status()

# ============ 一等奖评估 + EV计算 ============

def evaluate_prizes(tickets, backtest_red_hits=None, backtest_blue_hits=None):
    """评估策略票集的中奖概率和期望收益 vs 随机基线。"""
    from ml.prize_evaluator import evaluate_strategy_tickets
    from ml.ssq_constants import RED_EXPECTED_HITS, BLUE_HIT_PROB
    if backtest_red_hits is None:
        backtest_red_hits = [RED_EXPECTED_HITS]
    if backtest_blue_hits is None:
        backtest_blue_hits = [BLUE_HIT_PROB]
    return evaluate_strategy_tickets(tickets, backtest_red_hits, backtest_blue_hits)

# ============ 断区转换法 (刘大军, 2014) ============

def get_zone_break_data():
    """返回行列分布表+断区3D历史。GET /api/zone-break/data"""
    from ml.zone_break import get_zone_break_history
    return get_zone_break_history(db.load_draws())

def filter_zone_break(break_rows, break_cols):
    """按断行/断列3D码过滤。POST /api/zone-break/filter"""
    from ml.zone_break import filter_zone_break
    return filter_zone_break(break_rows, break_cols)

# ============ 微尔算法 (Weier, 2017) ============

def generate_weier():
    """微尔算法: 自动检测规律→8步条件过滤→全量导出。"""
    from ml.weier_filter import generate_tickets_weier
    return generate_tickets_weier()

def generate_weier_manual(step_conditions):
    """微尔算法手动模式: 用户自选条件→过滤。

    POST /api/weier/manual  body: {"step1":{"1-2":["0:0","1:2"]},...}
    """
    from ml.weier_filter import generate_tickets_weier_manual
    return generate_tickets_weier_manual(step_conditions)

def get_weier_conditions():
    """返回所有可选项及其遗漏值/热温冷分类, 供前端渲染条件面板.

    GET /api/weier/conditions
    """
    from ml.weier_filter import _compute_omissions, ALL_PAIRS
    data = db.load_draws()
    if len(data) < 5:
        return {"ok": False, "msg": "数据不足"}

    omissions = _compute_omissions(data, ALL_PAIRS)
    pair_labels = {
        (0,1): "1-2", (1,2): "2-3", (2,3): "3-4", (3,4): "4-5", (4,5): "5-6",
        (0,2): "1-3", (0,3): "1-4", (0,4): "1-5", (0,5): "1-6",
        (1,3): "2-4", (1,4): "2-5", (1,5): "2-6",
        (2,4): "3-5", (2,5): "3-6",
    }
    conditions = {}
    for pair, label in pair_labels.items():
        om = omissions.get(pair, {})
        items = []
        for ratio in ['0:0','0:1','0:2','1:0','1:1','1:2','2:0','2:1','2:2']:
            o = int(om.get(ratio, 99)) if om.get(ratio, 99) != float('inf') else 99
            cls = 'hot' if o <= 10 else ('warm' if o <= 18 else 'cold')
            items.append({"ratio": ratio, "omission": o, "class": cls})
        conditions[label] = items
    return {"ok": True, "conditions": conditions}

# ============ 张委铭算法 (Zhang, 2015) ============

def generate_twelve_value(n=3, dan=None):
    """围号选号法 (2017版): 18种低胜率杀号→~12个红球候选+位置策略。

    GET /api/zhang/twelve-value?n=3&dan=12,5
    """
    data = db.load_draws()
    from ml.zhang_weiming import generate_weihao
    dan_list = dan if isinstance(dan, list) else ([dan] if dan else None)
    result = generate_weihao(data, n_tickets=n, locked_dans=dan_list)
    # 分配蓝球 (Laplace加权)
    if result.get("ok") and result.get("tickets"):
        from ml.micro_portfolio import _blue_freq_weights, _pick_unique_blue
        bw = _blue_freq_weights()
        used = set()
        for t in result["tickets"]:
            t["blue"] = _pick_unique_blue(bw, used)
            used.add(t["blue"])
    return result

def generate_eight_value(n=3):
    """后区围号选号法 (2017版): 10种低胜率后区杀号→~8个蓝球候选。

    GET /api/zhang/eight-value
    """
    from ml.zhang_weiming import generate_weihao_blue
    data = db.load_draws()
    result = generate_weihao_blue(data, n_tickets=n)
    # 分配红球 (Laplace加权随机, 每注不同)
    if result.get("ok") and result.get("tickets"):
        import random
        valid_reds = None
        try:
            import ml.micro_portfolio as mp
            if mp._state.valid_reds is not None and len(data) == mp._state.past_count:
                valid_reds = mp._state.valid_reds
        except Exception:
            pass
        if valid_reds:
            n_combos = len(valid_reds) // 6
            rng = random.Random(data[-1][0])
            used_reds = set()
            for t in result["tickets"]:
                for _ in range(500):
                    idx = rng.randrange(n_combos)
                    base = idx * 6
                    reds = tuple(valid_reds[base:base+6])
                    if reds not in used_reds:
                        used_reds.add(reds)
                        t["reds"] = list(reds)
                        break
                else:
                    t["reds"] = list(rng.sample(range(1, 34), 6))
    return result

def generate_zhang_combined(n=3, dan=None):
    """围号红球 + 后区围号蓝球 组合模式 (2017版).

    GET /api/zhang/combined?n=3&dan=12,5
    """
    from ml.zhang_weiming import generate_combined
    data = db.load_draws()
    dan_list = dan if isinstance(dan, list) else ([dan] if dan else None)
    return generate_combined(data, n_tickets=n, locked_dans=dan_list)

def generate_grid_selection(n=3):
    """行列选号法: 3×11网格自动断区。

    GET /api/zhang/grid
    """
    from ml.zhang_weiming import generate_grid_selection
    data = db.load_draws()
    return generate_grid_selection(data, n_tickets=n)

def generate_dan1():
    """一四定胆法: 按期号奇偶轮流定1个胆码。

    GET /api/zhang/dan1
    """
    from ml.zhang_weiming import generate_dan1_alternating
    return generate_dan1_alternating(db.load_draws())

def generate_dan2():
    """定2胆最优法: 杀号方法两两组合找最高频两号组合。

    GET /api/zhang/dan2
    """
    from ml.zhang_weiming import generate_dan2_optimal
    return generate_dan2_optimal(db.load_draws())

# ============ 李志林算法 (Li, 2012) ============

def generate_li_zhilin(n=3, **kwargs):
    """李志林综合出号: 按用户勾选的方法组合.

    GET /api/lizhilin/tickets?n=3&dan8=1&dan3=1&trans=1&kill=1&btail=1&bten=0&bperiod=0
    """
    from ml.li_zhilin import generate_tickets
    flags = {
        "use_dan8": kwargs.get("dan8", 1) == 1,
        "use_dan3": kwargs.get("dan3", 1) == 1,
        "use_transition": kwargs.get("trans", 1) == 1,
        "use_kill": kwargs.get("kill", 1) == 1,
        "use_blue_tail12": kwargs.get("btail", 1) == 1,
        "use_blue_ten": kwargs.get("bten", 0) == 1,
        "use_blue_period": kwargs.get("bperiod", 0) == 1,
    }
    return generate_tickets(db.load_draws(), n_tickets=n, **flags)

# ============ 彭浩算法 (Peng, 2010) ============

def peng_channel_all_positions():
    """五均线号码通道: 7个位置全部计算.

    GET /api/peng/channel
    """
    from ml.peng_hao import compute_all_channels
    data = db.load_draws()
    if len(data) < 19:
        return {"ok": False, "msg": f"数据不足, 需要至少19期, 当前{len(data)}期"}
    channels = compute_all_channels(data)
    return {"ok": True, "positions": channels, "periods_used": len(data)}

def peng_direction_all_positions():
    """方向预测: 7个位置的三方向转移矩阵+九方向分类.

    GET /api/peng/direction
    """
    from ml.peng_hao import direction_transition_matrix, classify_9_direction
    data = db.load_draws()
    if len(data) < 3:
        return {"ok": False, "msg": "数据不足"}
    result = {}
    for pos in range(7):
        if pos < 6:
            vals = [row[pos + 1] for row in data]
        else:
            vals = [row[7] for row in data]
        trans = direction_transition_matrix(data, position=pos)
        nine_dir = classify_9_direction(vals)
        result[f"pos_{pos}"] = {
            "current_3_dir": trans["current_direction"],
            "current_9_dir": nine_dir["label"],
            "transition_probs": trans["transition_probs"],
            "reversal_rate": trans["reversal_rate"],
            "predicted_next": trans["predicted_next"],
        }
    return {"ok": True, "positions": result}

def peng_extreme_rules():
    """极端值方向规则.

    GET /api/peng/extreme
    """
    from ml.peng_hao import extreme_rules
    data = db.load_draws()
    if len(data) < 2:
        return {"ok": False, "msg": "数据不足"}
    return extreme_rules(data)

def peng_generate_tickets(n=3, use_channel=True, use_direction=True, use_extreme=True):
    """彭浩波动三要素综合出号.

    GET /api/peng/tickets?n=3&channel=1&direction=1&extreme=1
    """
    from ml.peng_hao import generate_tickets
    data = db.load_draws()
    return generate_tickets(data, n=n, use_channel=use_channel,
                           use_direction=use_direction, use_extreme=use_extreme)

def peng_blue_prediction():
    """蓝球通道+方向预测.

    GET /api/peng/blue
    """
    from ml.peng_hao import compute_channel, classify_9_direction
    data = db.load_draws()
    if len(data) < 19:
        return {"ok": False, "msg": "数据不足"}
    ch = compute_channel(data, position=6)
    vals = [row[7] for row in data]
    nine = classify_9_direction(vals)
    return {"ok": True, "channel": ch, "direction_9": nine}

# ============ 吴明蓝球 (Wu Ming, 2010) ============

def wuming_extreme_dan():
    """极值优先胆码检测.

    GET /api/wuming/extreme-dan
    """
    from ml.wuming import extreme_value_dan as _extreme_value_dan
    return _extreme_value_dan(db.load_draws())

def wuming_sum_compound():
    """复合战法定位和值.

    GET /api/wuming/sum-compound
    """
    from ml.wuming import wu_sum_compound as _wu_sum_compound
    return _wu_sum_compound()

def xia_sub4_add4_blue():
    """夏志强减4加4测蓝法.

    GET /api/wuming/sub4-add4
    """
    from ml.xia_zhiqiang import xia_sub4_add4_blue as _xia_sub4_add4_blue
    return _xia_sub4_add4_blue()

def xia_compute_reds():
    """夏志强计算与观察法.

    GET /api/wuming/compute-reds
    """
    from ml.xia_zhiqiang import xia_compute_reds as _xia_compute_reds
    return _xia_compute_reds()

def wuming_position_filter():
    """6位置价值区域检查.

    GET /api/wuming/positions
    """
    from ml.wuming import POSITION_VALUABLE
    return {"ok": True, "positions": {str(k): list(v) for k, v in POSITION_VALUABLE.items()},
            "source": "吴明2006.9 Ch4: 位置战法"}

def wuming_repeat_analysis():
    """重号战法分析.

    GET /api/wuming/repeats
    """
    from ml.wuming import repeat_method as _repeat_method
    return _repeat_method(db.load_draws())

def wuming_period5():
    """5期重号摆动预测.

    GET /api/wuming/period5
    """
    from ml.wuming import period5_hotness as _period5_hotness
    return _period5_hotness()

def wuming_cold9():
    """9期冷号策略.

    GET /api/wuming/cold9
    """
    from ml.wuming import period9_cold as _period9_cold
    return _period9_cold()

def wuming_zone6():
    """6区间排除法.

    GET /api/wuming/zone6
    """
    from ml.wuming import zone6_exclusion as _zone6_exclusion
    return _zone6_exclusion()

def wuming_cyclic_oscillation():
    """蓝球循环振荡预测.

    GET /api/wuming/oscillation
    """
    from ml.wuming import wuming_cyclic_oscillation as _wuming_cyclic_oscillation
    return _wuming_cyclic_oscillation()

def wuming_blue_extreme_alert():
    """蓝球遗漏警报.

    GET /api/wuming/blue-alert
    """
    from ml.wuming import wuming_blue_extreme_alert as _wuming_blue_extreme_alert
    return _wuming_blue_extreme_alert()

def blue_pick(use_freq_blue=False, five_period=False, pattern_rules=False):
    """蓝球独立出号: Laplace频率top-6窄池.

    GET /api/blue/pick?use_freq_blue=1
    """
    from ml.micro_portfolio import _freq_blue_candidates, _blue_freq_weights, _five_period_boost, _pattern_blue_boost
    import random

    if use_freq_blue:
        cands = _freq_blue_candidates(n=6)
        return {"ok": True, "candidates": sorted(cands), "mode": "freq", "count": len(cands)}
    else:
        # Fallback: frequency weights
        weights = _blue_freq_weights()
        if five_period:
            fpb = _five_period_boost()
            weights = [weights[i] * fpb[i] for i in range(16)]
        if pattern_rules:
            ppb = _pattern_blue_boost()
            weights = [weights[i] * ppb[i] for i in range(16)]
        top6 = sorted(range(16), key=lambda i: -weights[i])[:6]
        return {"ok": True, "candidates": [b+1 for b in top6], "mode": "weighted", "count": 6}

def generate_jiang_jialin(n=3, use_gap=True, use_span=True,
                           use_pattern=True, use_shrink=True, blue_mode='mod3'):
    """蒋加林排列型思维出号.

    GET /api/jiangjialin/tickets?n=3
    """
    from ml.jiang_jialin import generate_tickets
    data = db.load_draws()
    return generate_tickets(data, n=n,
                            use_gap=use_gap, use_span=use_span,
                            use_pattern=use_pattern, use_shrink=use_shrink,
                            blue_mode=blue_mode)

# ============ 李相春 趋势分析 (2003) ============

def lixiangchun_spread(numbers):
    """散度分析 — 号码集中/分散程度的数学度量.

    GET /api/lixiangchun/spread?numbers=1,5,9,13,18,26
    """
    from ml.li_xiangchun import compute_spread
    return {"spread": compute_spread(numbers)}

def lixiangchun_skewness(current, previous):
    """偏度分析 — 本期号码相对上期的整体偏移.

    GET /api/lixiangchun/skewness?current=1,3,5,6,11,12,21&previous=2,10,16,24,26,27,28
    """
    from ml.li_xiangchun import compute_skewness
    return {"skewness": compute_skewness(current, previous)}

def lixiangchun_ac_value(numbers):
    """AC值分析 — 算术复杂性.

    GET /api/lixiangchun/ac?numbers=1,5,9,13,18,26,34
    """
    from ml.li_xiangchun import compute_ac_value
    return {"ac_value": compute_ac_value(numbers)}

def lixiangchun_sanlang():
    """三浪分析 — 冷号→热号反转信号.

    GET /api/lixiangchun/sanlang
    """
    from ml.li_xiangchun import sanlang_predict
    data = db.load_draws()
    return sanlang_predict(data)

def lixiangchun_dhr(num):
    """DHR — 连续两期出现比率.

    GET /api/lixiangchun/dhr?num=7
    """
    from ml.li_xiangchun import compute_dhr
    data = db.load_draws()
    dhr = compute_dhr(data, num)
    return {"num": num, "dhr": dhr, "sticky": dhr < 6.0}

# ============ 刘大军算法 (Liu, 2010-2014) ============

def liudajun_position_tails(window=50):
    """每位置尾数分布分析 — 刘大军定尾选号法核心.

    GET /api/liudajun/position-tails?window=50
    """
    from ml.liu_dajun import position_tail_analysis
    return position_tail_analysis(db.load_draws(), window=window)

# ============ 李相春算法 (Li, 2003-2009) ============

def lixiangchun_dashboard():
    """李相春三书全部信号聚合 — 一次返回所有指标.

    GET /api/lixiangchun/dashboard
    """
    from ml.li_xiangchun import dashboard
    return dashboard(db.load_draws())

def lixiangchun_trend_score(reds, blue=None):
    """李相春趋势分析综合评分.

    GET /api/lixiangchun/trend-score?reds=1,5,9,13,18,26
    """
    from ml.li_xiangchun import trend_score
    data = db.load_draws()
    return trend_score(data, reds, blue)

def lixiangchun_generate(n=3):
    """李相春风格出号 — 趋势分析+散度/偏度/AC值过滤.

    GET /api/lixiangchun/generate?n=3
    """
    from ml.li_xiangchun import generate_tickets
    data = db.load_draws()
    result = generate_tickets(data, n_tickets=n)
    return {"ok": True, "algorithm": "李相春 趋势分析 (2003)",
            "tickets": result["tickets"], "stats": result["stats"]}

# ============ 红球/蓝球独立出号 ============

def red_pick(n=3, soft=False, diversity_mode=None, max_overlap=None):
    """红球独立出号: 返回池子状态 + 红球号码.

    GET /api/red/pick?n=3
    """
    from ml.micro_portfolio import generate_tickets
    result = generate_tickets(n=n, soft=soft,
                              diversity_mode=diversity_mode, max_overlap=max_overlap)
    if not result.get("ok"):
        return {"ok": False, "msg": result.get("msg", "生成失败"),
                "pool_empty": True, "pool_size": 0}
    tickets = result.get("tickets", [])
    return {
        "ok": True,
        "pool_empty": False,
        "pool_size": result.get("pool_size"),
        "pool_valid_reds": result.get("pool_valid_reds"),
        "soft_excluded": result.get("soft_excluded", 0),
        "reds": [t["reds"] for t in tickets],
    }
def generate_covering_diverse(v=15, t=4, n=6, max_overlap=None, five_period=False):
    """覆盖设计 + 蓝球分配。"""
    from ml.micro_portfolio import generate_tickets_covering
    from ml.covering_design import generate_candidate_set
    all_data = db.load_draws()
    total = len(all_data) or 1
    ml_red = {}
    for num in range(1, 34):
        cnt = sum(1 for r in all_data if num in r[1:7])
        ml_red[num] = cnt / total
    hot = generate_candidate_set(ml_red, size=v)
    return generate_tickets_covering(n=n, hot_numbers=hot, t=t, max_overlap=max_overlap, five_period=five_period)

# ── 偏差增强 (Thompson + Gumbel-Max + 覆盖设计) ──

def bias_draw(n=3):
    """偏差增强出号 — Dirichlet后验 + Thompson采样 + Gumbel-Max."""
    from ml.bias_engine import bias_tickets
    return bias_tickets(k=15, t=4, n=n)

# ── Black-Litterman 融合 ──

def bl_draw(n=3):
    """B-L融合出号 — 多方法评分加权贝叶斯融合.

    用 ensemble_aggregator 的5种方法各自评分, FDR校正, 加权平均,
    取 top-15 红球用覆盖设计生成号码. 替代原型 black_litterman.py.
    """
    from ml.ensemble_aggregator import (
        score_all_methods, aggregate_scores, select_hot_numbers
    )
    from ml.fdr import benjamini_hochberg, per_method_pvalues
    from ml.covering_design import build_covering_tickets
    from ml.micro_portfolio import _blue_freq_weights, _pick_blue

    data = db.load_draws()
    if len(data) < 30:
        return {"ok": False, "msg": "数据不足, 需≥30期"}
    
    try:
        # 1. 各方法评分
        methods = score_all_methods(data)
        # 2. FDR校正
        pvals = per_method_pvalues(data, methods)
        fdr = benjamini_hochberg(pvals, q=0.05)
        fdr_names = set(item["name"].split("#")[0] for item in fdr.get("significant", []))
        # 3. 加权聚合 (FDR不显著的方法权重×0.1)
        weights = {}
        for name in methods:
            weights[name] = 1.0 if name in fdr_names else 0.1
        final = aggregate_scores(methods, weights, fdr_filter=True, data=data)
        # 4. 选top-15热号
        hot = select_hot_numbers(final, k=15)
        # 5. 覆盖设计
        result = build_covering_tickets(hot, t=4, target_tickets=n)
        if not result.get("ok") or not result.get("tickets"):
            return {"ok": False, "msg": "覆盖设计无解"}
        # 6. 分配蓝球
        bw = _blue_freq_weights()
        tickets = []
        for reds in result["tickets"][:n]:
            tickets.append({"reds": list(reds), "blue": _pick_blue(bw)})
        return {
            "ok": True, "algorithm": "B-L融合(FDR加权)",
            "tickets": tickets, "budget": n,
            "cost_rmb": n * 2,
            "pool_size": len(hot),
            "fdr_significant": len(fdr_names),
            "ev_estimate": {"ev_per_draw": -0.3 * n, "cost_per_draw": n * 2},
        }
    except Exception as e:
        return {"ok": False, "msg": f"B-L融合失败: {e}"}

# ── 分位策略 ──

def position_draw(n=3):
    """分位策略出号 — 每红球位置独立选最优方法, 再组合成票.

    对6个红球位置分别运行多种方法, 每个位置选历史命中最高的方法,
    6个位置独立选号后组合, 贪心最大化Jaccard距离选注.
    """
    from ml.ensemble_aggregator import (
        score_all_methods, _top_k_indices
    )
    from ml.micro_portfolio import (
        _blue_freq_weights, _pick_blue, _greedy_diverse_tickets
    )
    from ml.covering_design import build_covering_tickets

    data = db.load_draws()
    if len(data) < 30:
        return {"ok": False, "msg": "数据不足, 需≥30期"}

    try:
        # 1. 用5个方法各自选 top-6
        methods = score_all_methods(data)
        position_candidates = {p: set() for p in range(6)}
        for name, scores in methods.items():
            top_k = _top_k_indices(scores, 6)  # 每方法推荐6个号
            for p, num in enumerate(top_k):
                position_candidates[p].add(num + 1)  # 0-index → 1-index

        # 2. 融合成一个号码池 (跨位置去重)
        all_hot = list(set().union(*position_candidates.values()))
        if len(all_hot) < 10:
            # 补足到至少15个
            for i in range(1, 34):
                if len(all_hot) >= 15:
                    break
                if i not in all_hot:
                    all_hot.append(i)

        # 3. 覆盖设计生成
        result = build_covering_tickets(all_hot[:15], t=4, target_tickets=n)
        if not result.get("ok") or not result.get("tickets"):
            return {"ok": False, "msg": "覆盖设计无解"}

        # 4. 分配蓝球
        bw = _blue_freq_weights()
        tickets = []
        for reds in result["tickets"][:n]:
            tickets.append({"reds": list(reds), "blue": _pick_blue(bw)})

        return {
            "ok": True, "algorithm": "分位策略(位置独立+覆盖)",
            "tickets": tickets, "budget": n,
            "cost_rmb": n * 2,
            "pool_size": len(all_hot),
            "ev_estimate": {"ev_per_draw": -0.3 * n, "cost_per_draw": n * 2},
        }
    except Exception as e:
        return {"ok": False, "msg": f"分位策略失败: {e}"}

# ── 智能覆盖 (组合覆盖设计 + 多样化) ──

def ensemble_draw(n=3, method="ensemble", fdr=True):
    """聚合覆盖出号 — 偏差驱动的动态v + 方法评分 + FDR校正 + 覆盖设计 + Kelly."""
    """聚合覆盖出号 — 方法评分 + FDR校正 + 覆盖设计 + Kelly.

    Args:
        n: 注数
        method: "ensemble"(5方法聚合+FDR) | "mi"(互信息) | "frequency"(纯频率)
        fdr: 是否启用FDR多重比较校正
    """
    from ml.micro_portfolio import generate_tickets_covering
    from ml.ensemble_aggregator import score_all_methods, aggregate_scores, select_hot_numbers
    from ml.kelly import ev_per_ticket, kelly_fraction

    data = db.load_draws()
    if len(data) < 20:
        return {"ok": False, "msg": f"数据不足 ({len(data)}期)"}

    if method == "mi":
        from ml.mi_selector import mi_based_hot_boost
        boosted = mi_based_hot_boost(data[-500:], k=15)
        hot = [num for num, _ in boosted]
    elif method == "frequency":
        from collections import Counter
        freq = Counter()
        for row in data:
            for r in row[1:7]: freq[r] += 1
        try:
            from ml.bias_v_selector import auto_v
            kv = auto_v().v
        except Exception:
            kv = 15
        hot = [n for n, _ in freq.most_common(kv)]
    else:
        method_scores = score_all_methods(data)
        weights = _get_ensemble_weights(data)
        if fdr:
            from ml.fdr import filter_methods_by_fdr
            fdr_result = filter_methods_by_fdr(data, method_scores, weights, q=0.05)
            weights = fdr_result["filtered_weights"]
        final = aggregate_scores(method_scores, weights)
        hot = select_hot_numbers(final, k=15)

    result = generate_tickets_covering(n=n, hot_numbers=hot, t=4)

    if result.get("ok"):
        v = result.get("covering", {}).get("v", 15)
        cov = result.get("covering", {}).get("estimated_coverage_pct", 36)
        ev = ev_per_ticket(n, v, pool_has_all_6_prob=0.00035,
                          coverage_pct=cov, blue_coverage_pct=37.5)
        kelly = kelly_fraction(ev)
        result["kelly"] = {"quarter_kelly_tickets": kelly["quarter_kelly_tickets"],
                           "verdict": kelly["verdict"], "net_ev": ev["net_ev"]}
        result["method"] = method
        result["fdr_enabled"] = method == "ensemble" and fdr

    return result

def _get_ensemble_weights(data):
    """从回测校准获取5方法权重."""
    from ml.ensemble_aggregator import _get_weights as _ew
    return _ew(data, k=15, window=50)

# ── 曾献忠 曾氏模块 (2014) ──

def zeng_dashboard():
    """曾氏模块仪表盘 — 衡值轮盘+四大定律+外部遗传."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'docs', 'research'))
    try:
        from zeng_xianzhong import dashboard as _zeng_dashboard
        result = _zeng_dashboard(db.load_draws())
        result["ok"] = True
        return result
    except Exception as e:
        return {"ok": False, "msg": f"曾氏模块加载失败: {e}",
                "wheel": {}, "linju": [], "prime_run": 0}

def zeng_generate(n=3, odd=3, big=3):
    """曾氏模块出号 — 衡值轮盘+四大定律+内外运动."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'docs', 'research'))
    try:
        from zeng_xianzhong import generate_from_module
        return generate_from_module(db.load_draws(), odd_count=odd, big_count=big, n_tickets=n)
    except Exception as e:
        return {"ok": False, "msg": f"曾氏模块出号失败: {e}",
                "tickets": [], "algorithm": "曾献忠-曾氏模块"}

# ── 自动兑奖 API ──

def claims_summary_api():
    """兑奖统计总览."""
    try:
        from server.auto_claim import get_claims_summary
        summary = get_claims_summary()
        return {"ok": True, **summary}
    except Exception as e:
        return {"ok": False, "msg": str(e)}

def claims_run_api():
    """手动触发自动兑奖."""
    try:
        from server.auto_claim import auto_claim_all
        stats = auto_claim_all()
        return {"ok": True, **stats}
    except Exception as e:
        return {"ok": False, "msg": str(e)}

# ── 调度器 API ──

# ═══════════════════════════════════════════════════════════════════════════
# 策略监控面板 — SPRT + Kelly + EV 三位一体
# ═══════════════════════════════════════════════════════════════════════════

def monitor_api(tickets=3, pool_v=None, pool_blue=6):
    if pool_v is None:
        try:
            from ml.bias_v_selector import auto_v
            pool_v = auto_v().v
        except Exception:
            pool_v = 15
    """综合监控面板 — 实际命中统计 + SPRT检测 + Kelly分配."""
    try:
        from ml.monitor import monitor_panel
        return monitor_panel(tickets=tickets, pool_v=pool_v,
                            pool_blue=pool_blue)
    except Exception as e:
        return {"ok": False, "msg": str(e)}

def schedule_status_api():
    """定时调度器状态."""
    try:
        from server.scheduler import schedule_status
        return {"ok": True, **schedule_status()}
    except Exception as e:
        return {"ok": False, "msg": str(e)}

# ═══════════════════════════════════════════════════════════════════════════
# Mandel 全买覆盖 (Stefan Mandel 14次中奖策略)
# ═══════════════════════════════════════════════════════════════════════════

def mandel_config_api():
    """Mandel 策略配置表 — V=8~15 成本/概率/等待年期对比."""
    from ml.mandel_cover import mandel_summary
    return {"ok": True, "summary": mandel_summary(),
            "breakeven_jackpot": 35442176,
            "note": "期望总成本 = 32×C(33,6) = ¥3,544万 (与V无关). "
                    "小V = 低成本 + 长等待; 大V = 高成本 + 短等待."}

def mandel_preview_api(v=None):
    if v is None:
        try:
            from ml.bias_v_selector import auto_v
            v = max(8, auto_v().v - 3)  # Mandel uses smaller v for full coverage
        except Exception:
            v = 12
    """Mandel 策略预览 — 不生成全部票, 仅返回配置+选号+成本分析."""
    from ml.mandel_cover import MandelConfig, select_v_numbers
    config = MandelConfig(v=v, jackpot_threshold=50_000_000)
    v_numbers = select_v_numbers(db.load_draws(), v, method="laplace")

    return {
        "ok": True,
        "config": config.to_dict(),
        "v_numbers": v_numbers,
        "sample_tickets": [
            {"reds": list(c), "blue": b}
            for c in list(__import__('itertools').combinations(sorted(v_numbers), 6))[:5]
            for b in [1, 2][:1]
        ],
        "warning": (
            f"全买需 {config.total_tickets:,} 注, 成本 ¥{config.cost_per_draw:,}/期. "
            f"期望等 {config.expected_years_to_win:.1f} 年, "
            f"总期望投入 ¥{config.expected_total_cost:,.0f}. "
            "仅供数学模型验证, 不构成购买建议."
        ),
    }

def mandel_jackpot_api():
    """拉取当前双色球头奖金额."""
    from ml.mandel_cover import _fetch_jackpot, MandelConfig
    jackpot = _fetch_jackpot()
    if not jackpot:
        return {"ok": False, "msg": "无法拉取头奖数据 (网络问题或中彩网API变更)"}

    # 算所有V的EV
    evaluations = []
    for v in [8, 10, 12, 14, 15]:
        cfg = MandelConfig(v=v)
        ev_first = cfg.p_all6_reds_in_v * jackpot
        # 低等奖简化估算
        from ml.mandel_cover import _estimate_lower_prizes
        low_ev = _estimate_lower_prizes(list(range(1, v + 1))) * 16
        ev_total = ev_first + low_ev
        evaluations.append({
            "v": v,
            "cost": cfg.cost_per_draw,
            "ev_total": round(ev_total, 2),
            "ev_ratio": round(ev_total / cfg.cost_per_draw, 4) if cfg.cost_per_draw else 0,
            "trigger": ev_total > cfg.cost_per_draw,
        })

    return {
        "ok": True,
        "jackpot": round(jackpot, 0),
        "jackpot_wan": round(jackpot / 10000, 0),
        "evaluations": evaluations,
        "breakeven_jackpot": 35442176,
        "verdict": f"头奖{jackpot/1e4:.0f}万, "
                   f"{'超过' if jackpot >= 35442176 else '低于'}保本线3,544万",
    }

# ═══════════════════════════════════════════════════════════════
# 组合数学武器库 API
# ═══════════════════════════════════════════════════════════════

def wheel_comparison_api():
    """V=8~15 已知最优轮次对比表."""
    from ml.combinatorial_math import la_jolla_comparison_table
    return {"ok": True, "table": la_jolla_comparison_table(),
            "note": "已知最优覆盖注数 (La Jolla + Bluskov 2011)",
            "reference": "ccrwest.org"}

def wheeling_generate_api(v=10):
    """V=8/9/10用已知轮次表, V>10用贪心构造."""
    from ml.combinatorial_math import get_known_wheel, generate_steiner_like, map_wheel_to_numbers
    from ml.ensemble_aggregator import score_all_methods, aggregate_scores, select_hot_numbers, _get_weights as _ew
    from server import db

    if v <= 10:
        result = get_known_wheel(v)
        if result["ok"] and result["tickets"]:
            data = db.load_draws()
            ws = _ew(data, k=15, window=50)
            ms = score_all_methods(data)
            final = aggregate_scores(ms, ws)
            hot = select_hot_numbers(final, k=v)
            mapped = map_wheel_to_numbers(result["tickets"], hot)
            result["mapped_tickets"] = mapped
        return result
    else:
        result = generate_steiner_like(v, max_tickets=30)
        return result

def kelly_api(tickets=3, pool_v=None, coverage_pct=36, blue_pct=37.5):
    if pool_v is None:
        try:
            from ml.bias_v_selector import auto_v
            pool_v = auto_v().v
        except Exception:
            pool_v = 15
    """Kelly 最优投注比例."""
    from ml.kelly import ev_per_ticket, kelly_fraction
    ev = ev_per_ticket(tickets, pool_v,
                       pool_has_all_6_prob=0.00035,  # V=15时6红全在池概率
                       coverage_pct=coverage_pct,
                       blue_coverage_pct=blue_pct)
    kelly = kelly_fraction(ev)
    cost_per_draw = tickets * 2  # ¥2 per ticket
    return {"ok": True, "ev": ev, "kelly": kelly, "cost_per_draw": cost_per_draw}

def sprt_monitor_api():
    """SPRT 序贯概率比检验: 当前策略是否偏离随机?"""
    from ml.sprt import SPRTState, expected_sample_size
    from server import db

    data = db.load_draws()
    # 用最近50期模拟: 假设每期蓝球是否命中
    mock_blue = [i % 4 == 0 for i in range(50)]  # 25%命中率
    result = SPRTState()
    for hit in mock_blue:
        result.update(hit, 0.40, 0.25)  # 声称40% vs 基线25%
    s = result.summary()

    n_expected = expected_sample_size(0.25, 0.40)
    return {"ok": True, "sprt": s, "expected_sample_size": n_expected,
            "reference": "Wald 1945, 'Sequential Tests of Statistical Hypotheses'"}

# ═══════════════════════════════════════════════════════════
# NIST 随机性检验
# ═══════════════════════════════════════════════════════════

def nist_api():
    """NIST SP 800-22 随机性检验: 双色球历史数据是否有结构性偏倚?"""
    from ml.nist_tests import run_nist_suite
    data = db.load_draws()
    report = run_nist_suite(data)
    return report.to_dict()

# ═══════════════════════════════════════════════════════════
# 精确覆盖
# ═══════════════════════════════════════════════════════════

def exact_cover_api(v=15, t=4, n=3):
    """精确覆盖: La Jolla已知最优表 + 整数规划."""
    from ml.exact_cover import exact_cover as ec
    from ml.covering_design import generate_candidate_set
    # 先取v个最热号码
    all_data = db.load_draws()
    total = len(all_data) or 1
    ml_red = {}
    for num in range(1, 34):
        cnt = sum(1 for r in all_data if num in r[1:7])
        ml_red[num] = cnt / total
    hot = generate_candidate_set(ml_red, size=v)
    result = ec(v=v, t=t, n=n, hot_numbers=sorted(hot))
    return {
        "ok": True,
        "v": result.v,
        "t": result.t,
        "n": result.n_tickets,
        "coverage_pct": result.coverage_pct,
        "source": result.source,
        "tickets": result.tickets,
        "hot_numbers": hot,
    }

def exact_cover_compare_api(n=3):
    """比较不同 v 的覆盖效率."""
    from ml.exact_cover import compare_v_configs
    return compare_v_configs(n_tickets=n)

# ═══════════════════════════════════════════════════════════
# 条件熵
# ═══════════════════════════════════════════════════════════

def cond_entropy_api():
    """条件熵分析: 哪些号码历史规律最强?"""
    from ml.cond_entropy import analyze_conditional_entropy
    data = db.load_draws()
    result = analyze_conditional_entropy(data, n_red=15, n_blue=6)
    ok = result.ok
    return {
        "ok": ok,
        "red_top15": result.red_top15,
        "blue_top6": result.blue_top6,
        "red_entropies": {str(k): round(v, 4) for k, v in result.red_entropies.items()},
        "blue_entropies": {str(k): round(v, 4) for k, v in result.blue_entropies.items()},
        "baseline_entropy": result.baseline_entropy,
        "entropy_reduction_pct": result.entropy_reduction_pct,
        "red_clusters": [[int(x) for x in c] for c in result.red_clusters] if result.red_clusters else [],
        "note": "熵降低>5% = 历史结构性规律可被条件化利用",
    }

def cond_entropy_blue_api(n=6):
    """条件熵蓝球候选集."""
    from ml.cond_entropy import entropy_blue_candidates
    data = db.load_draws()
    cands = entropy_blue_candidates(data, n=n)
    return {"ok": True, "candidates": sorted(cands), "mode": "条件熵", "count": len(cands)}

# ═══════════════════════════════════════════════════════════
# 差集构造
# ═══════════════════════════════════════════════════════════

def diffset_table_api():
    """差集覆盖表: 数论构造 vs 贪心比较."""
    from ml.diffset_cover import build_diffset_cover_table
    return build_diffset_cover_table()

# ═══════════════════════════════════════════════════════════
# Bandit 在线策略学习
# ═══════════════════════════════════════════════════════════

def bandit_select_api(n=3):
    """Bandit选择+出号: Thompson抽样选最优策略组合并生成号码."""
    from ml.bandit_strategy import bandit_select_and_generate
    data = db.load_draws()
    tickets, meta = bandit_select_and_generate(data, n=n)
    tickets["bandit_meta"] = meta
    return tickets

def bandit_feedback_api(score=0.0, arm_id=""):
    """Bandit反馈: 用实际开奖结果更新后验."""
    from ml.bandit_strategy import get_bandit
    bandit = get_bandit()
    # 手动设置选中的 arm
    if arm_id and bandit.arms:
        bandit.selected_history.append(arm_id)
    bandit.update(score)
    return {"ok": True, "score": score, "arm_id": arm_id}

def bandit_summary_api():
    """Bandit策略学习摘要."""
    from ml.bandit_strategy import get_bandit
    return get_bandit().summary()

def fdr_filter_api():
    """FDR多重比较校正: 哪些方法真正有信号?"""
    from ml.fdr import filter_methods_by_fdr
    from ml.ensemble_aggregator import METHOD_REGISTRY, _init_registry, score_all_methods
    from ml.ensemble_aggregator import _get_weights as _ew
    from server import db

    data = db.load_draws()
    _init_registry()
    methods = score_all_methods(data)
    weights = _ew(data, k=15, window=50)
    result = filter_methods_by_fdr(data, methods, weights, q=0.05)
    return {"ok": True, **result}

def changepoint_api():
    """变点检测: 开奖机制是否有结构性变化?"""
    from ml.changepoint import online_changepoint, detect_recent_window
    from server import db

    data = db.load_draws()
    result = online_changepoint(data, window=300)
    recent = detect_recent_window(data)
    result["recommended_window"] = recent
    return result

def mi_selector_api():
    """互信息分析: 哪些号码对有非独立共现?"""
    from ml.mi_selector import significant_pairs, mi_based_hot_boost
    from server import db

    data = db.load_draws()[-500:]
    mi = significant_pairs(data, n_bootstrap=100)  # 100 bootstrap: ~0.5s
    boosted = mi_based_hot_boost(data, k=15)
    return {"ok": True, "mi_analysis": mi,
            "mi_hot_numbers": boosted}

# ═══════════════════════════════════════════════════════════
# 多期联合覆盖
# ═══════════════════════════════════════════════════════════

def multi_period_stats_api(t=4):
    """多期覆盖统计."""
    from ml.multi_period_cover import coverage_stats
    return {"ok": True, **coverage_stats(t=t)}

def multi_period_clear_api(t=4):
    """清空多期覆盖历史."""
    from ml.multi_period_cover import clear_coverage
    clear_coverage(t=t)
    return {"ok": True, "msg": f"t={t} 覆盖历史已清空"}
