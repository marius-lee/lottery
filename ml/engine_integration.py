"""引擎集成层 — 简化版 (基于100期OOS回测结果)

[已修剪 2026-06-28] 移除对5个已归档模块的依赖:
  - particle_filter.py (粒子滤波, OOS无显著提升)
  - strategy_bandit.py (策略Bandit, 无独立验证)
  - fdr_method_selector.py (FDR筛选, 过度工程)
  - entropy_selector.py (熵值选号, 无独立验证)  
  - kelly_allocator.py (Kelly分配, 不适用于此场景)

替代方案:
  - 热号评分: 加权组合冷号反转(0.4) + 定尾选号(0.3) + 排列型(0.3)
  - 过滤推荐: 默认 color+block9 基础过滤
  - 注数: 固定 n=3 (Kelly在负EV场景下建议投注=0)
"""
import time
from typing import List, Dict

_cache: Dict = {}
_CACHE_TTL = 60


def _cached(key: str, compute_fn):
    now = time.time()
    entry = _cache.get(key)
    if entry and now - entry["ts"] < _CACHE_TTL:
        return entry["val"]
    val = compute_fn()
    _cache[key] = {"val": val, "ts": now}
    return val


def compute_advanced_hotness(window: int = 200) -> List[float]:  # 200期≈3年, 覆盖足够的历史统计
    """合成热号评分 [33]float — 用3个OOS验证方法加权."""
    def _compute():
        from server.db import load_draws
        from ml.ensemble_aggregator import _score_wuming_cold9, _score_liu_dajun_tail, _score_jiang_jialin
        data = load_draws()
        
        try:
            cold9 = _score_wuming_cold9(data)
            tails = _score_liu_dajun_tail(data)
            pos = _score_jiang_jialin(data)
        except Exception:
            # 回退到均匀分布
            return [0.5] * 33
        
        # 加权: 冷号反转 0.4 + 定尾选号 0.3 + 排列型 0.3
        scores = [0.0] * 33
        for i in range(33):
            scores[i] = 0.4 * cold9[i] + 0.3 * tails[i] + 0.3 * pos[i]
        return scores
    
    return _cached("advanced_hotness", _compute)


def recommend_filters() -> Dict[str, bool]:
    """推荐过滤组合 — 使用 OOS 中性配置."""
    return {"color_filter": True, "block9_filter": True}


def auto_ticket_count(budget: float = 100.0) -> int:
    """自动注数 — 固定3注 (Kelly在负EV场景建议为0)."""
    return 3


def ensemble_hot_numbers(k: int = None) -> List[int]:
    if k is None:
        try:
            from ml.bias_v_selector import auto_v
            k = auto_v().v
        except Exception:
            k = 15
    """多方法综合热号."""
    def _compute():
        from server.db import load_draws
        from ml.ensemble_aggregator import score_all_methods, aggregate_scores, _get_weights
        
        data = load_draws()
        weights = _get_weights(data, k=k)
        method_scores = score_all_methods(data)
        ensemble_scores = aggregate_scores(method_scores, weights)
        
        advanced = compute_advanced_hotness(min(200, len(data)))
        
        # 合成: ensemble 0.5 + advanced 0.5
        final = [0.0] * 33
        for i in range(33):
            final[i] = 0.5 * ensemble_scores[i] + 0.5 * advanced[i]
        
        indexed = [(i, s) for i, s in enumerate(final)]
        indexed.sort(key=lambda x: -x[1])
        return [i + 1 for i, _ in indexed[:k]]
    
    return _cached(f"ensemble_hot_{k}", _compute)


def integration_status() -> dict:
    """引擎集成状态报告."""
    try:
        hotness = compute_advanced_hotness()
        hot = ensemble_hot_numbers()  # auto-detect optimal v
        return {
            "ok": True,
            "active_methods": 5,
            "deprecated_modules": [
                "particle_filter", "strategy_bandit", "fdr_method_selector",
                "entropy_selector", "kelly_allocator"
            ],
            "recommended_filters": recommend_filters(),
            "ensemble_hot_numbers": hot[:10],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}
