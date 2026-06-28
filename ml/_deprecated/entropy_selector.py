"""熵值驱动的号码选择器 — 用互信息替代简单频率基线.

互信息 (MI) 已在 mi_detector.py 中计算为号码对依赖检测.
本模块将其扩展为: 用条件熵和联合熵给号码评分.

核心思想:
  - 简单频率: score(n) = P(n出现的次数)  # 边际统计, 忽略依赖
  - 互信息评分: score(n) = Σ_j MI(n, j)   # 考虑号码间依赖结构
  - 条件熵评分: score(n) = H(n | context)  # 给定已知条件, 号码的不确定性

三个评分来源:
  1. MI-sum: 号码与所有其他号码的互信息之和 (结构信号)
  2. Conditional Entropy: 给定近期出现的号码, 该号码的条件熵
  3. Composite: 归一化后的加权组合

用法:
  from ml.entropy_selector import run_entropy_selector
  result = run_entropy_selector()
  # result["hotness"]: [{num, mi_score, cond_score, composite}, ...]
"""
import math
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, Counter


def _compute_mi_matrix(data) -> Dict[Tuple[int, int], float]:
    """计算所有号码对的互信息矩阵 (C(33,2)=528对).
    
    使用与 mi_detector.py 相同的2×2列联表方法.
    """
    n = len(data)
    # 共现计数
    pair_counts = defaultdict(int)
    single_counts = Counter()
    
    for row in data:
        reds = sorted(row[1:7])
        for n in reds:
            single_counts[n] += 1
        for a in range(6):
            for b in range(a + 1, 6):
                pair_counts[(reds[a], reds[b])] += 1
    
    mi_matrix = {}
    for i in range(1, 34):
        for j in range(i + 1, 34):
            n_ij = pair_counts.get((i, j), 0)
            n_i = single_counts.get(i, 0)
            n_j = single_counts.get(j, 0)
            
            if n_i == 0 or n_j == 0 or n_ij == 0:
                mi_matrix[(i, j)] = 0.0
                continue
            
            # 2×2列联表MI
            cells = [
                (n_ij, n_i / n, n_j / n),
                (n_i - n_ij, n_i / n, (n - n_j) / n),
                (n_j - n_ij, (n - n_i) / n, n_j / n),
                (n - n_i - n_j + n_ij, (n - n_i) / n, (n - n_j) / n),
            ]
            
            mi = 0.0
            for cell_count, px, py in cells:
                if cell_count <= 0:
                    continue
                p_xy = cell_count / n
                ratio = p_xy / max(px * py, 1e-10)
                if ratio > 0:
                    mi += p_xy * math.log2(ratio)
            
            mi_matrix[(i, j)] = mi
    
    return mi_matrix, single_counts


def _conditional_entropy(num: int, context_nums: List[int],
                        mi_matrix: Dict[Tuple[int, int], float],
                        single_counts: Counter, n_data: int) -> float:
    """条件熵: H(num | context).
    
    近似: H(num | context) = H(num) - I(num; context)
    其中 I(num; context) = 互信息与上下文的最近似 = Σ_j MI(num, j) for j in context
    """
    n_i = single_counts.get(num, 0)
    if n_i == 0:
        return 1.0  # 最大熵
    
    p = n_i / n_data
    H_marginal = -p * math.log2(p) - (1 - p) * math.log2(1 - p) if 0 < p < 1 else 0.0
    
    # 互信息与上下文的近似
    I_cond = 0.0
    for ctx in context_nums:
        key = (min(num, ctx), max(num, ctx))
        I_cond += mi_matrix.get(key, 0.0)
    
    # H(num | context) = H(num) - I(num; context)
    # 但I不超过H
    H_cond = max(0.0, H_marginal - I_cond)
    return H_cond


def run_entropy_selector(window: int = 200) -> dict:
    """运行熵值号码选择.
    
    Args:
        window: 分析窗口期数
        
    Returns:
        dict with hotness rankings, mi_sum scores, conditional entropy scores
    """
    from server import db
    data = db.load_draws()
    if len(data) < window:
        window = len(data)
    
    subset = data[-window:]
    n_data = len(subset)
    
    # 计算MI矩阵
    mi_matrix, single_counts = _compute_mi_matrix(subset)
    
    # 上下文: 最近一期的红球号码
    last_row = subset[-1]
    context = set(last_row[1:7])
    
    # 为每个号码计算三个评分
    results = []
    for num in range(1, 34):
        n_i = single_counts.get(num, 0)
        freq_score = n_i / n_data if n_data > 0 else 0.0
        
        # MI-sum: 与所有号码的互信息总和
        mi_sum = 0.0
        for other in range(1, 34):
            if other != num:
                key = (min(num, other), max(num, other))
                mi_sum += mi_matrix.get(key, 0.0)
        
        # 条件熵: 给定上下文的熵 (越低越确定)
        cond_ent = _conditional_entropy(num, list(context), mi_matrix, single_counts, n_data)
        
        # 合成评分: 
        #   高MI-sum + 低条件熵 + 高频率 → 热号
        #   归一化到 [0, 1]
        results.append({
            "num": num,
            "freq": round(freq_score, 4),
            "mi_sum": round(mi_sum, 6),
            "cond_entropy": round(cond_ent, 6),
        })
    
    # 归一化各维度
    mi_max = max(r["mi_sum"] for r in results) or 1.0
    ent_max = max(r["cond_entropy"] for r in results) or 1.0
    ent_min = min(r["cond_entropy"] for r in results) or 0.0
    ent_range = max(ent_max - ent_min, 0.001)
    
    for r in results:
        mi_norm = r["mi_sum"] / mi_max
        ent_norm = 1.0 - (r["cond_entropy"] - ent_min) / ent_range  # 熵越低→分数越高
        freq_norm = r["freq"] / max(max(r_["freq"] for r_ in results), 0.001)
        
        # 加权: MI 0.3 + 条件熵 0.4 + 频率 0.3
        composite = 0.3 * mi_norm + 0.4 * ent_norm + 0.3 * freq_norm
        r["composite"] = round(composite, 4)
    
    # 排序
    ranked = sorted(results, key=lambda r: -r["composite"])
    
    return {
        "ok": True,
        "window": window,
        "n_data": n_data,
        "context": sorted(list(context)),
        "hotness": ranked,
        "top_6": [{"num": r["num"], "composite": r["composite"]} for r in ranked[:6]],
        "top_15": [r["num"] for r in ranked[:15]],
        "summary": {
            "avg_mi": round(sum(r["mi_sum"] for r in results) / 33, 6),
            "structural_signal": (
                "依赖结构存在" if sum(r["mi_sum"] for r in results) / 33 > 0.001
                else "近似独立"
            ),
        },
    }
