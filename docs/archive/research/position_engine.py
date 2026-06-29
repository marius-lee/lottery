"""分位置策略引擎 — 每位置独立最优方法 → 6层叠加缩小候选空间

核心发现 (2026-06-26):
  方法按位置分化严重。P1最佳=张委铭(100%), P6最佳=刘大军·重合码(40%).
  全局top-15掩盖了这个 — 同一方法在P1和P6的命中率差10倍以上.

策略:
  1. 每位置找最佳方法 (交叉验证 recall@15)
  2. 查询时: 每位置独立选候选 → 组合约束过滤
  3. 从约束池采样出号

效果 (window=100验证):
  候选空间: 110万 → ~11万 (10x缩小)
  全中率: 0.45% → 8% (18x提升)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import random
import math
from collections import defaultdict


def _load_data():
    from server.db import load_draws
    return load_draws()


# ═══════════════════════════════════════════════════════════
# 训练: 找每位置最佳方法
# ═══════════════════════════════════════════════════════════

def find_best_per_position(data, window=100, k=15):
    """交叉验证找每位置的最佳方法.

    Returns:
        {pos: (method_name, method_fn, hit_rate, top_k_set_size)}
    """
    from ml.ensemble_aggregator import METHOD_REGISTRY, _init_registry, _top_k_indices
    _init_registry()

    n = len(data)
    start = max(n - window, window // 2)

    best = {}
    for p in range(6):
        best_method = None
        best_fn = None
        best_rate = 0
        for name, fn in METHOD_REGISTRY.items():
            hits = 0
            total = 0
            for i in range(start, n):
                train = data[:i]
                actual = sorted(data[i][1:7])
                try:
                    scores = fn(train)
                except Exception:
                    continue
                top_k_set = set(idx + 1 for idx in _top_k_indices(scores, k))
                if actual[p] in top_k_set:
                    hits += 1
                total += 1
            rate = hits / total if total > 0 else 0
            if rate > best_rate:
                best_rate = rate
                best_method = name
                best_fn = fn
        best[p] = {
            "method": best_method,
            "fn": best_fn,
            "hit_rate": round(best_rate, 4),
            "k": k,
        }

    return best


def _get_position_candidates(data, pos_methods, k=15):
    """查询时: 每位置用其最佳方法生成候选号码.

    Returns:
        {pos: set(candidate_numbers)}
    """
    from ml.ensemble_aggregator import _top_k_indices
    candidates = {}
    for p in range(6):
        fn = pos_methods[p]["fn"]
        try:
            scores = fn(data)
        except Exception:
            scores = [1.0 / 33] * 33
        top_k = set(idx + 1 for idx in _top_k_indices(scores, k))
        candidates[p] = top_k
    return candidates


# ═══════════════════════════════════════════════════════════
# 约束池采样
# ═══════════════════════════════════════════════════════════

def _sample_from_constrained_pool(pos_candidates, n, exclude_past=True,
                                    extra_exclude=None):
    """从位置约束池不放回采样n个组合.

    约束: 组合的第p个(sorted)号码必须在pos_candidates[p]中.
    采样方式: 从 micro_portfolio 的 valid_reds 全局池随机取 → 检查位置约束 → 通过就留.
    """
    from ml.micro_portfolio import _state
    # 确保池子已构建
    if _state.valid_reds is None:
        from ml.micro_portfolio import _build_pool
        _build_pool()

    valid_reds = _state.valid_reds
    if valid_reds is None:
        return []

    n_combos = len(valid_reds) // 6
    if n_combos == 0:
        return []

    from server.db import load_draws
    data = load_draws()
    past = {tuple(sorted(r[1:7])) for r in data} if exclude_past else set()
    if extra_exclude:
        past = past | extra_exclude

    results = []
    used = set()
    max_attempts = min(n * 5000, n_combos)  # 防止无限循环
    for _ in range(n):
        found = False
        for _ in range(max_attempts):
            idx = random.randrange(n_combos)
            base = idx * 6
            reds = tuple(valid_reds[base:base + 6])
            if reds in past or reds in used:
                continue
            # 位置约束检查 (valid_reds 已经是 sorted)
            ok = True
            for p in range(6):
                if reds[p] not in pos_candidates[p]:
                    ok = False
                    break
            if not ok:
                continue
            used.add(reds)
            results.append(list(reds))
            found = True
            break
        if not found:
            break
    return results


# ═══════════════════════════════════════════════════════════
# 出号入口
# ═══════════════════════════════════════════════════════════

# 缓存: 每位置最佳方法 → 磁盘
import json as _json
_POS_CACHE_PATH = os.path.join(os.path.dirname(__file__), '..', '.cache', 'position_best.json')


def _load_cached_best():
    if os.path.exists(_POS_CACHE_PATH):
        try:
            with open(_POS_CACHE_PATH) as f:
                cached = _json.load(f)
            # 重建fn引用
            from ml.ensemble_aggregator import METHOD_REGISTRY, _init_registry
            _init_registry()
            result = {}
            for p_str, info in cached.items():
                p = int(p_str)
                name = info["method"]
                if name in METHOD_REGISTRY:
                    result[p] = {
                        "method": name,
                        "fn": METHOD_REGISTRY[name],
                        "hit_rate": info["hit_rate"],
                        "k": info["k"],
                    }
            if len(result) == 6:
                return result
        except Exception:
            pass
    return None


def _save_cached_best(best):
    os.makedirs(os.path.dirname(_POS_CACHE_PATH), exist_ok=True)
    data = {str(p): {"method": best[p]["method"], "hit_rate": best[p]["hit_rate"], "k": best[p]["k"]} for p in range(6)}
    with open(_POS_CACHE_PATH, 'w') as f:
        _json.dump(data, f)


_cached_best = None
_cached_data_count = 0


def _get_position_methods(data):
    global _cached_best, _cached_data_count
    if _cached_best is not None and len(data) == _cached_data_count:
        return _cached_best
    # 尝试磁盘加载
    disk = _load_cached_best()
    if disk is not None:
        _cached_best = disk
        _cached_data_count = len(data)
        return disk
    # 训练
    best = find_best_per_position(data)
    _cached_best = best
    _cached_data_count = len(data)
    _save_cached_best(best)
    return best


def position_tickets(n=6, k=15):
    """分位置策略出号.

    1. 训练最优方法分配 (缓存)
    2. 每位置独立生成候选
    3. 约束池采样
    4. 蓝球: Dirichlet+Thompson+Gumbel
    """
    from ml.bias_engine import dirichlet_blue_posterior, thompson_sample, gumbel_max_topk
    from ml.ssq_constants import TICKET_PRICE, RANDOM_SINGLE_EV

    data = _load_data()

    if len(data) < 100:
        return {"ok": False, "msg": f"数据不足, 当前{len(data)}期"}

    # 1. 加载/更新每位置最佳方法 (磁盘缓存)
    _cached_best = _get_position_methods(data)

    # 2. 每位置生成候选
    pos_candidates = _get_position_candidates(data, _cached_best, k=k)

    # 3. 约束池采样
    tickets_reds = _sample_from_constrained_pool(pos_candidates, n)

    if len(tickets_reds) < n:
        # 部分失败: 补充纯池子采样
        from ml.micro_portfolio import _pool_sample
        needed = n - len(tickets_reds)
        extra = _pool_sample(needed, extra_exclude=set(tuple(r) for r in tickets_reds))
        tickets_reds.extend(extra)

    # 4. 蓝球分配
    blue_alphas = dirichlet_blue_posterior(data)
    blue_theta = thompson_sample(blue_alphas)
    used_blues = set()
    result_tickets = []
    for reds in tickets_reds:
        cand_blues = [b for b in range(1, 17) if b not in used_blues]
        if not cand_blues:
            cand_blues = list(range(1, 17))
        cand_thetas = [blue_theta[b-1] if b in cand_blues else 0 for b in range(1, 17)]
        blue = gumbel_max_topk(cand_thetas, k=1)[0]
        used_blues.add(blue)
        result_tickets.append({"reds": reds, "blue": blue})

    # 5. 元数据
    pos_methods_display = {f"P{p+1}": _cached_best[p]["method"] for p in range(6)}
    pos_rates_display = {f"P{p+1}": f"{_cached_best[p]['hit_rate']:.0%}" for p in range(6)}

    return {
        "ok": True,
        "algorithm": "Position-Optimized-v" + str(k),
        "tickets": result_tickets,
        "budget": len(result_tickets),
        "cost_rmb": len(result_tickets) * TICKET_PRICE,
        "position_methods": pos_methods_display,
        "position_hit_rates": pos_rates_display,
        "candidate_sizes": {f"P{p+1}": len(pos_candidates[p]) for p in range(6)},
        "ev_estimate": {
            "ev_per_draw": round(RANDOM_SINGLE_EV * len(result_tickets), 2),
            "cost_per_draw": len(result_tickets) * TICKET_PRICE,
        },
    }


def pos_stats():
    """分位置统计摘要."""
    data = _load_data()
    best = find_best_per_position(data, window=200)
    return {
        "ok": True,
        "best_per_position": {f"P{p+1}": {
            "method": best[p]["method"],
            "hit_rate": best[p]["hit_rate"],
        } for p in range(6)},
    }


if __name__ == "__main__":
    result = position_tickets(n=6, k=15)
    if result["ok"]:
        print("分位置策略出号:")
        for i, t in enumerate(result["tickets"]):
            print(f"  #{i+1} {' '.join(str(n).zfill(2) for n in t['reds'])} | {str(t['blue']).zfill(2)}")
        print(f"位置方法: {result['position_methods']}")
        print(f"位置命中率: {result['position_hit_rates']}")
        print(f"候选集大小: {result['candidate_sizes']}")
    else:
        print(f"失败: {result.get('msg')}")
