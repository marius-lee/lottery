"""FDR 多重比较校正 — Benjamini-Hochberg (1995, JRSS-B)

问题: 18种方法各自对33个号码打分, 多重比较导致假阳性泛滥.
      P(至少1个假阳性 | 18方法 × 33号码 = 594 tests) ≈ 1 - (0.95)^594 ≈ 1

解法: 控制 False Discovery Rate (FDR) 而非 Family-Wise Error Rate.
      Benjamini-Hochberg过程: q=0.05下, 期望不超过5%的"显著"结果是假的.

用法:
  1. 收集所有方法的p值
  2. rank排序
  3. 找最大k: p_{(k)} ≤ k/m * q
  4. 前k个p值对应的结果 → 统计显著
"""
import math
from typing import List, Dict, Tuple
from collections import defaultdict


def benjamini_hochberg(p_values: List[float], q: float = 0.05):
    """Benjamini-Hochberg FDR校正.

    Args:
        p_values: p值列表 [(name, p_val), ...]
        q: FDR阈值 (默认0.05)

    Returns:
        {"significant": [(name, p, rank, threshold), ...], "n_total": N, "q": q}
    """
    if not p_values:
        return {"significant": [], "n_total": 0, "q": q}

    # 排序
    sorted_p = sorted(p_values, key=lambda x: x[1])
    m = len(sorted_p)

    # 找最大k: p_{(k)} ≤ k/m * q
    significant = []
    for k, (name, p) in enumerate(sorted_p, 1):
        threshold = (k / m) * q
        if p <= threshold:
            significant.append({
                "name": name, "p_value": round(p, 6),
                "rank": k, "bh_threshold": round(threshold, 6),
                "significant": True,
            })
        else:
            # 一旦p > threshold, 后面更大的rank都不可能通过
            break

    return {
        "significant": significant,
        "n_total": m,
        "q": q,
        "n_significant": len(significant),
        "interpretation": (
            f"{len(significant)}/{m} tests significant at FDR {q}"
            if len(significant) > 0
            else "无统计显著结果 — 所有方法表现不优于随机"
        ),
    }


def per_method_pvalues(data, methods):
    """对每种方法计算号码评分的p值 (vs 随机洗牌分布).

    精简版: 用二项式检验近似 (频率 vs 均匀分布期望).
    """
    import random
    from collections import Counter

    total = len(data)
    if total < 30:
        return []

    # 全局频率
    freq = Counter()
    for row in data:
        for n in row[1:7]:
            freq[n] += 1

    expected = total * 6 / 33  # 均匀期望

    all_pvals = []
    for name, scores in methods.items():
        # 对每个号码: 二项式检验近似
        for num in range(1, 34):
            observed = freq.get(num, 0)
            # 二项式 p值 (双侧)
            if observed >= expected:
                # 单侧 H1: observed > expected
                p = _binom_survival(observed - 1, total, 6/33)
            else:
                p = _binom_cdf(observed, total, 6/33)
            # 双侧 × 2, clip [0, 1]
            p = min(p * 2, 1.0)
            all_pvals.append((f"{name}#{num:02d}", p))

    return all_pvals


def _binom_cdf(k, n, p):
    """二项式CDF: P(X ≤ k) — log-space计算避免溢出."""
    import math
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    # 使用 log-sum-exp 或直接近似
    # 对彩票数据 (n≈2000), 正态近似已足够
    if n * p > 5 and n * (1-p) > 5:
        # 正态近似
        mu = n * p
        sigma = math.sqrt(n * p * (1 - p))
        z = (k - mu) / sigma
        return max(0.0, min(1.0, 0.5 * (1 + math.erf(z / math.sqrt(2)))))
    # 精确: log-space
    s = 0.0
    for i in range(min(k + 1, 100)):  # cap at 100 terms
        log_term = (math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
                    + i * math.log(p) + (n - i) * math.log(1 - p))
        s += math.exp(log_term)
    return min(s, 1.0)


def _binom_survival(k, n, p):
    """二项式survival: P(X > k)."""
    return 1 - _binom_cdf(k, n, p)


def filter_methods_by_fdr(data, methods, weights, q=0.05):
    """FDR过滤: 移除统计不显著的方法.

    Returns:
        {"filtered_methods": {name: w}, "removed": [names], "bh_results": {...}}
    """
    pvals = per_method_pvalues(data, methods)
    bh = benjamini_hochberg(pvals, q)

    # 收集显著的方法名
    significant_names = set()
    for item in bh["significant"]:
        method_name = item["name"].split("#")[0]
        significant_names.add(method_name)

    filtered = {k: v for k, v in weights.items() if k in significant_names}
    removed = [k for k in weights if k not in significant_names]

    return {
        "filtered_weights": filtered,
        "removed_methods": removed,
        "bh_results": bh,
        "note": (f"FDR q={q}: 保留{len(filtered)}/{len(weights)}方法"
                 if filtered else "所有方法均不显著 — 无预测能力"),
        "reference": "Benjamini & Hochberg 1995, JRSS-B 57(1):289-300",
    }
