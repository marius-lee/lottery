"""共现图 + 社区发现 — 超几何检验检测显著共现对 + Louvain 聚类

如果两个球在搅拌中因物理关联总是同时被推到出球口附近，
它们的共现频率应显著高于独立假设下的期望。
"""
import math
from collections import Counter, defaultdict


def _hypergeometric_pvalue(k, N, K, n):
    """超几何右尾概率 P(X >= k): 从 N 个球中抽 n 个, K 个为"成功".
    用正态近似。
    """
    if n == 0 or K == 0 or k <= 0:
        return 1.0
    mu = n * K / N
    sigma = math.sqrt(n * K / N * (N - K) / N * (N - n) / (N - 1)) if N > 1 else 0.01
    if sigma < 0.001:
        return 0.0 if k > mu else 1.0
    return 0.5 * math.erfc((k - mu) / (sigma * math.sqrt(2)))


def compute_cooccurrence(data, window=300, alpha=0.01):
    """构建 33×33 共现图, 只保留显著高共现边.

    Returns:
        edges: [(i, j, obs, expected, p_value), ...]  显著共现对
        communities: {node: community_id}  Louvain 聚类结果
        diagnostics: dict
    """
    recent = data[-window:] if len(data) > window else data
    T = len(recent)

    # 单球出现次数
    c = Counter()
    # 共现次数
    cooc = defaultdict(int)
    for row in recent:
        reds = row[1:7]
        for r in reds:
            c[r] += 1
        for i in range(5):
            for j in range(i + 1, 6):
                a, b = reds[i], reds[j]
                cooc[(min(a, b), max(a, b))] += 1

    # 超几何检验
    edges = []
    adj = defaultdict(set)
    for i in range(1, 33):
        for j in range(i + 1, 34):
            obs = cooc.get((i, j), 0)
            if obs == 0:
                continue
            # 超几何: N=总期数, K=c[i], n=6(每期抽6球), 但这不是标准超几何
            # 改为二项: 给定球 i 出现 c[i] 次, 在这些期中球 j 出现的次数
            # 期望: c[i] * (c[j]/T) * 6/33 ≈ c[i] * c[j] / T * 6/33
            # 更准确: 球 i 出现的期中, 剩余 5 个位置从 32 球中选, 球 j 被选概率 = 5/32
            expected = c[i] * 5.0 / 32.0  # 球i出现的期, 球j被同时选中的期望次数
            # 实际观察到的共现次数 obs
            p_val = _hypergeometric_pvalue(obs, T * 6, c[i], 5)
            # 用更精确的二项: ci 次出现, 每次从32球中选5个, 选到 j 的概率 = 5/32
            mu = c[i] * 5.0 / 32.0
            sigma = math.sqrt(c[i] * (5.0/32.0) * (27.0/32.0))
            if sigma > 0.001:
                z = (obs - mu) / sigma
                p_val = 0.5 * math.erfc(z / math.sqrt(2))
            else:
                p_val = 1.0

            if obs > expected and p_val < alpha:
                edges.append((i, j, obs, round(expected, 1), round(p_val, 6)))
                adj[i].add(j)
                adj[j].add(i)

    # Louvain 社区发现 (简化: 贪心模块度优化)
    communities = _louvain(adj)

    # 群组摘要
    groups = defaultdict(list)
    for node, cid in communities.items():
        groups[cid].append(node)

    return edges, communities, {
        "window": T,
        "n_edges": len(edges),
        "n_communities": len(groups),
        "communities": {str(k): sorted(v) for k, v in groups.items()},
        "top_edges": sorted(edges, key=lambda e: -e[2])[:10],
    }


def _louvain(adj):
    """简化 Louvain: 贪心模块度最大化, 单轮."""
    if not adj:
        return {}

    nodes = list(adj.keys())
    m = sum(len(neighbors) for neighbors in adj.values()) / 2  # 总边数
    if m == 0:
        return {n: i for i, n in enumerate(nodes)}

    # 度数
    k = {n: len(adj.get(n, set())) for n in nodes}

    # 初始化: 每个节点独立社区
    community = {n: i for i, n in enumerate(nodes)}
    # 社区内边数
    comm_edges = defaultdict(float)

    improved = True
    while improved:
        improved = False
        for n in nodes:
            old_comm = community[n]
            # 计算移到邻居社区后的模块度增益
            neighbor_comms = set(community[v] for v in adj.get(n, set()) if v != n)
            if not neighbor_comms:
                continue

            best_gain = 0
            best_comm = old_comm

            for new_comm in neighbor_comms:
                # 模块度增益 ΔQ = (Σ_in + 2k_i,in)/2m - ((Σ_tot + k_i)/2m)^2
                #                - [Σ_in/2m - (Σ_tot/2m)^2 - (k_i/2m)^2]
                # 简化: gain ≈ (k_i_in / m) - (k[n] * tot_weight / (2*m*m))
                # 这里用简化版本
                k_i_in = sum(1 for v in adj.get(n, set()) if community[v] == new_comm)
                gain = k_i_in / (2 * m) - k[n] * (k[n]) / (4 * m * m)
                if gain > best_gain:
                    best_gain = gain
                    best_comm = new_comm

            if best_comm != old_comm:
                community[n] = best_comm
                improved = True

    # 重新编号
    seen = {}
    result = {}
    for n in nodes:
        cid = community[n]
        if cid not in seen:
            seen[cid] = len(seen)
        result[n] = seen[cid]

    return result


# ═══ 红蓝共现 ═══

def compute_red_blue_cooccurrence(data, window=300, alpha=0.05):
    """33×16 红蓝共现检测: 某红球出现时, 蓝球b是否异常高共现.

    对每对 (red, blue), 二项检验 H₀: P(blue | red出现时) = 1/16.
    显著偏高 → 物理关联网红蓝耦合.

    Returns:
        pairs: [(red, blue, obs, expected, p_value), ...]  显著高共现对
        diagnostics: dict
    """
    recent = data[-window:] if len(data) > window else data
    T = len(recent)

    # 红球出现次数
    red_counts = Counter()
    # 红蓝共现次数
    rb_cooc = defaultdict(lambda: defaultdict(int))
    for row in recent:
        reds = row[1:7]
        blue = row[7]
        for r in reds:
            red_counts[r] += 1
            rb_cooc[r][blue] += 1

    # 二项检验: 红球 r 出现了 c[r] 次, 每次蓝球独立的 P(b) = 1/16
    nominal = 1.0 / 16.0  # 蓝球基线概率
    pairs = []
    for r in range(1, 34):
        cr = red_counts.get(r, 0)
        if cr < 20:
            continue
        expected = cr * nominal
        for b in range(1, 17):
            obs = rb_cooc[r].get(b, 0)
            if obs <= expected:
                continue
            # 二项右尾
            mu = cr * nominal
            sigma = math.sqrt(cr * nominal * (1 - nominal))
            if sigma < 0.001:
                p_val = 0.0 if obs > mu else 1.0
            else:
                z = (obs - mu) / sigma
                p_val = 0.5 * math.erfc(z / math.sqrt(2))
            if p_val < alpha:
                pairs.append((r, b, obs, round(expected, 1), round(p_val, 6)))

    pairs.sort(key=lambda x: x[4])  # 按p值排序

    return pairs, {
        "window": T,
        "n_pairs": len(pairs),
        "top_pairs": [(r, b, obs, round(p, 6)) for r, b, obs, _, p in pairs[:15]],
    }
