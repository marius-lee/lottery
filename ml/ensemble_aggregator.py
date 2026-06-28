"""方法聚合引擎 — 5个验证有效的方法 → 加权聚合 → 覆盖设计

[已修剪 2026-06-28] 100期OOS回测后从13方法精简到5:
  保留(OOS lift>1.0): 冷号反转/定尾选号/排列型/八招定胆/重合码
  移除(OOS lift≤1.0): 5期重号/6区间/极值/围号/频率基线/贝叶斯偏差/MA双通道/趋势分析

新增方法只需: 实现score_reds(data)→[33]float + register_method(name, fn)
"""
import math

# ═══════════════════════════════════════════════════════════════════════════
# 方法注册表
# ═══════════════════════════════════════════════════════════════════════════

METHOD_REGISTRY = {}  # {name: score_reds_fn}


def register_method(name, fn):
    """注册评分方法. fn(data) -> list[float] (33个, 0-1)."""
    METHOD_REGISTRY[name] = fn
    return fn  # 可用作装饰器


# ═══════════════════════════════════════════════════════════════════════════
# 12个评分函数 — 每函数 data→[33]float
# ═══════════════════════════════════════════════════════════════════════════

def _score_wuming_period5(data):
    """吴明·5期重号 [吴明2006 Ch1: 5大定理].
    近5期出现过的号码=热号=1.0, 其他=0.3."""
    from ml.micro_portfolio import _period5_hotness
    result = _period5_hotness()
    if not result.get("ok"):
        return [0.5] * 33  # [数学] 0.5=无信息中性值(等概率假设)
    hot = set(result["hot_numbers"])
    return [1.0 if (i + 1) in hot else 0.3 for i in range(33)]


def _score_wuming_cold9(data):
    """吴明·9期冷号反转 [吴明2006 Ch3: 63.15%转化率].
    遗漏9-20期→即将反弹=1.0, 遗漏>30→极寒=0.1, 正常=0.5."""
    from ml.micro_portfolio import _period9_cold
    result = _period9_cold()
    if not result.get("ok"):
        return [0.5] * 33
    scores = [0.5] * 33
    for c in result["cold_numbers"]:
        n, om = c["number"], c["omission"]
        if 9 <= om <= 20:
            scores[n - 1] = 1.0    # [原书] 63%冷号5期内转热
        elif om > 30:
            scores[n - 1] = 0.1    # [原书] 极寒, 继续回避
        else:
            scores[n - 1] = 0.5
    return scores


def _score_wuming_zone6(data):
    """吴明·6区间排除 [吴明2006 Ch4: 100%安全排1区].
    非空区间号码=1.0, 空区间号码=0.1."""
    from ml.micro_portfolio import _zone6_exclusion
    result = _zone6_exclusion()
    if not result.get("ok"):
        return [0.5] * 33
    killed = set(result["killed"])
    return [0.1 if (i + 1) in killed else 1.0 for i in range(33)]


def _score_wuming_extreme(data):
    """吴明·极值优先 [吴明胆码篇 p15-16].
    位置连空>15→极值接近→1.0, 正常=0.5."""
    from ml.micro_portfolio import _extreme_value_dan
    result = _extreme_value_dan(data)
    if not result.get("ok"):
        return [0.5] * 33
    scores = [0.5] * 33
    for pos_stats in result["positions"].values():
        for item in pos_stats:
            n = item["number"]
            om = item["omission"]
            scores[n - 1] = max(scores[n - 1], 1.0 if om > 15 else 0.5)
    return scores


def _score_peng_channel(data):
    """彭浩·MA双通道 [彭浩 2010 Ch5 §3].
    用通道覆盖计数替代二元评分: 被越多位置通道覆盖→分数越高."""
    from ml.peng_hao import compute_all_channels
    if len(data) < 19:
        return [0.5] * 33
    channels = compute_all_channels(data)
    coverage = [0] * 33
    for pos in range(6):
        ch = channels.get(f"pos_{pos}", {})
        lo = ch.get("lower")
        hi = ch.get("upper")
        if lo is not None and hi is not None:
            for n in range(max(1, int(lo)), min(33, int(hi)) + 1):
                coverage[n - 1] += 1
    max_cov = max(coverage) or 1
    # [数学] min-max归一化到[0.1, 1.0], 保留下限0.1避免归零
    return [0.1 + 0.9 * (c / max_cov) for c in coverage]


def _score_jiang_jialin(data):
    """蒋加林·排列型 [蒋加林 2001/2010: 位间隔+位跨度+位形态].
    每个位置统计历史出现频率, 高频号码=1.0, 递减到低频=0.1."""
    # [数学] 窗口=50: 50期≈4个月, 平衡近期趋势与长期分布
    window = min(50, len(data))
    recent = data[-window:]
    pos_counts = [[0] * 33 for _ in range(6)]
    for row in recent:
        s = sorted(row[1:7])
        for p in range(6):
            pos_counts[p][s[p] - 1] += 1
    scores = [0.0] * 33
    for n in range(1, 34):
        total = 0.0
        for p in range(6):
            total += pos_counts[p][n - 1] / window
        scores[n - 1] = max(0.1, min(1.0, total * 3.0))
        # [数学] *3缩放: 6位置平均频率≈6/33≈0.18, ×3→0.54中线
    return scores


def _score_zhang_weiming(data):
    """张委铭·围号选号 [张委铭 2017: 18种低胜率杀号].
    _compute_weihao_values 返回 (candidates, values_dict). 候选号码=1.0, 其他=0.3."""
    from ml.zhang_weiming import _compute_weihao_values
    try:
        weihao = _compute_weihao_values(data)
        # [工程] weihao 是 tuple: (candidates_list, values_dict)
        if isinstance(weihao, tuple) and len(weihao) >= 1:
            candidates = weihao[0]  # list of ints
        elif isinstance(weihao, dict):
            candidates = list(weihao.get('reds', weihao).keys())
        else:
            candidates = []
        scores = [0.3] * 33
        for n in candidates:
            if isinstance(n, int) and 1 <= n <= 33:
                scores[n - 1] = 1.0
        return scores
    except Exception:
        return [0.5] * 33


def _score_li_zhilin(data):
    """李志林·八招定胆 [李志林 2012: 8种定胆方法].
    被≥1个定胆方法选中=1.0, 其他=0.3."""
    from ml.li_zhilin import generate_eight_dan, generate_dan3_methods
    try:
        dan_candidates = set()
        # 八招定胆
        dan8 = generate_eight_dan(data)
        if dan8.get("ok"):
            for item in dan8.get("candidates", []):
                if isinstance(item, int):
                    dan_candidates.add(item)
        # 三胆辅助
        dan3 = generate_dan3_methods(data)
        if dan3.get("ok"):
            for item in dan3.get("candidates", []):
                if isinstance(item, int):
                    dan_candidates.add(item)
        return [1.0 if (i + 1) in dan_candidates else 0.3 for i in range(33)]
    except Exception:
        return [0.5] * 33


def _score_liu_dajun_tail(data):
    """刘大军·定尾选号 [刘大军 2010: 定尾选号法].
    高频尾数号码=1.0, 递减到低频=0.1."""
    from ml.liu_dajun import position_tail_analysis
    try:
        analysis = position_tail_analysis(data)
        tail_scores = {}
        for pos_data in analysis.get("positions", []):
            tails = pos_data.get("tails", [])  # list of {digit, count, pct, hot}
            for tinfo in tails:
                digit = tinfo["digit"]
                count = tinfo["count"]
                tail_scores[digit] = max(tail_scores.get(digit, 0), count)
        if not tail_scores:
            return [0.5] * 33
        max_count = max(tail_scores.values()) or 1
        scores = [0.1] * 33
        for n in range(1, 34):
            t = n % 10
            scores[n - 1] = max(0.1, tail_scores.get(t, 0) / max_count)
        return scores
    except Exception:
        return [0.5] * 33


def _score_liu_dajun_coincidence(data):
    """刘大军·重合码 [刘大军 2010 p21-22: 大中小∩012路交叉].
    尾数∈{1,3,6,8}=1.0, 其他=0.3."""
    from ml.liu_dajun import COINCIDENCE_TAILS
    return [1.0 if (i + 1) % 10 in COINCIDENCE_TAILS else 0.3 for i in range(33)]


def _score_li_xiangchun(data):
    """李相春·趋势分析 [李相春 2003: 散度/偏度/DHR/三浪].
    综合趋势信号→评分: DHR粘性号(低DHR=热) + 遗漏比 + 三浪信号."""
    from ml.li_xiangchun import dashboard, sanlang_predict
    try:
        scores = [0.3] * 33

        dash = dashboard(data)
        # DHR粘性号: 低DHR→号码频繁出现, 高DHR→冷号 [原书p.84]
        dhr_sticky = dash.get("dhr_sticky", [])
        if dhr_sticky:
            max_dhr = max(d["dhr"] for d in dhr_sticky) or 1.0
            for item in dhr_sticky:
                n = item["num"]
                if 1 <= n <= 33:
                    # 低DHR→高分: score = 1 - dhr/max_dhr, 映射到[0.3, 1.0]
                    dhr_norm = min(1.0, item["dhr"] / max_dhr)
                    scores[n - 1] = max(scores[n - 1], 1.0 - 0.7 * dhr_norm)

        # 遗漏比: 高遗漏→冷号(降权)
        omission = dash.get("omission_ratios", {})
        max_om = max(omission.values()) if omission else 1.0
        for n_str, om_val in omission.items():
            try:
                n = int(n_str)
                if 1 <= n <= 33 and max_om > 0:
                    # 高遗漏→降低分数
                    om_norm = om_val / max_om
                    scores[n - 1] = max(0.1, scores[n - 1] * (1.0 - 0.3 * om_norm))
            except (ValueError, TypeError):
                pass

        # 三浪: 冷→热反转信号 [原书p.133]
        sanlang = sanlang_predict(data)
        for signal_list in ["jiang", "sheng"]:
            for item in sanlang.get(signal_list, []):
                n = item.get("num") if isinstance(item, dict) else item
                if isinstance(n, int) and 1 <= n <= 33:
                    scores[n - 1] = max(scores[n - 1], 0.9)

        return scores
    except Exception:
        return [0.5] * 33


def _score_frequency_baseline(data):
    """频率基线 — Laplace平滑频率归一化.
    每个红球的出现频率, 归一化到[0.1, 1.0]."""
    counts = [1.0] * 33  # Laplace平滑: +1伪计数 [数学] 拉普拉斯先验
    for row in data:
        for n in row[1:7]:
            counts[n - 1] += 1.0
    total = sum(counts)
    freqs = [c / total for c in counts]
    fmin, fmax = min(freqs), max(freqs)
    if fmax == fmin:
        return [0.5] * 33
    # [数学] min-max归一化到[0.1, 1.0]: 保留下限0.1避免归零
    return [0.1 + 0.9 * (f - fmin) / (fmax - fmin) for f in freqs]


# ═══════════════════════════════════════════════════════════════════════════
# 注册所有方法
# ═══════════════════════════════════════════════════════════════════════════

_initialized = False


def _init_registry():
    """一次性注册所有12个方法."""
    global _initialized
    if _initialized:
        return
    methods = [
        ("吴明·9期冷号反转",  _score_wuming_cold9),
        ("蒋加林·排列型",     _score_jiang_jialin),
        ("李志林·八招定胆",   _score_li_zhilin),
        ("刘大军·定尾选号",   _score_liu_dajun_tail),
        ("刘大军·重合码",     _score_liu_dajun_coincidence),
    ]
    for name, fn in methods:
        register_method(name, fn)
    _initialized = True




# ═══════════════════════════════════════════════════════════════════════════
# 回测校准
# ═══════════════════════════════════════════════════════════════════════════

def _top_k_indices(scores, k):
    """返回分数最高的k个索引(0-based)."""
    indexed = [(i, s) for i, s in enumerate(scores)]
    indexed.sort(key=lambda x: -x[1])
    return [i for i, _ in indexed[:k]]


def backtest_calibrate(data, k=15, window=50):
    """滑动窗口回测, 计算每个方法的 recall@K.

    recall@K = 开奖6红有多少落在方法评分top-K中, 除以6.

    Args:
        data: 全部历史开奖数据
        k: top-K (默认15, C(15,6)=5005组合, SA可收敛)
        window: 验证窗口期数 (默认50, ~4个月) [工程] 50期覆盖冷热转换周期
    Returns:
        {method_name: weight} 归一化权重字典
    """
    _init_registry()
    if len(data) < window + 10:
        # [工程] window+10是最小回测样本: 50期验证+10期缓冲
        return {name: 1.0 / len(METHOD_REGISTRY) for name in METHOD_REGISTRY}

    recalls = {name: [] for name in METHOD_REGISTRY}
    start = max(len(data) - window, window // 2)

    for i in range(start, len(data)):
        train = data[:i]
        actual = set(data[i][1:7])

        for name, fn in METHOD_REGISTRY.items():
            try:
                scores = fn(train)
                top_k_set = set(idx + 1 for idx in _top_k_indices(scores, k))
                hit = len(actual & top_k_set)
                recalls[name].append(hit / 6.0)  # [数学] recall=命中数/6
            except Exception:
                recalls[name].append(0.0)

    # [数学] 平均recall, 下限0.01防止归零
    raw = {}
    for name, vals in recalls.items():
        raw[name] = max(0.01, sum(vals) / len(vals)) if vals else 0.01

    # [数学] 温度softmax, τ=0.5放大方法间差距 [工程] 0.5=中等区分度
    tau = 0.5
    exp_sum = sum(math.exp(v / tau) for v in raw.values())
    if exp_sum == 0:
        return {name: 1.0 / len(raw) for name in raw}

    return {name: math.exp(v / tau) / exp_sum for name, v in raw.items()}


# ═══════════════════════════════════════════════════════════════════════════
# 实时聚合
# ═══════════════════════════════════════════════════════════════════════════

def score_all_methods(data):
    """运行所有活跃方法, 返回 {name: [33]float}."""
    _init_registry()
    results = {}
    for name, fn in METHOD_REGISTRY.items():
        try:
            results[name] = fn(data)
        except Exception:
            results[name] = [0.5] * 33  # [数学] 异常=中性分0.5
    return results


def aggregate_scores(method_scores, weights):
    """加权聚合: final[n] = Σ(w_m × score_m[n]) / Σw_m.

    Args:
        method_scores: {name: [33]float}
        weights: {name: weight}
    Returns:
        [33]float 聚合分数
    """
    total_w = sum(weights.values())
    if total_w == 0:
        return [0.5] * 33  # [数学] 0.5=无信息中性值

    final = [0.0] * 33
    for name, scores in method_scores.items():
        w = weights.get(name, 0.0)
        if w == 0:
            continue
        for i in range(33):
            final[i] += w * scores[i]

    # 归一化到[0,1]
    return [s / total_w for s in final]


def select_hot_numbers(final_scores, k=15):
    """按聚合分数排序, 取top-K号码."""
    return [idx + 1 for idx in _top_k_indices(final_scores, k)]


# ═══════════════════════════════════════════════════════════════════════════
# 权重缓存 (避免每次生成都跑回测)
# ═══════════════════════════════════════════════════════════════════════════

_cached_weights = None
_cached_data_count = 0


def _get_weights(data, k=15, window=50):
    """获取权重(带缓存). 数据未变时重用缓存. 同时持久化到 strategy_weights."""
    global _cached_weights, _cached_data_count
    if _cached_weights is not None and len(data) == _cached_data_count:
        return _cached_weights
    weights = backtest_calibrate(data, k=k, window=window)
    _cached_weights = weights
    _cached_data_count = len(data)
    _persist_weights(weights)
    return weights


def _persist_weights(weights):
    """将回测权重写入 strategy_weights 表."""
    try:
        from server import db
        conn = db.get_db()
        now = db._now() if hasattr(db, '_now') else None
        for name, w in weights.items():
            hits = int(w * 100)
            tries = 100
            conn.execute(
                """INSERT OR REPLACE INTO strategy_weights (name, weight, hits, tries)
                   VALUES (?, ?, ?, ?)""",
                (name, round(w, 4), hits, tries))
        conn.commit()
        conn.close()
    except Exception:
        pass  # 持久化失败不影响核心逻辑


def run_full_backtest(k=15, window=50):
    """全量回测 — 计算每个方法的 recall@K 并记录到 backtest_results.

    Returns:
        {"ok": True, "methods": [...], "baseline": float, "period": int}
    """
    from server import db
    data = db.load_draws()
    if len(data) < window + 10:
        return {"ok": False, "msg": f"数据不足, 需≥{window+10}期, 当前{len(data)}期"}

    _init_registry()
    results = []
    for name, fn in METHOD_REGISTRY.items():
        recalls = []
        max_hit = 0
        start = max(len(data) - window, window // 2)
        for i in range(start, len(data)):
            try:
                train = data[:i]
                actual = set(data[i][1:7])
                scores = fn(train)
                top_k_set = set(idx + 1 for idx in _top_k_indices(scores, k))
                hit = len(actual & top_k_set)
                recalls.append(hit / 6.0)
                if hit > max_hit:
                    max_hit = hit
            except Exception:
                recalls.append(0.0)
        avg_recall = sum(recalls) / len(recalls) if recalls else 0.0
        results.append({
            "name": name,
            "avg_red_hit": round(avg_recall * 6, 2),  # 转换为命中数
            "blue_hit_rate": 0.0,  # 红球方法无蓝球命中率
            "max_hit": max_hit,
            "test_count": len(recalls),
        })

    # 频率基线: 随机选15个号码的期望recall
    # 超几何: E[命中数] = 6 * 15/33 ≈ 2.73
    baseline_hit = 6.0 * k / 33.0

    # 持久化
    try:
        conn = db.get_db()
        for r in results:
            weight_val = round(max(0.01, r["avg_red_hit"] / max(baseline_hit, 0.01)), 4)
            conn.execute(
                """INSERT INTO backtest_results (window_size, strategy, avg_red_hit,
                   blue_hit_rate, max_hit, test_count, weight)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (window, r["name"], r["avg_red_hit"], r["blue_hit_rate"],
                 r["max_hit"], r["test_count"], weight_val))
            # 同时更新 strategy_weights
            conn.execute(
                """INSERT OR REPLACE INTO strategy_weights (name, weight, hits, tries)
                   VALUES (?, ?, ?, ?)""",
                (r["name"], weight_val, int(r["avg_red_hit"] * r["test_count"]),
                 r["test_count"] * 6))
        conn.commit()
        conn.close()
    except Exception:
        pass

    return {
        "ok": True,
        "methods": results,
        "baseline_expected_hit": round(baseline_hit, 2),
        "window_size": window,
        "data_period": data[-1][0] if data else 0,
        "total_draws": len(data),
    }


# ═══════════════════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════════════════

def ensemble_tickets(k=15, t=4, n=6, max_overlap=2):
    """方法聚合 + 覆盖设计 出号.

    Args:
        k: 热号数 (默认15, C(15,6)=5005)
        t: 覆盖强度 (默认4, 保底四等奖)
        n: 目标注数 (默认6)
        max_overlap: 注间最大共享红球数 (默认2)

    Returns:
        dict {ok, tickets, hot_numbers, method_weights, coverage_pct, ...}
    """
    from server.db import load_draws
    from ml.covering_design import greedy_t_covering
    from ml.micro_portfolio import _pick_unique_blue
    from ml.ssq_constants import TICKET_PRICE, RANDOM_SINGLE_EV

    data = load_draws()
    if len(data) < 30:
        return {"ok": False, "msg": f"数据不足(需≥30期), 当前{len(data)}期"}

    # 1. 回测校准权重
    weights = _get_weights(data, k=k)

    # 2. 运行所有方法
    method_scores = score_all_methods(data)

    # 3. 加权聚合 → top-K
    final_scores = aggregate_scores(method_scores, weights)
    hot_numbers = select_hot_numbers(final_scores, k=k)

    # 4. 覆盖设计 (轻量版, 限迭代)
        # 贪心覆盖: 确定性, ~0.1-1s, (1-1/e)近似比
    best_tickets, best_cov = greedy_t_covering(hot_numbers, n, t)

    if not best_tickets:
        return {"ok": False, "msg": "覆盖设计未能产生有效票"}
    if len(best_tickets) < n:
        # 补随机票到n注
        import random
        while len(best_tickets) < n:
            ticket = sorted(random.sample(hot_numbers, 6))
            if ticket not in best_tickets:
                best_tickets.append(ticket)

    cover = {
        "ok": True,
        "tickets": best_tickets,
        "ticket_count": len(best_tickets),
        "estimated_coverage_pct": best_cov,
        "guarantee": (f"如果全部6个开奖红球都在{k}个热号中，"
                      f"则≈{best_cov:.0f}%概率至少命中{t}个红球"),
        "coverage_quality": "optimal" if best_cov > 99 else ("near_optimal" if best_cov > 90 else "moderate"),
    }

    # 5. 蓝球分配 (复用现有多作者投票)
    from ml.micro_portfolio import (
        _liu_dajun_candidates, _cailele_candidates, _gongyi_candidates,
        _wuming_candidates, _wuming_clockwise_candidates, _wuming_bsd_candidates,
    )
    blue_active = [
        _liu_dajun_candidates, _cailele_candidates, _gongyi_candidates,
        _wuming_candidates, _wuming_clockwise_candidates, _wuming_bsd_candidates,
    ]
    inter = set(range(1, 17))
    union = set()
    for fn in blue_active:
        cands = fn()
        if cands:
            inter &= cands
            union |= cands
    blue_pool = inter if inter else union if union else set(range(1, 17))

    blue_weights = [0.0] * 16
    w = 1.0 / len(blue_pool) if blue_pool else 1.0 / 16
    for b in blue_pool:
        blue_weights[b - 1] = w

    used_blues = set()
    tickets = []
    for reds in cover["tickets"]:
        blue = _pick_unique_blue(blue_weights, used_blues)
        used_blues.add(blue)
        tickets.append({"reds": reds, "blue": blue})

    # 6. 构建返回
    weight_display = {name: round(w, 4) for name, w in
                      sorted(weights.items(), key=lambda x: -x[1])}

    return {
        "ok": True,
        "algorithm": f"Ensemble-Covering-v{k}-t{t}",
        "tickets": tickets,
        "budget": len(tickets),
        "cost_rmb": len(tickets) * TICKET_PRICE,
        "hot_numbers": hot_numbers,
        "hot_count": k,
        "method_weights": weight_display,
        "method_count": len(METHOD_REGISTRY),
        "coverage_pct": cover["estimated_coverage_pct"],
        "coverage_quality": cover.get("coverage_quality", "unknown"),
        "guarantee": cover["guarantee"],
        "ev_estimate": {
            "ev_per_draw": round(RANDOM_SINGLE_EV * len(tickets), 2),
            "cost_per_draw": len(tickets) * TICKET_PRICE,
        },
    }
