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

def micro_3_tickets(n=3, soft=False, luck_mode='off'):
    """从号码池不放回随机采样 n 注。soft=True 加位置软过滤。
    luck_mode: 'off' (无), 'blend' (池采样+偏置), 'pure' (位置运气)."""
    from ml.micro_portfolio import generate_tickets
    return generate_tickets(n=n, soft=soft, luck_mode=luck_mode)


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
