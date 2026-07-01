"""信号融合 — 双算法加权组合 + walk-forward 回测

仅用回测验证的两个有效算法:
  A. gap_analysis    — 间隔/存活分析 (Weibull MLE, window=50, lift +1.9%)
  B. position_model  — 位置条件概率 (window=100, lift +1.3%)

融合策略: 加权平均 (gap 0.6, position 0.4).
蓝球: 间隔分析 (Weibull MLE, window=50).
"""
import math
import random


# ═══ 红球信号融合 ═══

def collect_all_signals(data, window=200, active=None):
    """运行 gap + position, 返回融合权重 [0.0]*34 (1-indexed)."""
    diag = {}
    weights_pool = {}

    # ── A: gap_analysis ──
    try:
        from ml.gap_analysis import compute_gap_weights
        gap_w, gap_d = compute_gap_weights(data, window=min(window, 50))
        weights_pool["gap_analysis"] = gap_w
        diag["gap_analysis"] = {
            "hot": gap_d.get("hot", [])[:8],
            "n_hot": gap_d.get("n_hot", 0),
        }
    except Exception:
        weights_pool["gap_analysis"] = [1.0] * 34
        diag["gap_analysis"] = {"error": "failed"}

    # ── B: position_model ──
    try:
        from ml.position_model import compute_position_weights
        pos_probs, pos_d = compute_position_weights(data, window=min(window, 100))
        pos_w = [0.0] * 34
        for num in range(1, 34):
            pos_w[num] = sum(pos_probs[p][num] for p in range(1, 7)) / 6.0
        mean_pos = sum(pos_w[1:]) / 33
        if mean_pos > 0:
            for num in range(1, 34):
                pos_w[num] = pos_w[num] / mean_pos
        weights_pool["position"] = pos_w
        diag["position"] = {
            "hot_by_pos": pos_d.get("hot_by_pos", {}),
            "chi2_by_pos": {str(k): v for k, v in pos_d.get("chi2_by_pos", {}).items()},
        }
    except Exception:
        weights_pool["position"] = [1.0] * 34
        diag["position"] = {"error": "failed"}

    # ── 归一化 → 等权融合 ──
    def _normalize(w):
        vals = [w[n] for n in range(1, 34)]
        mean_val = sum(vals) / 33
        if mean_val <= 0:
            return w
        scaled = [0.0] * 34
        for n in range(1, 34):
            scaled[n] = max(0.5, min(2.0, w[n] / mean_val))
        return scaled

    for name in weights_pool:
        weights_pool[name] = _normalize(weights_pool[name])

    fused = [1.0] * 34
    n_active = len(weights_pool)
    if n_active == 0:
        return fused, diag

    for num in range(1, 34):
        fused[num] = sum(weights_pool[name][num] for name in weights_pool) / n_active

    diag["n_active"] = n_active
    diag["active_list"] = list(weights_pool.keys())

    return fused, diag


# ═══ 蓝球权重 (简单频率) ═══

def collect_blue_signals(data, window=None, active=None):
    """蓝球: 间隔分析 + 频率 融合.

    优先使用 gap_analysis 蓝球 (Weibull MLE),
    降级时使用频率加权.
    """
    diag = {}
    try:
        from ml.gap_analysis import compute_blue_gap_weights
        weights, gap_d = compute_blue_gap_weights(data, window=min(window or 50, 50))
        diag["algorithm"] = "间隔分析蓝球"
        diag["n_hot"] = gap_d.get("n_hot", 0)
        diag["hot"] = gap_d.get("hot", [])[:6]
        return weights, diag
    except Exception:
        pass

    # 降级: 频率加权
    if not data:
        return [1.0] * 17, diag
    recent = data[-(window or 100):]
    blue_counts = [0] * 17
    for row in recent:
        blue_counts[row[7]] += 1
    total = sum(blue_counts[1:])
    expected = total / 16.0 if total > 0 else 1.0

    weights = [0.0] * 17
    for b in range(1, 17):
        ratio = blue_counts[b] / expected if expected > 0 else 1.0
        weights[b] = max(0.5, min(2.0, ratio))

    diag["algorithm"] = "频率蓝球(降级)"
    diag["n_hot"] = sum(1 for b in range(1, 17) if weights[b] > 1.05)
    diag["hot"] = [(b, round(weights[b], 3)) for b in range(1, 17) if weights[b] > 1.05][:6]
    return weights, diag


# ═══ Walk-forward 回测 ═══

def backtest_single_algorithm(data, algo_fn, window=200, step=10):
    """Walk-forward 回测: 用前 window 期训练, 预测下 step 期.

    algo_fn(data_window) → weights [0.0]*34
    对每期预测: 用 weights 做 weighted 采样, 统计命中。
    """
    if len(data) < window + step:
        return None, "数据不足"

    total_tests = 0
    total_red_hits = 0
    best_hits = 0

    for start in range(0, len(data) - window - 1, step):
        train = data[start:start + window]
        test = data[start + window:start + window + step]

        try:
            weights = algo_fn(train)
            if weights is None:
                continue
        except Exception:
            continue

        for test_row in test:
            actual_reds = set(test_row[1:7])

            from ml.micro_portfolio import _state
            if _state.valid_reds is None:
                from ml.micro_portfolio import _build_pool
                _build_pool()
            if _state.valid_reds is None:
                continue

            n_combos = len(_state.valid_reds) // 6
            if n_combos == 0:
                continue

            best_of = min(20, n_combos)
            cands = random.sample(range(n_combos), best_of)
            idx = max(cands, key=lambda i: sum(
                weights[n] if n < 34 else 1.0
                for n in _state.valid_reds[i * 6:i * 6 + 6]
            ))
            reds = set(_state.valid_reds[idx * 6:idx * 6 + 6])
            rh = len(reds & actual_reds)
            total_red_hits += rh
            total_tests += 1
            best_hits = max(best_hits, rh)

    if total_tests == 0:
        return None, "无有效测试"

    avg_red = total_red_hits / total_tests
    baseline = 6 * 6 / 33  # ≈ 1.09
    return {
        "tests": total_tests,
        "avg_red": round(avg_red, 3),
        "best": best_hits,
        "baseline": round(baseline, 3),
        "lift": round(avg_red / baseline, 3),
    }, None


def run_all_backtests(data):
    """Walk-forward 回测: gap + position."""

    def algo_gap(train_data):
        from ml.gap_analysis import compute_gap_weights
        w, _ = compute_gap_weights(train_data, window=min(len(train_data), 50))
        return w

    def algo_position(train_data):
        from ml.position_model import compute_position_weights
        pos_probs, _ = compute_position_weights(train_data, window=min(len(train_data), 100))
        pos_w = [0.0] * 34
        for num in range(1, 34):
            pos_w[num] = sum(pos_probs[p][num] for p in range(1, 7)) / 6.0
        mean_pos = sum(pos_w[1:]) / 33
        if mean_pos > 0:
            for num in range(1, 34):
                pos_w[num] = pos_w[num] / mean_pos
        return pos_w

    results = {}
    for name, fn in [
        ("gap_analysis", algo_gap),
        ("position", algo_position),
    ]:
        result, err = backtest_single_algorithm(data, fn)
        if err:
            results[name] = {"error": err}
        else:
            results[name] = result

    return results
