"""ML门面 — 微投资组合 + Mandel覆盖 + 一等奖EV评估

已删除:
  - XGBoost/LSTM/高级统计/Sirius/Thompson/GPT 桥接函数
  - OOT 验证 / 高级模型回测
  - luck_mode='blend' (运气规则, 已移除 — 与贪心冲突, 效果不显著)
  - bundle_a/bundle_b (捆绑投注, 已移除 — Lift≠未来, 操作链太长)

归档备份: docs/deprecated-backend-backup/ml_bridge.py
"""
from server import db
from functools import wraps


def _with_data(fn):
    """Decorator: auto-loads draw data and passes as first argument.
    Usage: @_with_data \n    def foo(data, n=3): ..."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        data = db.load_draws()
        return fn(data, *args, **kwargs)
    return wrapper


# ============ 覆盖设计 (Mandel — 纯频率) ============

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
                    param_filter=False, pattern_rules=False,
                    liu_blue=False, cailele_blue=False, gongyi_blue=False, wuming_blue=False,
                    author_mode=None, filter_config=None,
                    # 向后兼容的独立过滤器参数
                    color_filter=False, block9_filter=False,
                    spread_filter=False, ac_filter=False,
                    peng_channel_filter=False, gap_filter=False,
                    omission_filter=False, coincidence_filter=False,
                    wuming_clockwise=False, wuming_bsd=False):
    """从号码池不放回随机采样 n 注。filter_config 优先于独立参数。"""
    from ml.micro_portfolio import generate_tickets, FilterConfig
    if filter_config is None:
        filter_config = FilterConfig(
            color_filter=color_filter, block9_filter=block9_filter,
            spread_filter=spread_filter, ac_filter=ac_filter,
            peng_channel_filter=peng_channel_filter, gap_filter=gap_filter,
            omission_filter=omission_filter, coincidence_filter=coincidence_filter,
            wuming_clockwise=wuming_clockwise, wuming_bsd=wuming_bsd)
    return generate_tickets(n=n, soft=soft, luck_mode=luck_mode,
                            max_overlap=max_overlap, diversity_mode=diversity_mode,
                            five_period=five_period, backtest_rank=backtest_rank,
                            param_filter=param_filter, pattern_rules=pattern_rules,
                            liu_blue=liu_blue, cailele_blue=cailele_blue,
                            gongyi_blue=gongyi_blue, wuming_blue=wuming_blue,
                            author_mode=author_mode,
                            filter_config=filter_config)


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


# ── 已归档的API (模块迁移至 ml/_deprecated/) ──

def kelly_allocate(red_lift=1.0, blue_lift=1.0, budget=100.0, tau=0.25):
    """Kelly最优注数 — 已归档."""
    return {"ok": False, "msg": "Kelly模块已归档至 ml/_deprecated/kelly_allocator.py — 负EV场景下最优投注=0"}

def kelly_advanced(backtest_red_hits=None, backtest_blue_hits=None, budget=100.0, tau=0.25):
    """基于回测数据的Kelly建议 — 已归档."""
    return {"ok": False, "msg": "Kelly模块已归档"}

def particle_filter_state(window=200):
    """粒子滤波 — 已归档."""
    return {"ok": False, "msg": "粒子滤波已归档至 ml/_deprecated/particle_filter.py — OOS无显著提升"}

def strategy_bandit_state(widget_bandit=True):
    """策略Bandit — 已归档."""
    return {"ok": False, "msg": "策略Bandit已归档至 ml/_deprecated/strategy_bandit.py — 无独立验证"}

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

@_with_data
def generate_twelve_value(data, n=3, dan=None):
    """围号选号法 (2017版): 18种低胜率杀号→~12个红球候选+位置策略。

    GET /api/zhang/twelve-value?n=3&dan=12,5
    """
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


def blue_pick(liu_blue=False, cailele_blue=False, gongyi_blue=False, wuming_blue=False,
              wuming_clockwise=False, wuming_bsd=False, xia_blue=False,
              five_period=False, pattern_rules=False):
    """蓝球独立出号: 策略候选集取交集, 交集为空时退到并集.

    GET /api/blue/pick?liu_blue=1&cailele_blue=1
    """
    from ml.micro_portfolio import (
        _liu_dajun_candidates, _cailele_candidates, _gongyi_candidates,
        _wuming_candidates, _wuming_clockwise_candidates, _wuming_bsd_candidates,
        _five_period_candidates, _pattern_blue_candidates, _xia_sub4_add4_blue,
    )
    active = []
    if liu_blue: active.append(_liu_dajun_candidates)
    if cailele_blue: active.append(_cailele_candidates)
    if gongyi_blue: active.append(_gongyi_candidates)
    if wuming_blue: active.append(_wuming_candidates)
    if wuming_clockwise: active.append(_wuming_clockwise_candidates)
    if wuming_bsd: active.append(_wuming_bsd_candidates)
    if xia_blue: active.append(lambda: set(_xia_sub4_add4_blue().get("candidates", [])))
    if five_period: active.append(_five_period_candidates)
    if pattern_rules: active.append(_pattern_blue_candidates)

    if not active:
        return {"ok": True, "candidates": [], "mode": "none", "count": 0}

    inter = set(range(1, 17))
    union = set()
    for fn in active:
        cands = fn()
        if cands:
            inter &= cands
            union |= cands
    # 优先取交集, 为空则退到并集 (至少一票)
    result = inter if inter else union
    return {"ok": True, "candidates": sorted(result) if result else [],
            "mode": "intersection" if inter else "union",
            "count": len(result) if result else 0}
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

def red_pick(n=3, soft=False, param_filter=False, color_filter=False, block9_filter=False,
             spread_filter=False, ac_filter=False, peng_channel_filter=False, gap_filter=False,
             omission_filter=False, coincidence_filter=False,
             diversity_mode=None, max_overlap=None):
    """红球独立出号: 返回池子状态 + 红球号码.

    GET /api/red/pick?n=3&color_filter=1&block9_filter=1&spread_filter=1&ac_filter=1&peng_channel=1&gap_filter=1
    """
    from ml.micro_portfolio import generate_tickets
    result = generate_tickets(n=n, soft=soft, param_filter=param_filter,
                              color_filter=color_filter, block9_filter=block9_filter,
                              spread_filter=spread_filter, ac_filter=ac_filter,
                              peng_channel_filter=peng_channel_filter,
                              gap_filter=gap_filter,
                              omission_filter=omission_filter,
                              coincidence_filter=coincidence_filter,
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
    """B-L融合出号 — 多方法观点贝叶斯融合."""
    from ml.black_litterman import bl_tickets
    return bl_tickets(k=15, t=4, n=n)


# ── 分位策略 ──

def position_draw(n=3):
    """分位策略出号 — 每位置独立最优方法选号."""
    from ml.position_engine import position_tickets
    return position_tickets(n=n, k=15)


# ── 智能覆盖 (组合覆盖设计 + 多样化) ──

def ensemble_draw(n=3):
    """智能覆盖出号 — 覆盖设计 + 贪心多样化."""
    from ml.micro_portfolio import generate_tickets_covering
    from ml.covering_design import generate_candidate_set
    data = db.load_draws()
    total = len(data) or 1
    ml_red = {}
    for num in range(1, 34):
        cnt = sum(1 for r in data if num in r[1:7])
        ml_red[num] = cnt / total
    hot = generate_candidate_set(ml_red, size=15)
    return generate_tickets_covering(n=n, hot_numbers=hot, t=4)

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


def mandel_preview_api(v=12):
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
