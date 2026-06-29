"""实验3: 反事实最近邻检验 — 相似历史是否预测相似未来

原理: 对每期开奖d_t, 在历史中找k个最相似期[d_a, d_b, d_c, ...],
比较它们的下一期[d_{a+1}, d_{b+1}, d_{c+1}, ...]与真实下一期d_{t+1}的相似度,
vs 随机基线(随机选k期的下一期).

如果 P(d_{t+1}|d_t相似的历史) > P(d_{t+1}) (随机基线),
则说明历史可以预测未来 → 序列有内存效应 → 非Markov.

距离度量:
  - 红球Jaccard距离: 1 - |A∩B|/|A∪B| = 1 - 交集/并集
  - 特征向量欧氏距离
  - 位置差绝对值之和

检验:
  配对t检验: H0: 最近邻相似度 = 随机相似度
  p < 0.01 → 拒绝H0 → 最近邻预测优于随机
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import random
import math


def load_data():
    from server.db import load_draws
    return load_draws()


# ═══════════════════════════════════════════════════════════════════
# 相似度度量
# ═══════════════════════════════════════════════════════════════════

def jaccard_sim(a_reds, b_reds):
    """Jaccard相似度: |A∩B| / |A∪B|."""
    inter = len(set(a_reds) & set(b_reds))
    union = len(set(a_reds) | set(b_reds))
    return inter / union if union > 0 else 0


def overlap_count(a_reds, b_reds):
    """直接的重叠数: |A∩B|."""
    return len(set(a_reds) & set(b_reds))


def blue_match(a_blue, b_blue):
    return 1 if a_blue == b_blue else 0


FEATURE_NAMES = ["和值", "跨度", "奇数比", "大号比", "质数比",
                 "012路和", "AC值", "蓝球", "最大间距", "重号比", "邻号比", "连号比"]
PRIMES = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31}


def extract_feature_vec(reds, blue, prev_reds=None):
    """提取单期12维特征."""
    s = sorted(reds)
    f_sum = sum(s)
    f_span = s[-1] - s[0]
    f_odd = sum(1 for r in s if r % 2 == 1)
    f_big = sum(1 for r in s if r >= 17)
    f_prime = sum(1 for r in s if r in PRIMES)
    f_mod3 = sum(r % 3 for r in s)
    f_ac = len({abs(s[j]-s[i]) for i in range(6) for j in range(i+1,6)}) - 5
    f_maxgap = max(s[j+1]-s[j] for j in range(5))
    f_consec = sum(1 for j in range(5) if s[j+1]-s[j]==1)

    if prev_reds:
        prev_set = set(prev_reds)
        f_repeat = len(set(s) & prev_set)
        f_neighbor = sum(1 for r in s if any(abs(r-p)==1 for p in prev_reds))
    else:
        f_repeat = 0
        f_neighbor = 0

    return [
        (f_sum-21)/(183-21), (f_span-5)/(32-5), f_odd/6, f_big/6,
        f_prime/6, f_mod3/12, f_ac/10, (blue-1)/15, (f_maxgap-1)/27,
        f_repeat/6, f_neighbor/6, f_consec/5,
    ]


def feature_dist(a_vec, b_vec):
    """欧氏距离."""
    return math.sqrt(sum((a-b)**2 for a, b in zip(a_vec, b_vec)))


# ═══════════════════════════════════════════════════════════════════
# 反事实检验
# ═══════════════════════════════════════════════════════════════════

def counterfactual_test(data, k=5, metric='jaccard'):
    """反事实最近邻检验.

    对每期t:
      1. 找t之前最相似的k期 (基于metric)
      2. 计算这k期的下一期与真实d_{t+1}的平均相似度 → 最近邻得分
      3. 随机选k期, 计算随机基线得分
      4. 比较

    Returns:
      {paired_results, mean_nn, mean_random, p_value, significant}
    """
    n = len(data)
    if n < 100:
        return {"error": f"数据不足 (n={n}<100)"}

    # 预计算所有红球和特征
    reds_list = [sorted(row[1:7]) for row in data]
    blues_list = [row[7] for row in data]
    feat_list = []
    for i, row in enumerate(data):
        prev = reds_list[i-1] if i > 0 else None
        feat_list.append(extract_feature_vec(reds_list[i], blues_list[i], prev))

    start = max(50, n // 4)  # [工程] 从第50期开始, 需要足够的历史
    nn_scores = []
    rand_scores = []

    for t in range(start, n - 1):
        # 候选: t之前的所有期 (排除最近5期避免时间相关性)
        candidates = [i for i in range(max(0, t - 5))]

        if len(candidates) < k:
            continue

        this_vec = feat_list[t] if metric == 'feature' else None

        # 找k个最近邻
        if metric == 'jaccard':
            scored = [(i, jaccard_sim(reds_list[i], reds_list[t])) for i in candidates]
            scored.sort(key=lambda x: -x[1])  # 降序, 高相似在前
        elif metric == 'overlap':
            scored = [(i, overlap_count(reds_list[i], reds_list[t])) for i in candidates]
            scored.sort(key=lambda x: -x[1])
        else:  # feature
            scored = [(i, -feature_dist(feat_list[i], this_vec)) for i in candidates]
            scored.sort(key=lambda x: -x[1])

        nn_indices = [i for i, _ in scored[:k]]

        # 最近邻得分: 这k期下一期与真实d_{t+1}的平均重叠
        nn_overlap = sum(overlap_count(reds_list[i+1], reds_list[t+1]) for i in nn_indices) / k
        nn_blue = sum(blue_match(blues_list[i+1], blues_list[t+1]) for i in nn_indices) / k
        nn_scores.append({"overlap": nn_overlap, "blue": nn_blue})

        # 随机基线: 随机选k期
        rand_indices = random.sample(candidates, min(k, len(candidates)))
        rand_overlap = sum(overlap_count(reds_list[i+1], reds_list[t+1]) for i in rand_indices) / k
        rand_blue = sum(blue_match(blues_list[i+1], blues_list[t+1]) for i in rand_indices) / k
        rand_scores.append({"overlap": rand_overlap, "blue": rand_blue})

    # 统计分析
    nn_ov = [s["overlap"] for s in nn_scores]
    rand_ov = [s["overlap"] for s in rand_scores]
    nn_bl = [s["blue"] for s in nn_scores]
    rand_bl = [s["blue"] for s in rand_scores]

    mean_nn = sum(nn_ov) / len(nn_ov)
    mean_rand = sum(rand_ov) / len(rand_ov)
    diff = mean_nn - mean_rand

    # 配对t检验
    diffs_ov = [a - b for a, b in zip(nn_ov, rand_ov)]
    mean_diff = sum(diffs_ov) / len(diffs_ov)
    sd_diff = math.sqrt(sum((d - mean_diff)**2 for d in diffs_ov) / (len(diffs_ov) - 1))
    t_stat = mean_diff / (sd_diff / math.sqrt(len(diffs_ov))) if sd_diff > 0 else 0

    # [统计] 自由度=n-1, t临界值: α=0.01单尾≈2.33, α=0.05单尾≈1.65
    # n_samples > 200 → t≈1.65
    t_critical_05 = 1.65
    t_critical_01 = 2.33
    significant = t_stat > t_critical_01

    # 蓝球
    mean_nn_blue = sum(nn_bl) / len(nn_bl)
    mean_rand_blue = sum(rand_bl) / len(rand_bl)

    return {
        "samples": len(nn_scores),
        "metric": metric,
        "k": k,
        "mean_nn_overlap": round(mean_nn, 4),
        "mean_random_overlap": round(mean_rand, 4),
        "delta": round(diff, 4),
        "delta_pct": round(diff / (mean_rand or 0.01) * 100, 1),
        "t_statistic": round(t_stat, 3),
        "significant_01": significant,
        "significant_05": t_stat > t_critical_05,
        "nn_blue_hit_rate": round(mean_nn_blue, 4),
        "random_blue_hit_rate": round(mean_rand_blue, 4),
        "verdict": ("⚠️  显著 — 历史相似期可预测未来"
                    if significant else
                    ("弱信号 — 但未达p<0.01" if t_stat > t_critical_05
                     else "无预测力 — 相似历史不预示相似未来")),
    }


# ═══════════════════════════════════════════════════════════════════
# 主函数
# ═══════════════════════════════════════════════════════════════════

def run():
    data = load_data()
    n = len(data)

    print(f"=" * 60)
    print(f"实验3: 反事实最近邻检验")
    print(f"=" * 60)
    print(f"数据: {n} 期")
    print(f"假设H0: 相似历史的下一期相似度 = 随机基线相似度")
    print(f"假设H1: 相似历史的下一期相似度 > 随机基线 (单尾)")
    print()

    metrics = ["jaccard", "overlap", "feature"]
    ks = [3, 5, 10]

    for metric in metrics:
        print(f"  ── 度量: {metric} ──")
        for k in ks:
            result = counterfactual_test(data, k=k, metric=metric)
            if "error" in result:
                print(f"    k={k}: {result['error']}")
                continue
            sig = "***" if result["significant_01"] else ("*" if result["significant_05"] else "")
            print(f"    k={k}: 最近邻={result['mean_nn_overlap']:.3f} | "
                  f"随机={result['mean_random_overlap']:.3f} | "
                  f"Δ={result['delta']:+.4f} ({result['delta_pct']:+.0f}%) | "
                  f"t={result['t_statistic']:.2f}{sig} | "
                  f"蓝球NN={result['nn_blue_hit_rate']:.3f} vs 随机={result['random_blue_hit_rate']:.3f}")
        print()

    # 综合best result
    best = None
    for metric in metrics:
        r = counterfactual_test(data, k=5, metric=metric)
        if "error" not in r and (best is None or r["t_statistic"] > best["t_statistic"]):
            best = r

    print(f"{'─' * 60}")
    if best and best["significant_05"]:
        print(f"判定: ⚠️  反事实预测有效 (best: {best['metric']}, k=5, Δ={best['delta']:+.4f})")
        print(f"  → 历史真的在重复, 不是幻觉")
        print(f"  → 最近邻选号器本身就是一个可用策略")
    else:
        print(f"判定: 无显著反事实预测力")
        print(f"  → 彩票序列像是Markov/独立过程")
        print(f"  → 时序记忆可能不存在")
    print(f"{'─' * 60}")

    return best


if __name__ == "__main__":
    run()
