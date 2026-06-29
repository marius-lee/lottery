"""条件熵号码池 — 5-gram 转移概率 + 条件熵 + 互信息聚类

不预测号码。只做一件事: 识别"历史规律最强的号码"。
- 条件熵 H(ball_t | context): 给定最近 N 期上下文, 号码的不确定性
- 熵最低 = 历史规律最强 = 最受历史约束
- 如果开奖是真随机, 所有号码条件熵相同 → 选任何子集都一样
- 如果开奖有任何结构性, 条件熵会指出哪些号码更可预测

结合前面 NIST 的结果: NIST 检测全局偏倚, 条件熵检测局部规律。
"""
import math
from typing import List, Dict, Tuple, Set, Optional
from collections import Counter, defaultdict
from dataclasses import dataclass


@dataclass
class CondEntropyResult:
    """条件熵分析结果."""
    ok: bool = True
    red_entropies: Dict[int, float] = None   # {号码: 条件熵} 越低越好
    blue_entropies: Dict[int, float] = None  # {号码: 条件熵}
    red_top15: List[int] = None              # 熵最低的15个红球
    blue_top6: List[int] = None              # 熵最低的6个蓝球
    red_clusters: List[List[int]] = None     # 基于MI的号码聚类
    baseline_entropy: float = 0.0            # 均权基线熵
    entropy_reduction_pct: float = 0.0       # 熵降低百分比

    def __post_init__(self):
        if self.red_entropies is None:
            self.red_entropies = {}
        if self.blue_entropies is None:
            self.blue_entropies = {}
        if self.red_top15 is None:
            self.red_top15 = []
        if self.blue_top6 is None:
            self.blue_top6 = []


# ═══════════════════════════════════════════════════════════
# 条件熵计算: H(Y | X) 对 5-gram 上下文
# ═══════════════════════════════════════════════════════════

def _build_5gram_contexts(data, window=5):
    """构建红球+蓝球的 5-gram 转移矩阵.

    对每个号码 n:
      上下文 = 最近 window 期内号码 n 出现与否的向量
      目标   = 下期号码 n 是否出现

    返回 {n: [(context_tuple, target), ...]}.
    """
    total = len(data)
    if total < window + 2:
        return {}, {}

    red_contexts = {n: [] for n in range(1, 34)}
    blue_contexts = {n: [] for n in range(1, 17)}

    for t in range(window, total - 1):
        for n in range(1, 34):
            ctx = tuple(
                1 if n in data[t - window + i][1:7] else 0
                for i in range(window)
            )
            target = 1 if n in data[t + 1][1:7] else 0
            red_contexts[n].append((ctx, target))

        for n in range(1, 17):
            ctx = tuple(
                1 if data[t - window + i][7] == n else 0
                for i in range(window)
            )
            target = 1 if data[t + 1][7] == n else 0
            blue_contexts[n].append((ctx, target))

    return red_contexts, blue_contexts


def _conditional_entropy(samples: List[Tuple[tuple, int]]) -> float:
    """计算条件熵 H(Y | X).

    H(Y|X) = - Σ_x P(x) Σ_y P(y|x) log P(y|x)
    """
    if not samples:
        return 0.0

    # 按上下文分组
    ctx_groups = defaultdict(lambda: [0, 0])  # [count_0, count_1]
    for ctx, target in samples:
        ctx_groups[ctx][target] += 1

    total = len(samples)
    entropy = 0.0

    for ctx, (cnt0, cnt1) in ctx_groups.items():
        total_ctx = cnt0 + cnt1
        if total_ctx == 0:
            continue
        p_ctx = total_ctx / total
        # H(Y | X=c)
        p0 = cnt0 / total_ctx
        p1 = cnt1 / total_ctx
        h_ctx = 0.0
        if p0 > 0:
            h_ctx -= p0 * math.log2(p0)
        if p1 > 0:
            h_ctx -= p1 * math.log2(p1)
        entropy += p_ctx * h_ctx

    return entropy


def _compute_red_mi_matrix(data, window=20):
    """计算红球对之间的互信息矩阵 (对称)."""
    total = len(data)
    if total < window + 2:
        return {}

    mi_matrix = {}
    for n1 in range(1, 34):
        for n2 in range(n1 + 1, 34):
            # 计数联合出现
            joint = [[0, 0], [0, 0]]  # [n1=0][n2=0], [n1=0][n2=1], ...
            for t in range(total - 1):
                a = 1 if n1 in data[t + 1][1:7] else 0
                b = 1 if n2 in data[t + 1][1:7] else 0
                joint[a][b] += 1
            N = sum(sum(row) for row in joint)
            if N == 0:
                continue
            # 互信息
            p_a = [(joint[0][0] + joint[0][1]) / N, (joint[1][0] + joint[1][1]) / N]
            p_b = [(joint[0][0] + joint[1][0]) / N, (joint[0][1] + joint[1][1]) / N]
            mi = 0.0
            for i in range(2):
                for j in range(2):
                    p_ab = joint[i][j] / N
                    if p_ab > 0 and p_a[i] > 0 and p_b[j] > 0:
                        mi += p_ab * math.log2(p_ab / (p_a[i] * p_b[j]))
            mi_matrix[(n1, n2)] = mi

    return mi_matrix


def _hierarchical_cluster(mi_matrix, n_clusters=5):
    """基于互信息对号码做层次聚类."""
    if not mi_matrix:
        return [[i] for i in range(1, 34)]  # 回退: 每个号码独自一簇

    # 初始: 每个号码一个簇
    clusters = [{n} for n in range(1, 34)]
    cluster_sets = [set(range(1, 34))] + [{n} for n in range(1, 34)]  # dummy

    # 用 MI 做凝聚聚类: 重复合并最"相关"的簇
    while len(clusters) > n_clusters:
        best_mi = -1
        best_pair = (-1, -1)
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                # 簇间平均MI
                mi_sum = 0
                cnt = 0
                for n1 in clusters[i]:
                    for n2 in clusters[j]:
                        key = (min(n1, n2), max(n1, n2))
                        mi_sum += mi_matrix.get(key, 0)
                        cnt += 1
                if cnt > 0 and mi_sum / cnt > best_mi:
                    best_mi = mi_sum / cnt
                    best_pair = (i, j)

        if best_pair[0] < 0:
            break
        i, j = best_pair
        clusters[i] = clusters[i] | clusters[j]
        del clusters[j]

    # 平铺为列表
    cluster_lists = [sorted(list(c)) for c in clusters]
    cluster_lists.sort(key=lambda c: -sum(n in c for n in range(1, 34)))
    return cluster_lists


# ═══════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════

def analyze_conditional_entropy(data, n_red=15, n_blue=6, ngram=5) -> CondEntropyResult:
    """主入口: 计算条件熵 + 互信息 + 聚类.

    Args:
        data: [[period, r1..r6, blue], ...]
        n_red: 需要的红球数 (默认15)
        n_blue: 需要的蓝球数 (默认6)
        ngram: 上下文窗口大小

    Returns:
        CondEntropyResult with entropies, top picks, clusters
    """
    result = CondEntropyResult()
    if len(data) < ngram + 5:
        result.ok = False
        return result

    # 构建上下文
    red_ctx, blue_ctx = _build_5gram_contexts(data, ngram)

    # 计算各号码条件熵
    red_entropies = {}
    for n, samples in red_ctx.items():
        if samples:
            red_entropies[n] = _conditional_entropy(samples)
    blue_entropies = {}
    for n, samples in blue_ctx.items():
        if samples:
            blue_entropies[n] = _conditional_entropy(samples)

    result.red_entropies = red_entropies
    result.blue_entropies = blue_entropies

    # 基线熵: H(Y) 边缘熵 (零阶)
    red_total = len(data)
    red_freq = Counter()
    for row in data:
        for n in row[1:7]:
            red_freq[n] += 1
    baseline_h = 0.0
    for n in range(1, 34):
        p = red_freq.get(n, 0) / max(1, red_total)
        if p > 0:
            baseline_h -= p * math.log2(p)
    result.baseline_entropy = round(baseline_h, 4)

    # 选熵最低的号码
    sorted_red = sorted(red_entropies.items(), key=lambda x: x[1])[:n_red]
    result.red_top15 = [n for n, _ in sorted_red]

    sorted_blue = sorted(blue_entropies.items(), key=lambda x: x[1])[:n_blue]
    result.blue_top6 = [n for n, _ in sorted_blue]

    # 熵降低
    if result.red_top15:
        avg_cond_entropy = sum(red_entropies[n] for n in result.red_top15) / len(result.red_top15)
        result.entropy_reduction_pct = round(
            (1 - avg_cond_entropy / max(0.001, baseline_h)) * 100, 1
        )

    # 互信息聚类
    mi_matrix = _compute_red_mi_matrix(data)
    result.red_clusters = _hierarchical_cluster(mi_matrix, n_clusters=5)

    return result


def entropy_blue_candidates(data, n=6) -> set:
    """用条件熵选蓝球候选集 — 替代简单频率 top-6.

    如果熵降低显著 (>5%), 返回条件熵top-N.
    否则回退到频率 top-N (等同于均权 — 无信息可提取).
    """
    result = analyze_conditional_entropy(data, n_red=15, n_blue=n)
    if not result.ok or result.entropy_reduction_pct < 5:
        # 回退: 零阶频率
        from collections import Counter
        cnt = Counter()
        for row in data:
            cnt[row[7]] += 1
        return {n for n, _ in cnt.most_common(n)}

    return set(result.blue_top6)
