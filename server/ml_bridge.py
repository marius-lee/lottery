"""ML门面 — 微投资组合 + Mandel覆盖 + 一等奖EV评估

已删除（对应模块已归档至 ml/_deprecated/）:
  - XGBoost/LSTM/高级统计/Sirius/Thompson/GPT 桥接函数
  - OOT 验证 / 高级模型回测

归档备份: docs/deprecated-backend-backup/ml_bridge.py
"""
from server import db


# ============ 覆盖设计 (Mandel — 纯频率) ============

def generate_covering(v=15, t=4):
    """生成 Stefan Mandel 覆盖设计票集。

    GET /api/covering/generate?v=15&t=4
    — 选 top-v 热号，生成 C(v,6,t) 覆盖票集
    """
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

def micro_3_tickets(n=3, soft=False, luck_mode='off', max_overlap=None, diversity_mode=None, five_period=False, backtest_rank=False, param_filter=False, bundle_a=None, bundle_b=None):
    """从号码池不放回随机采样 n 注。soft=True 加位置软过滤。
    luck_mode: 'off' (无), 'blend' (池采样+偏置), 'pure' (位置运气).
    max_overlap: 注间最大共享红球数, None=不限制.
    diversity_mode: None=随机采样, 'greedy'=贪心max-min Jaccard.
    five_period: 五期断蓝法加权 (刘大军, 2011).
    backtest_rank: 回测排名选注 (蒋加林, 2001).
    param_filter: 奇偶比/和值过滤 (蒋加林, 2001).
    bundle_a/bundle_b: 捆绑投注对 (蒋加林, 2001 第三绝招)."""
    from ml.micro_portfolio import generate_tickets
    return generate_tickets(n=n, soft=soft, luck_mode=luck_mode,
                            max_overlap=max_overlap, diversity_mode=diversity_mode,
                            five_period=five_period, backtest_rank=backtest_rank,
                            param_filter=param_filter, bundle_a=bundle_a, bundle_b=bundle_b)


def get_rule_status():
    """返回硬过滤规则状态。"""
    from ml.micro_portfolio import rule_status
    return rule_status()


# ============ 一等奖评估 + EV计算 ============

def evaluate_prizes(tickets, backtest_red_hits=None, backtest_blue_hits=None):
    """评估策略票集的中奖概率和期望收益 vs 随机基线。

    GET /api/evaluate/prizes?n=3
    """
    from ml.prize_evaluator import evaluate_strategy_tickets
    from ml.ssq_constants import RED_EXPECTED_HITS, BLUE_HIT_PROB
    if backtest_red_hits is None:
        backtest_red_hits = [RED_EXPECTED_HITS]
    if backtest_blue_hits is None:
        backtest_blue_hits = [BLUE_HIT_PROB]
    return evaluate_strategy_tickets(tickets, backtest_red_hits, backtest_blue_hits)


# ============ 覆盖设计多样化 (Tier 3) ============

def generate_covering_diverse(v=15, t=4, n=6, max_overlap=None, five_period=False):
    """覆盖设计 + 蓝球分配, 一步生成完整票集。

    GET /api/covering-diverse?v=15&t=4&n=6&five_period=1
    """
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
