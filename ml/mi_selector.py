"""互信息熵值选号 — 检测红球号码间的非独立结构

原 mi_detector.py 是独立脚本, 本模块硬化为可调用的评分函数.

用途:
  计算每对号码 (i,j) 的互信息 MI(i,j) = Σ p(i,j) × log[p(i,j) / (p(i)×p(j))]
  然后用bootstrap检验哪些对显著偏离独立性.
  显著偏离独立性的号码对 → 如果同时出现, 应一起覆盖.

数学:
  MI ≥ 0, MI=0 当且仅当 i,j 独立.
  bootstrap: 洗牌破坏关联, 计算空分布, 0.5分位数以上的MI为显著.

返回:
  显著互信息号码对的列表, 可用于指导覆盖设计.
"""
import math
from collections import Counter, defaultdict
from typing import List, Dict, Tuple


def compute_cooccurrence(data):
    """计算33×33共现矩阵."""
    n = len(data)
    counts = defaultdict(int)
    single = Counter()

    for row in data:
        reds = row[1:7]
        for r in reds:
            single[r] += 1
        for i in range(len(reds)):
            for j in range(i+1, len(reds)):
                a, b = sorted([reds[i], reds[j]])
                counts[(a, b)] += 1

    return dict(counts), dict(single), n


def mutual_information(n_ij, n_i, n_j, n_total):
    """一对号码的互信息."""
    if n_total <= 0 or n_i <= 0 or n_j <= 0 or n_ij <= 0:
        return 0.0

    p_ij = n_ij / n_total
    p_i = n_i / n_total
    p_j = n_j / n_total

    if p_ij == 0 or p_i == 0 or p_j == 0:
        return 0.0

    return p_ij * math.log(p_ij / (p_i * p_j))


def compute_all_mi(data):
    """计算所有号码对的互信息.

    Returns:
        [(num1, num2, mi, cooccur_count), ...] sorted by MI desc
    """
    pair_counts, single_counts, n = compute_cooccurrence(data)
    results = []

    for (a, b), n_ij in pair_counts.items():
        mi = mutual_information(n_ij, single_counts.get(a, 0),
                                single_counts.get(b, 0), n)
        results.append((a, b, mi, n_ij))

    results.sort(key=lambda x: -x[2])
    return results


def bootstrap_mi_threshold(data, n_bootstrap=200, alpha=0.05):
    """Bootstrap估计MI显著阈值: 洗牌破坏关联 → 空分布 → 95%分位数."""
    import random
    rng = random.Random(42)

    null_mis = []
    n = len(data)
    all_reds = []
    for row in data:
        all_reds.extend(row[1:7])

    for _ in range(n_bootstrap):
        rng.shuffle(all_reds)
        # 重建伪开奖数据
        shuffled_data = []
        for _ in range(n):
            shuffled_data.append(
                [0] + sorted(rng.sample(range(1, 34), 6)) + [0]
            )
        all_mis = compute_all_mi(shuffled_data)
        if all_mis:
            null_mis.append(all_mis[0][2])

    null_mis.sort()
    threshold = null_mis[int(len(null_mis) * (1 - alpha))] if null_mis else 0.0
    return threshold, null_mis


def significant_pairs(data, n_bootstrap=200, alpha=0.05, top_k=20):
    """找出互信息显著高于随机的号码对.

    Returns:
        {"significant": [(a,b,mi,cooccur),...], "threshold": threshold, ...}
    """
    all_mi = compute_all_mi(data)
    threshold, null_dist = bootstrap_mi_threshold(data, n_bootstrap, alpha)

    sig = [(a, b, round(mi, 6), cooc)
           for a, b, mi, cooc in all_mi[:top_k]
           if mi > threshold]

    return {
        "significant_pairs": sig,
        "mi_threshold": round(threshold, 6),
        "n_bootstrap": n_bootstrap,
        "alpha": alpha,
        "top_all": [(a, b, round(mi, 6), cooc) for a, b, mi, cooc in all_mi[:10]],
        "interpretation": (
            f"{len(sig)}对号码的互信息显著高于Bootstrap空分布: "
            "这些号码对有非独立共现趋势, 应在覆盖设计中考虑"
            if sig else
            "无显著非独立号码对 — 号码间无结构化依赖, 均匀覆盖即可"
        ),
        "reference": "Cover & Thomas 2006, 'Elements of Information Theory' 2nd ed.",
    }


def mi_based_hot_boost(data, k=15, mi_weight=0.2):
    """用互信息增强频率评分: 不仅出现频率高, 且与高频号有互信息的号码加权.

    Returns:
        [(num, boosted_score), ...] 排序
    """
    all_mi = compute_all_mi(data)
    single = Counter()
    for row in data:
        for r in row[1:7]:
            single[r] += 1
    n = len(data)

    # 频率分数
    freq_scores = {r: single.get(r, 0) / (n * 6 / 33) for r in range(1, 34)}

    # 互信息分数: 与至少K个其他号码有显著MI的号码 → 加权
    mi_boost = defaultdict(float)
    for a, b, mi, _ in all_mi:
        mi_boost[a] += mi
        mi_boost[b] += mi

    # 归一化
    max_mi = max(mi_boost.values()) if mi_boost else 1.0
    mi_scores = {r: mi_boost.get(r, 0) / max(max_mi, 0.01) for r in range(1, 34)}

    # 融合
    boosted = {}
    for r in range(1, 34):
        boosted[r] = freq_scores.get(r, 1.0) * (1 - mi_weight) + mi_scores.get(r, 0) * mi_weight

    return sorted(boosted.items(), key=lambda x: -x[1])[:k]


def select_by_mi(data, k=15):
    """纯互信息驱动选号: 选互信息连接最多的k个号码."""
    all_mi = compute_all_mi(data)
    degree = defaultdict(int)
    for a, b, mi, _ in all_mi:
        degree[a] += 1
        degree[b] += 1

    return sorted(degree.items(), key=lambda x: -x[1])[:k]
