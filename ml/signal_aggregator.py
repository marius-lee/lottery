"""多算法信号融合 — 四个方向的信号加权组合 + walk-forward 回测

四个方向:
  A. recent_bias (已有)     — 偏热号码加权
  B. position_model         — 位置条件概率
  C. cooccurrence           — 共现图社区
  D. rmt_spectrum           — RMT 谱分析
  E. transfer_entropy       — 转移熵

融合策略: 默认等权平均各算法的号码权重, 后续可根据回测结果调权.
"""
import math
import random
from collections import Counter


# ═══ 信号融合 ═══

def collect_all_signals(data, window=200, active=None):
    """运行算法, 返回融合权重 [0.0]*34 (1-indexed).

    active: 启用的算法列表. None/"all"=启用全部五个.
    """
    if active is None or active == 'all':
        active = ['recent_bias', 'position', 'cooccurrence', 'rmt', 'transfer_entropy', 'gap', 'modular', 'markov']
    elif isinstance(active, str) and active == 'all':
        active = ['recent_bias', 'position', 'cooccurrence', 'rmt', 'transfer_entropy', 'gap', 'modular', 'markov']

    diag = {}
    weights_pool = {}

    # ── A: recent_bias ──
    if 'recent_bias' in active:
        try:
            from ml.recent_bias import compute_recent_bias_weights
            rb_w, rb_d = compute_recent_bias_weights(data, window=window)
            weights_pool["recent_bias"] = rb_w
            diag["recent_bias"] = {
                "hot": [(n, round(rb_w[n], 3)) for n in range(1, 34) if rb_w[n] > 1.05][:8],
                "n_hot": sum(1 for n in range(1, 34) if rb_w[n] > 1.05),
            }
        except Exception:
            weights_pool["recent_bias"] = [1.0] * 34
            diag["recent_bias"] = {"error": "failed"}
    else:
        diag["recent_bias"] = {"inactive": True}

    # ── B: position_model ──
    if 'position' in active:
        try:
            from ml.position_model import compute_position_weights
            pos_probs, pos_d = compute_position_weights(data, window=min(window, 200))
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
    else:
        diag["position"] = {"inactive": True}

    # ── C: cooccurrence ──
    if 'cooccurrence' in active:
        try:
            from ml.cooccurrence import compute_cooccurrence
            edges, communities, cooc_d = compute_cooccurrence(data, window=min(window, 300))
            cooc_w = [1.0] * 34
            if communities:
                comm_sizes = Counter(communities.values())
                for num, cid in communities.items():
                    size = comm_sizes.get(cid, 1)
                    cooc_w[num] = 1.0 + (size - 1) * 0.1
            weights_pool["cooccurrence"] = cooc_w
            diag["cooccurrence"] = {
                "n_edges": cooc_d["n_edges"],
                "n_communities": cooc_d["n_communities"],
                "communities": cooc_d.get("communities", {}),
                "top_edges": [(e[0], e[1], e[2]) for e in cooc_d.get("top_edges", [])[:8]],
            }
        except Exception:
            weights_pool["cooccurrence"] = [1.0] * 34
            diag["cooccurrence"] = {"error": "failed"}
    else:
        diag["cooccurrence"] = {"inactive": True}

    # ── D: rmt_spectrum ──
    if 'rmt' in active:
        try:
            from ml.rmt_spectrum import compute_rmt_signals
            signal_nums, lam1, mp_bound, rmt_d = compute_rmt_signals(data, window=min(window, 200))
            rmt_w = [1.0] * 34
            for num in signal_nums:
                rmt_w[num] = 1.5
            weights_pool["rmt"] = rmt_w
            diag["rmt"] = {
                "is_signal": rmt_d["is_signal"],
                "signal_strength": rmt_d["signal_strength"],
                "max_eigenvalue": rmt_d["max_eigenvalue"],
                "mp_upper": rmt_d["mp_upper"],
                "signal_nums": signal_nums,
            }
        except Exception:
            weights_pool["rmt"] = [1.0] * 34
            diag["rmt"] = {"error": "failed"}
    else:
        diag["rmt"] = {"inactive": True}

    # ── E: transfer_entropy ──
    if 'transfer_entropy' in active:
        try:
            from ml.transfer_entropy import compute_transfer_entropy
            sig_pairs, te_d = compute_transfer_entropy(data, window=min(window, 400))
            te_w = [1.0] * 34
            top_pairs = [s for s in sig_pairs if s[5] < 0.001][:300]
            for a, b, lag, rate, baseline, p_val in top_pairs:
                boost = min(0.3, (0.001 - p_val) / 0.001 * 0.3)
                te_w[b] = min(2.0, te_w[b] + boost)
            weights_pool["transfer_entropy"] = te_w
            diag["transfer_entropy"] = {
                "n_pairs": te_d["n_significant"],
                "n_strong": te_d["n_strong"],
                "strong_pairs": te_d.get("strong_pairs", [])[:10],
            }
        except Exception:
            weights_pool["transfer_entropy"] = [1.0] * 34
            diag["transfer_entropy"] = {"error": "failed"}
    else:
        diag["transfer_entropy"] = {"inactive": True}


    # ── F: gap_analysis ──
    if 'gap' in active:
        try:
            from ml.gap_analysis import compute_gap_weights
            gap_w, gap_d = compute_gap_weights(data, window=min(window, 200))
            weights_pool["gap_analysis"] = gap_w
            diag["gap_analysis"] = {
                "hot": gap_d.get("hot", [])[:8],
                "cold": gap_d.get("cold", [])[:8],
                "n_hot": gap_d.get("n_hot", 0),
                "n_cold": gap_d.get("n_cold", 0),
            }
        except Exception:
            weights_pool["gap_analysis"] = [1.0] * 34
            diag["gap_analysis"] = {"error": "failed"}
    else:
        diag["gap_analysis"] = {"inactive": True}

    # ── G: modular_math ──
    if 'modular' in active:
        try:
            from ml.modular_math import compute_modular_weights
            mod_w, mod_d = compute_modular_weights(data, window=min(window, 200))
            weights_pool["modular_math"] = mod_w
            diag["modular_math"] = {
                "modules": mod_d.get("modules", {}),
                "hot": mod_d.get("hot", [])[:8],
                "n_hot": mod_d.get("n_hot", 0),
            }
        except Exception:
            weights_pool["modular_math"] = [1.0] * 34
            diag["modular_math"] = {"error": "failed"}
    else:
        diag["modular_math"] = {"inactive": True}

    # ── H: markov_state ──
    if 'markov' in active:
        try:
            from ml.markov_state import compute_markov_weights
            mkv_w, mkv_d = compute_markov_weights(data, window=min(window, 300))
            weights_pool["markov_state"] = mkv_w
            diag["markov_state"] = {
                "current_state": mkv_d.get("current_state", []),
                "predicted_state": mkv_d.get("predicted_state"),
                "confidence": mkv_d.get("confidence", 0),
                "n_states": mkv_d.get("n_states", 0),
                "hot": mkv_d.get("hot", [])[:8],
                "n_hot": mkv_d.get("n_hot", 0),
            }
        except Exception:
            weights_pool["markov_state"] = [1.0] * 34
            diag["markov_state"] = {"error": "failed"}
    else:
        diag["markov_state"] = {"inactive": True}
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

    # 归一化所有活跃算法
    for name in weights_pool:
        weights_pool[name] = _normalize(weights_pool[name])

    # 等权平均活跃算法
    fused = [1.0] * 34
    n_active = len(weights_pool)
    if n_active == 0:
        return fused, diag
    for num in range(1, 34):
        fused[num] = sum(weights_pool[name][num] for name in weights_pool) / n_active

    diag["n_active"] = n_active
    diag["active_list"] = list(weights_pool.keys())

    return fused, diag



# ═══ 蓝球信号融合 ═══

def collect_blue_signals(data, window=None, active=None):
    """运行蓝球相关算法, 返回融合蓝球权重 [0.0]*17 (1-indexed)."""
    if active is None or active == 'all':
        active = ['recent_bias', 'cooccurrence_red_blue', 'transfer_entropy_blue', 'rmt_cross']
    if not isinstance(active, list):
        active = [active]

    diag = {}
    weights_pool = {}

    if 'recent_bias' in active:
        try:
            from ml.recent_bias import compute_recent_blue_weights
            rb_blue_w = compute_recent_blue_weights(data, window=min(window or 50, 50))
            weights_pool["recent_bias"] = rb_blue_w
            hot_rb = [(b, round(rb_blue_w[b], 3)) for b in range(1, 17) if rb_blue_w[b] > 1.2]
            diag["recent_bias"] = {"hot": hot_rb, "n_hot": len(hot_rb)}
        except Exception:
            weights_pool["recent_bias"] = [1.0] * 17
            diag["recent_bias"] = {"error": "failed"}

    if 'cooccurrence_red_blue' in active:
        try:
            from ml.cooccurrence import compute_red_blue_cooccurrence
            rb_pairs, rb_d = compute_red_blue_cooccurrence(data, window=min(window or 300, 300))
            rb_blue_w = [1.0] * 17
            blue_mentions = Counter()
            for r, b, obs, _, p in rb_pairs:
                if p < 0.01:
                    blue_mentions[b] += 1
            for b in blue_mentions:
                rb_blue_w[b] = min(2.0, 1.0 + blue_mentions[b] * 0.15)
            weights_pool["cooc_rb"] = rb_blue_w
            top_blue = sorted([(b, rb_blue_w[b]) for b in range(1, 17) if rb_blue_w[b] > 1.1],
                              key=lambda x: -x[1])[:6]
            diag["cooccurrence_red_blue"] = {
                "n_pairs": rb_d["n_pairs"],
                "top_blue": top_blue,
            }
        except Exception:
            weights_pool["cooc_rb"] = [1.0] * 17
            diag["cooccurrence_red_blue"] = {"error": "failed"}

    if 'transfer_entropy_blue' in active:
        try:
            from ml.transfer_entropy import compute_blue_transfer_entropy
            te_pairs, te_d = compute_blue_transfer_entropy(data, window=min(window or 300, 300))
            te_blue_w = [1.0] * 17
            to_counts = Counter()
            for a, b, lag, rate, _, p in te_pairs:
                if p < 0.01:
                    boost = rate / (1.0 / 16.0)
                    to_counts[b] += min(1.0, boost * 0.3)
            for b in to_counts:
                te_blue_w[b] = min(2.0, 1.0 + to_counts[b])
            weights_pool["te_blue"] = te_blue_w
            top_te = sorted([(b, te_blue_w[b]) for b in range(1, 17) if te_blue_w[b] > 1.05],
                            key=lambda x: -x[1])[:6]
            diag["transfer_entropy_blue"] = {
                "n_fdr": te_d["n_fdr_significant"],
                "top_blue": top_te,
            }
        except Exception:
            weights_pool["te_blue"] = [1.0] * 17
            diag["transfer_entropy_blue"] = {"error": "failed"}

    if 'rmt_cross' in active:
        try:
            from ml.rmt_spectrum import compute_red_blue_cross_signal
            _, rmt_blue_w, rmt_d = compute_red_blue_cross_signal(data, window=min(window or 200, 200))
            weights_pool["rmt_cross"] = rmt_blue_w
            diag["rmt_cross"] = {
                "lam_blue": rmt_d["lam_blue"],
                "top_blue": rmt_d["top_blue"],
            }
        except Exception:
            weights_pool["rmt_cross"] = [1.0] * 17
            diag["rmt_cross"] = {"error": "failed"}

    def _norm(w):
        vals = w[1:17]
        mean_val = sum(vals) / 16
        if mean_val <= 0:
            return w
        return [0.0] + [max(0.5, min(2.0, w[b] / mean_val)) for b in range(1, 17)]

    for name in weights_pool:
        weights_pool[name] = _norm(weights_pool[name])

    fused = [0.0] * 17
    n_active = len(weights_pool)
    if n_active == 0:
        return [1.0] * 17, diag
    for b in range(1, 17):
        fused[b] = sum(weights_pool[name][b] for name in weights_pool) / n_active

    diag["n_active"] = n_active
    diag["active_list"] = list(weights_pool.keys())
    return fused, diag
# ═══ Walk-forward 回测 ═══

def backtest_single_algorithm(data, algo_fn, window=200, step=10):
    """Walk-forward 回测: 用前 window 期训练, 预测下 step 期.

    algo_fn(data_window) → weights [0.0]*34
    对每期预测: 用 weights 做 weighted 采样, 统计命中。

    Returns: avg_red_hits, blue_hit_rate, summary
    """
    if len(data) < window + step:
        return None, "数据不足"

    total_tests = 0
    total_red_hits = 0
    total_blue_hits = 0
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
            actual_blue = test_row[7]

            # 用权重做 weighted 采样 (best-of-20)
            from ml.micro_portfolio import _state
            if _state.valid_reds is None:
                from ml.micro_portfolio import _build_pool
                _build_pool()
            if _state.valid_reds is None:
                continue

            n_combos = len(_state.valid_reds) // 6
            if n_combos == 0:
                continue

            # 选 combo: best-of-20 weighted
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
    """运行所有算法的 walk-forward 回测."""
    results = {}

    # Algorithm functions that return weights given data window
    def algo_recent_bias(train_data):
        from ml.recent_bias import compute_recent_bias_weights
        w, _ = compute_recent_bias_weights(train_data, window=100)
        return w

    def algo_position(train_data):
        from ml.position_model import compute_position_weights
        pos_probs, _ = compute_position_weights(train_data, window=min(len(train_data), 200))
        pos_w = [0.0] * 34
        for num in range(1, 34):
            pos_w[num] = sum(pos_probs[p][num] for p in range(1, 7)) / 6.0
        mean_pos = sum(pos_w[1:]) / 33
        if mean_pos > 0:
            for num in range(1, 34):
                pos_w[num] = pos_w[num] / mean_pos
        return pos_w

    def algo_cooccurrence(train_data):
        from ml.cooccurrence import compute_cooccurrence
        _, communities, _ = compute_cooccurrence(train_data, window=min(len(train_data), 300))
        w = [1.0] * 34
        if communities:
            comm_sizes = Counter(communities.values())
            for num, cid in communities.items():
                w[num] = 1.0 + (comm_sizes.get(cid, 1) - 1) * 0.1
        return w

    def algo_rmt(train_data):
        from ml.rmt_spectrum import compute_rmt_signals
        signal_nums, _, _, _ = compute_rmt_signals(train_data, window=min(len(train_data), 200))
        w = [1.0] * 34
        for num in signal_nums:
            w[num] = 1.5
        return w

    def algo_transfer_entropy(train_data):
        from ml.transfer_entropy import compute_transfer_entropy
        sig_pairs, _ = compute_transfer_entropy(train_data, window=min(len(train_data), 400))
        w = [1.0] * 34
        top_pairs = [s for s in sig_pairs if s[5] < 0.001][:300]
        for a, b, lag, rate, baseline, p_val in top_pairs:
            w[b] = min(2.0, w[b] + 0.3)
        return w

    for name, fn in [
        ("recent_bias", algo_recent_bias),
        ("position", algo_position),
        ("cooccurrence", algo_cooccurrence),
        ("rmt", algo_rmt),
        ("transfer_entropy", algo_transfer_entropy),
    ]:
        result, err = backtest_single_algorithm(data, fn)
        if err:
            results[name] = {"error": err}
        else:
            results[name] = result

    return results
