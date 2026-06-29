"""实验2: Takens时延嵌入 + 假近邻法 — 检测确定性吸引子

原理: 混沌动力系统的状态空间可以从单变量时间序列重建 (Takens 1981).
假近邻法 (FNN, Kennel+1992) 判断重建需要多少维度.

判定:
  - 嵌入维度 m < 8 且 FNN < 5% → 低维确定性系统
  - 嵌入维度 m → ∞ (FNN始终>10%) → 真随机/高维噪声
  - m在8-15之间 → 可能有结构但噪声大

特征提取:
  每期开奖 → 多维特征向量:
    f0: 红球和值 (21-183)
    f1: 红球跨度 (max-min)
    f2: 奇偶比 (0-6)
    f3: 大小比 (≥17计数)
    f4: 质数个数
    f5: 012路模数之和
    f6: AC值
    f7: 蓝球值 (1-16)
    f8: 最大间距
    f9: 重号数(与上期)
    f10: 邻号数(与上期)
    f11: 连号数

参考:
  Kennel, Brown & Abarbanel (1992): "Determining embedding dimension
    for phase-space reconstruction using a geometrical construction."
  Cao (1997): "Practical method for determining the minimum embedding
    dimension of a scalar time series."
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import math
import random


def load_data():
    from server.db import load_draws
    return load_draws()


# ═══════════════════════════════════════════════════════════════════
# 特征提取
# ═══════════════════════════════════════════════════════════════════

PRIMES = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31}


def extract_features(data):
    """每期提取12维特征向量, 所有值归一化到[0,1]."""
    features = []
    for i, row in enumerate(data):
        reds = sorted(row[1:7])
        blue = row[7]

        f_sum = sum(reds)                                    # 和值 21-183
        f_span = reds[-1] - reds[0]                           # 跨度 5-32
        f_odd = sum(1 for r in reds if r % 2 == 1)           # 奇数个数
        f_big = sum(1 for r in reds if r >= 17)              # 大号个数
        f_prime = sum(1 for r in reds if r in PRIMES)        # 质数个数
        f_mod3 = sum(r % 3 for r in reds)                    # 012路和
        f_ac = _ac_value(reds)                                # AC值 0-10
        f_maxgap = max(reds[j+1] - reds[j] for j in range(5))  # 最大间距
        f_consec = sum(1 for j in range(5) if reds[j+1] - reds[j] == 1)  # 连号数

        # 与上期的关系
        if i > 0:
            prev_reds = set(data[i-1][1:7])
            f_repeat = len(set(reds) & prev_reds)            # 重号数 0-6
            prev_reds_list = sorted(data[i-1][1:7])
            f_neighbor = sum(1 for r in reds
                           if any(abs(r - p) == 1 for p in prev_reds_list))  # 邻号数
        else:
            f_repeat = 0
            f_neighbor = 0

        # 归一化
        vec = [
            (f_sum - 21) / (183 - 21),           # f0: 和值
            (f_span - 5) / (32 - 5),              # f1: 跨度
            f_odd / 6,                            # f2: 奇数比
            f_big / 6,                            # f3: 大号比
            f_prime / 6,                          # f4: 质数比
            f_mod3 / 12,                          # f5: 012路和 (max 12)
            f_ac / 10,                            # f6: AC值
            (blue - 1) / 15,                      # f7: 蓝球
            (f_maxgap - 1) / 27,                 # f8: 最大间距
            f_repeat / 6,                         # f9: 重号比
            f_neighbor / 6,                       # f10: 邻号比
            f_consec / 5,                         # f11: 连号比
        ]
        features.append(vec)

    return features


def _ac_value(reds):
    """AC值 (算术复杂性) — 简化计算."""
    diffs = set()
    for i in range(6):
        for j in range(i + 1, 6):
            diffs.add(abs(reds[j] - reds[i]))
    return len(diffs) - 5  # AC = 差值种类数 - (r-1), r=6


# ═══════════════════════════════════════════════════════════════════
# Takens时延嵌入
# ═══════════════════════════════════════════════════════════════════

def time_delay_embed(series, dim, delay=1):
    """时延嵌入: 单变量 → dim维向量.

    series: 时间序列 [x1, x2, ..., xN]
    返回: [(x_t, x_{t-delay}, ..., x_{t-(dim-1)delay}), ...]
    """
    n = len(series)
    vectors = []
    start = (dim - 1) * delay
    for t in range(start, n):
        vec = [series[t - k * delay] for k in range(dim)]
        vectors.append(vec)
    return vectors


def false_nearest_neighbors(series, max_dim=15, delay=1, rtol=15.0, atol=2.0):
    """假近邻法 (FNN) — 对每个嵌入维计算FNN比例.

    Args:
        series: 单变量时间序列
        max_dim: 最大检测维度
        delay: 时延
        rtol: 相对距离容限 [文献] Kennel+1992建议15.0
        atol: 绝对距离容限 [文献] Kennel+1992建议2.0

    Returns:
        {dim: fnn_ratio} — 每个维度的假近邻比例
    """
    n = len(series)
    fnn_ratios = {}

    for dim in range(1, max_dim + 1):
        # 嵌入到 dim 维
        vecs = time_delay_embed(series, dim, delay)
        m = len(vecs)
        if m < 50:  # [工程] 至少50个点才能可靠估计
            fnn_ratios[dim] = None
            continue

        # 找每个点的最近邻
        false_count = 0
        total_count = min(m, 500)  # [工程] 采样500点, M1 8G友好
        sample_indices = random.sample(range(m), total_count)

        for i in sample_indices:
            vi = vecs[i]
            # 排除时间上太近的点 [文献] 排除|i-j|<10避免时间相关性
            candidates = [j for j in range(m) if abs(i - j) > 10]
            if not candidates:
                continue

            # 找dim维空间的最近邻
            min_dist = float('inf')
            nearest = -1
            for j in candidates:
                dist = sum((vi[k] - vecs[j][k]) ** 2 for k in range(dim))
                if dist < min_dist:
                    min_dist = dist
                    nearest = j

            if nearest < 0 or min_dist == 0:
                continue

            # 检查在 dim+1 维是否还是近邻
            if i + dim * delay < n and nearest + dim * delay < n:
                next_i = series[i + dim * delay] if i + dim * delay < n else None
                next_j = series[nearest + dim * delay] if nearest + dim * delay < n else None

                if next_i is not None and next_j is not None:
                    dist_next = (next_i - next_j) ** 2
                    # [文献] Kennel+1992公式:
                    # 如果新距离 > rtol * 原距离 → 假近邻
                    # 或新距离 > atol * std → 假近邻
                    if dist_next > rtol * min_dist or dist_next > atol:
                        false_count += 1

        fnn_ratios[dim] = false_count / total_count if total_count > 0 else 1.0

    return fnn_ratios


def cao_method(series, max_dim=15, delay=1):
    """Cao方法 (1997): E1(d) = 平均(||v_i^{d+1} - v_j^{d+1}|| / ||v_i^d - v_j^d||).
    当E1(d)饱和(不再变化)→ 最小嵌入维度.

    比FNN更鲁棒, 不需要阈值参数.
    """
    vecs_by_dim = {}
    for dim in range(1, max_dim + 2):
        vecs_by_dim[dim] = time_delay_embed(series, dim, delay)

    E1 = {}
    for dim in range(1, max_dim + 1):
        vecs_d = vecs_by_dim[dim]
        vecs_d1 = vecs_by_dim[dim + 1]
        m = min(len(vecs_d), len(vecs_d1))

        ratios = []
        for i in range(m):
            vi_d = vecs_d[i]
            vi_d1 = vecs_d1[i]

            # 找最近邻
            min_dist = float('inf')
            nearest = -1
            for j in range(m):
                if abs(i - j) < 10:
                    continue
                dist = sum((vi_d[k] - vecs_d[j][k]) ** 2 for k in range(dim))
                if dist < min_dist:
                    min_dist = dist
                    nearest = j

            if nearest >= 0 and min_dist > 0:
                dist_d1 = sum((vi_d1[k] - vecs_d1[nearest][k]) ** 2 for k in range(dim + 1))
                ratios.append(math.sqrt(dist_d1) / math.sqrt(min_dist))

        E1[dim] = sum(ratios) / len(ratios) if ratios else float('inf')

    return E1


# ═══════════════════════════════════════════════════════════════════
# 主函数
# ═══════════════════════════════════════════════════════════════════

def run():
    data = load_data()
    n = len(data)
    features = extract_features(data)

    print(f"=" * 60)
    print(f"实验2: Takens时延嵌入 + 假近邻法")
    print(f"=" * 60)
    print(f"数据: {n} 期 → {len(features[0])}维特征")
    print()

    # 对每个特征维度做FNN
    feature_names = [
        "和值", "跨度", "奇数比", "大号比", "质数比",
        "012路和", "AC值", "蓝球", "最大间距", "重号比", "邻号比", "连号比"
    ]

    all_fnn = {}
    for fi in range(len(features[0])):
        series = [f[fi] for f in features]
        fnn = false_nearest_neighbors(series)
        all_fnn[feature_names[fi]] = fnn

    # 综合: 聚合所有特征的FNN平均值
    print(f"  假近邻分析 (FNN% 每维度):")
    print(f"  {'维度':>5} | " + " | ".join(f"{fn[:4]:>4}" for fn in feature_names) + " | 平均")
    print(f"  {'─'*5}─┼─" + "─┼─".join("─"*4 for _ in feature_names) + "─┼─" + "─"*4)

    avg_fnn = {}
    for dim in range(1, 16):
        vals = []
        row = f"  {dim:>5} |"
        for fn in feature_names:
            v = all_fnn[fn].get(dim)
            if v is not None:
                vals.append(v)
                row += f" {v*100:4.0f}%"
            else:
                row += f"  N/A"
        avg = sum(vals) / len(vals) if vals else 1.0
        avg_fnn[dim] = avg
        row += f" | {avg*100:4.0f}%"
        print(row)

    print()
    print(f"  Cao E1 分析 (和值序列):")
    series_sum = [f[0] for f in features]  # 和值
    cao = cao_method(series_sum)
    for dim, e1 in cao.items():
        bar = "█" * min(40, int(e1 * 10))
        print(f"    dim={dim:>2}: E1={e1:.4f} {bar}")

    # 判定
    print()
    print(f"{'─' * 60}")
    # [文献] 嵌入维<8且FNN<5%→确定性系统 (Kantz+Schreiber 2004)
    low_dim_dims = [d for d, fnn in avg_fnn.items() if fnn < 0.05]
    if low_dim_dims:
        m_opt = low_dim_dims[0]
        print(f"判定: ⚠️  嵌入维度 m≈{m_opt} → 低维确定性系统")
        print(f"  系统自由度 ≈ {m_opt}, 具有可预测的动力学结构")
        print(f"  → 强烈建议进行实验3+后续预测建模")

        # [文献] Lyapunov指数粗略估计
        # 如果E1在m之后稳定, 可通过最近邻发散率估计λ
        e1_vals = [cao.get(d, float('inf')) for d in range(1, 16)]
        stable_period = []
        for d in range(m_opt, min(m_opt + 5, 15)):
            if d + 1 < len(e1_vals) and e1_vals[d] > 0:
                stable_period.append(e1_vals[d])
        if stable_period:
            lyap_est = math.log(sum(stable_period) / len(stable_period))
            pred_horizon = 1.0 / max(lyap_est, 0.001)
            print(f"  估计Lyapunov指数 ≈ {lyap_est:.4f}")
            print(f"  可预测窗口 ≈ {pred_horizon:.0f} 期")

        return {"verdict": "deterministic", "embedding_dim": m_opt,
                "lyapunov_est": lyap_est if stable_period else None}
    else:
        print(f"判定: FNN始终>5%, 无明显低维嵌入 → 高维/随机")
        print(f"  → 时序结构可能微弱, 需要更多数据或不同编码")
        return {"verdict": "high_dimensional", "embedding_dim": None}


if __name__ == "__main__":
    run()
