"""False Discovery Rate (Benjamini-Hochberg) 方法筛选器.

问题: ensemble_aggregator 用13种方法加权聚合, 但部分方法统计不显著,
  用BH过程过滤掉"假阳性"方法, 保留真正有预测力的方法.

Benjamini-Hochberg (1995):
  1. 对每个方法做Permutation检验: 打乱时间序列 → 重算得分 → 零分布
  2. 得到 p-value = P(随机得分 ≥ 实际得分)
  3. BH过程: 对 p-values 排序, 找到最大 k 满足 p_{(k)} ≤ (k/m)×α
  4. 拒绝前k个假设 (即这些方法显著)

用法:
  from ml.fdr_method_selector import run_fdr_filter
  result = run_fdr_filter()
  # result["significant_methods"]: 显著方法的名称列表
  # result["rejected"]: 被拒绝(不显著)的方法
"""
import math
import random
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


def _permutation_test(score_fn, data, actual_score, n_perm: int = 200) -> float:
    """置换检验: 打乱时间序列, 重算得分, 计算p值.
    
    Args:
        score_fn: 从 data → [33]float 的评分函数
        data: 原始数据
        actual_score: 实际方法的评分向量 [33]float
        n_perm: 置换次数
        
    Returns:
        p-value: P(随机得分 ≥ 实际得分)
    """
    # 使用得分向量的L2范数作为检验统计量
    actual_stat = sum(s * s for s in actual_score)
    
    null_stats = []
    for _ in range(n_perm):
        # 打乱红球号码 (保持每期6个的结构)
        permuted_data = []
        for row in data:
            # 随机重新分配6个红球号码
            all_nums = list(range(1, 34))
            random.shuffle(all_nums)
            new_reds = sorted(all_nums[:6])
            # 保持蓝球不变
            new_row = [row[0]] + new_reds + [row[7] if len(row) > 7 else row[6]]
            permuted_data.append(new_row)
        
        try:
            perm_scores = score_fn(permuted_data)
            perm_stat = sum(s * s for s in perm_scores)
            null_stats.append(perm_stat)
        except Exception:
            null_stats.append(0.0)
    
    # p-value = 右尾比例
    null_stats.sort()
    right_tail = sum(1 for s in null_stats if s >= actual_stat) / n_perm
    return max(right_tail, 1.0 / n_perm)  # 下限


def _benjamini_hochberg(p_values: List[Tuple[str, float]], alpha: float = 0.10) -> Tuple[List[str], List[str]]:
    """Benjamini-Hochberg 过程.
    
    Args:
        p_values: [(method_name, p_value), ...]
        alpha: FDR控制水平 (默认0.10, 较宽松; 0.05更严格)
        
    Returns:
        (significant_methods, rejected_methods)
    """
    # 按p值升序
    sorted_p = sorted(p_values, key=lambda x: x[1])
    m = len(sorted_p)
    
    # 找到最大k满足 p_{(k)} ≤ (k/m) × α
    k_max = 0
    for k, (name, p) in enumerate(sorted_p, 1):
        threshold = (k / m) * alpha
        if p <= threshold:
            k_max = k
    
    significant = [name for name, _ in sorted_p[:k_max]]
    rejected = [name for name, _ in sorted_p[k_max:]]
    
    return significant, rejected


def run_fdr_filter(method_scores: Optional[Dict[str, List[float]]] = None,
                   alpha: float = 0.10, n_perm: int = 100) -> dict:
    """运行FDR过滤, 返回显著/不显著方法.
    
    Args:
        method_scores: {name: [33]float} 预计算的评分, None=自动计算
        alpha: FDR水平
        n_perm: 置换次数 (100=快速, 500=准确)
        
    Returns:
        dict with significant_methods, rejected, p_values, threshold
    """
    from server import db
    from ml.ensemble_aggregator import score_all_methods, METHOD_REGISTRY
    
    data = db.load_draws()
    if len(data) < 50:
        return {"ok": False, "msg": "数据不足, 需≥50期"}
    
    # 计算实际评分
    if method_scores is None:
        method_scores = score_all_methods(data)
    
    # 对每个方法做置换检验 (耗时, 使用缓存)
    from ml.ensemble_aggregator import _get_weights as get_weights
    
    p_values = []
    detail = {}
    
    for name, scores in method_scores.items():
        # 获取该方法的评分函数
        fn = METHOD_REGISTRY.get(name)
        if fn is None:
            continue
        
        # 实际统计量
        actual_stat = sum(s * s for s in scores)
        
        # 置换零分布
        null_stats = []
        for _ in range(n_perm):
            permuted_data = []
            for row in data:
                # 打乱红球
                all_nums = list(range(1, 34))
                random.shuffle(all_nums)
                new_reds = sorted(all_nums[:6])
                new_row = [row[0]] + new_reds + [row[7] if len(row) > 7 else row[6]]
                permuted_data.append(new_row)
            
            try:
                perm_scores = fn(permuted_data)
                perm_stat = sum(s * s for s in perm_scores)
                null_stats.append(perm_stat)
            except Exception:
                null_stats.append(0.0)
        
        # p-value
        null_stats.sort()
        right_tail = sum(1 for s in null_stats if s >= actual_stat) / n_perm
        p_val = max(right_tail, 1.0 / n_perm)
        
        p_values.append((name, p_val))
        detail[name] = {
            "actual_statistic": round(actual_stat, 4),
            "null_median": round(null_stats[n_perm // 2] if null_stats else 0, 4),
            "p_value": round(p_val, 4),
        }
    
    # BH过程
    significant, rejected = _benjamini_hochberg(p_values, alpha=alpha)
    
    return {
        "ok": True,
        "alpha": alpha,
        "n_permutations": n_perm,
        "significant_methods": significant,
        "rejected_methods": rejected,
        "detail": detail,
        "p_values": [{"name": n, "p": round(p, 4)} for n, p in sorted(p_values, key=lambda x: x[1])],
        "recommendation": (
            f"保留 {len(significant)}/{len(p_values)} 个方法 (FDR≤{alpha})"
            if significant else "所有方法均不显著 — 考虑更宽松的α或更大窗口"
        ),
    }
