"""ML门面 (Facade Pattern) — 封装XGBoost+LSTM，提供统一预测接口"""
import json
from server import db
from ml.ssq_constants import RED_EXPECTED_HITS, BLUE_HIT_PROB, WEIGHT_MIN, WEIGHT_MAX

RED_BASELINE = RED_EXPECTED_HITS  # 1.0909

_xgb_predictor = None
_lstm_predictor = None


def get_xgb():
    global _xgb_predictor
    if _xgb_predictor is None:
        try:
            from ml.xgb_predictor import XGBPredictor
            _xgb_predictor = XGBPredictor()
            _xgb_predictor.load()
        except ImportError:
            _xgb_predictor = None
    return _xgb_predictor


def get_lstm():
    global _lstm_predictor
    if _lstm_predictor is None:
        try:
            from ml.lstm_predictor import LSTMPredictor
            _lstm_predictor = LSTMPredictor()
            _lstm_predictor.load()
        except ImportError:
            _lstm_predictor = _MLPlaceholder()
    return _lstm_predictor


class _MLPlaceholder:
    """归档模块的占位对象 — 模拟 is_trained=False 防止调用方崩溃"""
    is_trained = False
    def validate_oot(self, *a, **kw):
        return {"ok": False, "msg": "模块已归档"}
    def predict(self, *a, **kw):
        return None
    def load(self, *a, **kw):
        pass


def ml_status():
    status = {"xgb_trained": False, "lstm_trained": False}
    try:
        xgb = get_xgb()
        status["xgb_trained"] = xgb.is_trained()
        status["xgb_models"] = len(xgb.models) if hasattr(xgb, 'models') else 0
    except Exception:
        pass
    try:
        lstm = get_lstm()
        status["lstm_trained"] = lstm.is_trained
    except Exception:
        pass
    return status


def _normalize(probs):
    vals = list(probs.values())
    mn, mx = min(vals), max(vals)
    if mx == mn:
        return probs
    return {k: (v - mn) / (mx - mn) for k, v in probs.items()}


def predict_xgb(all_data):
    xgb = get_xgb()
    if not xgb.is_trained():
        return None
    return xgb.predict(all_data)


def predict_lstm(all_data):
    lstm = get_lstm()
    if not lstm.is_trained:
        return None
    return lstm.predict(all_data)


def predict_ensemble(all_data):
    """XGBoost + LSTM 加权集成预测"""
    xgb_pred = predict_xgb(all_data)
    lstm_pred = predict_lstm(all_data)

    if not xgb_pred and not lstm_pred:
        return None

    red_probs = {str(n): 0.0 for n in range(1, 34)}
    blue_probs = {str(n): 0.0 for n in range(1, 17)}
    total_weight = 0.0

    for pred, w in [(xgb_pred, 0.5), (lstm_pred, 0.5)]:
        if pred is None:
            continue
        total_weight += w
        nr = _normalize({k: float(v) for k, v in pred.get("red_probs", {}).items()})
        nb = _normalize({k: float(v) for k, v in pred.get("blue_probs", {}).items()})
        for k, v in nr.items():
            red_probs[k] += v * w
        for k, v in nb.items():
            blue_probs[k] += v * w

    if total_weight > 0:
        for k in red_probs:
            red_probs[k] /= total_weight
        for k in blue_probs:
            blue_probs[k] /= total_weight

    top6 = sorted(red_probs, key=lambda x: red_probs[x], reverse=True)[:6]
    top_blue = max(blue_probs, key=lambda x: blue_probs[x])

    return {
        "reds": sorted(int(x) for x in top6),
        "blue": int(top_blue),
        "red_probs": red_probs,
        "blue_probs": blue_probs,
    }


def train_xgb():
    all_data = db.load_draws()
    if not all_data:
        return False, "无数据，请先拉取"
    try:
        from ml.xgb_predictor import train_xgb_models
        n = train_xgb_models(all_data, verbose=False)
        return True, f"XGBoost {n}/49 模型训练完成"
    except ImportError:
        return False, "XGBoost 模块已归档，不可用"


def train_lstm():
    all_data = db.load_draws()
    if not all_data:
        return False, "无数据"
    try:
        from ml.lstm_predictor import LSTMPredictor
        lstm = LSTMPredictor()
        ok = lstm.train(all_data, epochs=60, batch_size=32, verbose=False)
        if ok:
            return True, "LSTM 训练完成"
        return False, "LSTM 训练失败，数据不足"
    except ImportError:
        return False, "LSTM 模块已归档，不可用"


def backtest_ml(all_data, window_size, test_count):
    """ML回测：滑动窗口评估预测准确率"""
    xgb = get_xgb()
    if xgb is None or not xgb.is_trained():
        return None

    red_hits_list = []
    blue_hits_count = 0
    total_tests = 0
    max_hit_val = 0

    test_start = max(window_size, 30)
    actual_count = min(test_count, len(all_data) - test_start - 1)

    for t in range(actual_count):
        cutoff = len(all_data) - window_size - t - 1
        if cutoff < 10:
            break
        window_data = all_data[:cutoff]
        actual = all_data[cutoff]
        try:
            pred = xgb.predict(window_data)
            actual_reds = set(actual[1:7])
            hits = len(actual_reds & set(pred["reds"]))
            red_hits_list.append(hits)
            if pred["blue"] == actual[7]:
                blue_hits_count += 1
            total_tests += 1
            max_hit_val = max(max_hit_val, hits)
        except Exception:
            continue

    avg_red = sum(red_hits_list) / total_tests if total_tests > 0 else 0
    blue_rate = blue_hits_count / total_tests if total_tests > 0 else 0
    weight = round(max(0.3, min(2.0, avg_red / 1.5)), 1)

    return {
        "avg_red_hit": round(avg_red, 2),
        "blue_hit_rate": round(blue_rate * 100, 1),
        "max_hit": max_hit_val,
        "test_count": total_tests,
        "weight": weight,
    }


def get_ml_probabilities(all_data):
    """获取ML概率：返回 (ml_red, ml_blue) 两份字典"""
    ml_red = {}
    ml_blue = {}
    try:
        xgb = get_xgb()
        if xgb is not None and xgb.is_trained():
            pred = xgb.predict(all_data)
            for k, v in pred["red_probs"].items():
                ml_red[int(k)] = float(v)
            for k, v in pred["blue_probs"].items():
                ml_blue[int(k)] = float(v)
    except Exception:
        pass

    try:
        lstm = get_lstm()
        if lstm is not None and lstm.is_trained:
            pred2 = lstm.predict(all_data)
            if pred2:
                for k, v in pred2["red_probs"].items():
                    ml_red[int(k)] = ml_red.get(int(k), 0) + float(v)
                for k, v in pred2["blue_probs"].items():
                    ml_blue[int(k)] = ml_blue.get(int(k), 0) + float(v)
                for k in ml_red:
                    ml_red[k] /= 2.0
                for k in ml_blue:
                    ml_blue[k] /= 2.0
    except Exception:
        pass

    return ml_red, ml_blue


# ============ 高级统计模型桥接 (6种新算法) ============

_advanced_model_cache = {}


def _get_advanced_model(model_name):
    """延迟加载高级模型实例"""
    if model_name not in _advanced_model_cache:
        try:
            from ml.advanced import CopulaModel, BayesianModel, EntropyModel, PolyaUrnModel, EVTModel, RMTModel
            class_map = {
                "copula": CopulaModel, "bayesian": BayesianModel,
                "entropy": EntropyModel, "polya": PolyaUrnModel,
                "evt": EVTModel, "rmt": RMTModel,
            }
            _advanced_model_cache[model_name] = class_map[model_name]()
        except ImportError:
            _advanced_model_cache[model_name] = None
    return _advanced_model_cache[model_name]


def predict_advanced(data, model_name):
    """调用指定高级模型预测"""
    model = _get_advanced_model(model_name)
    if model is None:
        return {"ok": False, "msg": "高级模型模块已归档"}
    return model.predict(data)


def predict_all_advanced(data):
    """运行全部6个高级模型"""
    try:
        from ml.advanced import run_all_advanced
        return run_all_advanced(data)
    except ImportError:
        return {"error": "高级模型模块已归档"}


# ============ OOT 验证 ============

def validate_oot(holdout=50):
    """Out-of-Time 验证: XGBoost + LSTM 各做 OOT 评估，防止过拟合假象。

    返回 in-sample vs OOT 对比，判断模型是否真正超越随机基线。
    """
    all_data = db.load_draws()
    if not all_data or len(all_data) < holdout + 50:
        return {"ok": False, "msg": f"数据不足，当前{len(all_data)}期，需≥{holdout + 50}"}

    results = {"holdout": holdout, "total_draws": len(all_data)}

    # XGBoost OOT
    try:
        from ml.xgb_predictor import XGBPredictor
        xgb = XGBPredictor()
        xgb_result = xgb.validate_oot(all_data, holdout=holdout)
        results["xgb"] = xgb_result
    except Exception as e:
        results["xgb"] = {"ok": False, "msg": str(e)}

    # LSTM OOT
    try:
        from ml.lstm_predictor import LSTMPredictor
        lstm = LSTMPredictor()
        lstm_result = lstm.validate_oot(all_data, holdout=holdout)
        results["lstm"] = lstm_result
    except Exception as e:
        results["lstm"] = {"ok": False, "msg": str(e)}

    return results


# ============ 覆盖设计 ============

def generate_covering(v=15, t=4):
    """生成 Stefan Mandel 覆盖设计票集。

    GET /api/covering/generate?v=15&t=4
    — 选 top-v 热号，生成 C(v,6,t) 覆盖票集
    """
    all_data = db.load_draws()
    ml_red, ml_blue = get_ml_probabilities(all_data)

    # Fallback: 用频率概率
    if not ml_red:
        total = len(all_data) or 1
        for n in range(1, 34):
            cnt = sum(1 for r in all_data if n in r[1:7])
            ml_red[n] = cnt / total

    if not ml_blue:
        total = len(all_data) or 1
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


# ============ Sirius Code 投资组合优化 ============

def sirius_portfolio(budget=50):
    """Sirius Code 二级奖投资组合优化。

    GET /api/sirius/portfolio?budget=50
    """
    all_data = db.load_draws()
    ml_red, ml_blue = get_ml_probabilities(all_data)

    if not ml_red:
        total = len(all_data) or 1
        for n in range(1, 34):
            cnt = sum(1 for r in all_data if n in r[1:7])
            ml_red[n] = cnt / total
    if not ml_blue:
        total = len(all_data) or 1
        for n in range(1, 17):
            cnt = sum(1 for r in all_data if r[7] == n)
            ml_blue[n] = cnt / total

    try:
        from ml.sirius_optimizer import optimize_portfolio
        return optimize_portfolio(ml_red, ml_blue, budget_tickets=budget)
    except ImportError:
        return {"ok": False, "msg": "Sirius 模块已归档"}


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


# ============ Thompson Sampling ============

_thompson = None

def get_thompson():
    global _thompson
    if _thompson is None:
        try:
            from ml.thompson_sampler import ThompsonSampler
            _thompson = ThompsonSampler()
            if not _thompson.load():
                all_data = db.load_draws()
                if all_data:
                    _thompson.update(all_data)
                    _thompson.save()
        except ImportError:
            _thompson = None
    return _thompson

def thompson_predict(n=3):
    ts = get_thompson()
    if ts is None:
        return {"ok": False, "msg": "Thompson 模块已归档"}
    tickets = ts.predict(n_tickets=n)
    stats = ts.get_posterior_stats()
    return {"ok": True, "tickets": tickets, "posterior_stats": stats}

def thompson_evaluate(holdout=50, n_tickets=3):
    try:
        from ml.thompson_sampler import ThompsonSampler
        all_data = db.load_draws()
        ts = ThompsonSampler()
        return ts.evaluate(all_data, holdout=holdout, n_tickets=n_tickets)
    except ImportError:
        return {"ok": False, "msg": "Thompson 模块已归档"}


# ============ GPT Transformer ============

_gpt = None

def get_gpt():
    global _gpt
    if _gpt is None:
        try:
            from ml.transformer_predictor import GPTLotteryPredictor
            _gpt = GPTLotteryPredictor()
            _gpt.load()
        except ImportError:
            _gpt = None
    return _gpt

def train_gpt():
    try:
        from ml.transformer_predictor import GPTLotteryPredictor
        all_data = db.load_draws()
        gpt = GPTLotteryPredictor()
        ok = gpt.train(all_data, epochs=30, block_size=256, verbose=True)
        global _gpt
        _gpt = gpt
        return {"ok": ok, "msg": "GPT Transformer training completed" if ok else "Failed"}
    except ImportError:
        return {"ok": False, "msg": "GPT 模块已归档"}

def predict_gpt():
    gpt = get_gpt()
    if gpt is None:
        return {"ok": False, "msg": "GPT 模块已归档"}
    if not gpt.is_trained:
        return {"ok": False, "msg": "GPT model not trained. Call /api/ml/train/gpt first"}
    all_data = db.load_draws()
    result = gpt.predict(all_data)
    return {"ok": True, "model": "gpt", **result}

def validate_gpt(holdout=50):
    try:
        from ml.transformer_predictor import GPTLotteryPredictor
        all_data = db.load_draws()
        gpt = GPTLotteryPredictor()
        return gpt.validate_oot(all_data, holdout=holdout)
    except ImportError:
        return {"ok": False, "msg": "GPT 模块已归档"}


# ============ 一等奖评估 + EV计算 ============

def evaluate_prizes(tickets, backtest_red_hits=None, backtest_blue_hits=None):
    """评估策略票集的中奖概率和期望收益 vs 随机基线。

    GET /api/evaluate/prizes?n=3
    """
    from ml.prize_evaluator import evaluate_strategy_tickets
    if backtest_red_hits is None:
        backtest_red_hits = [RED_EXPECTED_HITS]
    if backtest_blue_hits is None:
        backtest_blue_hits = [BLUE_HIT_PROB]
    return evaluate_strategy_tickets(tickets, backtest_red_hits, backtest_blue_hits)


# ============ 高级模型回测 ============

def backtest_advanced(all_data, window_size=30, test_count=50):
    """回测 6 个高级统计模型 + ML集成。

    返回每个模型的 avg_red_hit, blue_hit_rate, weight.
    """
    try:
        from ml.advanced import CopulaModel, BayesianModel, EntropyModel, PolyaUrnModel, EVTModel, RMTModel
    except ImportError:
        return {"error": "高级模型模块已归档"}

    models = [
        ("Copula", CopulaModel),
        ("贝叶斯", BayesianModel),
        ("熵值", EntropyModel),
        ("Pólya", PolyaUrnModel),
        ("EVT", EVTModel),
        ("RMT", RMTModel),
    ]

    results = {}
    test_start = max(window_size, 30)
    actual_count = min(test_count, len(all_data) - test_start - 1)

    for name, ModelClass in models:
        model = ModelClass()
        red_hits_list = []
        blue_hits_count = 0
        total_tests = 0
        max_hit_val = 0

        for t in range(actual_count):
            cutoff = len(all_data) - window_size - t - 1
            if cutoff < 10:
                break
            window_data = all_data[:cutoff]
            actual = all_data[cutoff]
            try:
                pred = model.predict(window_data)
                actual_reds = set(actual[1:7])
                hits = len(actual_reds & set(pred.get("reds", [])))
                red_hits_list.append(hits)
                if pred.get("blue") == actual[7]:
                    blue_hits_count += 1
                total_tests += 1
                max_hit_val = max(max_hit_val, hits)
            except Exception:
                continue

        if total_tests > 0:
            avg_red = sum(red_hits_list) / total_tests
            blue_rate = blue_hits_count / total_tests
            weight = round(max(WEIGHT_MIN, min(WEIGHT_MAX, avg_red / RED_BASELINE)), 2)
            results[name] = {
                "avg_red_hit": round(avg_red, 2),
                "blue_hit_rate": round(blue_rate * 100, 1),
                "max_hit": max_hit_val,
                "test_count": total_tests,
                "weight": weight,
            }
        else:
            results[name] = {"error": "no data"}

    return results
