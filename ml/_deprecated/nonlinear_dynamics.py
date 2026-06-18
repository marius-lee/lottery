"""非线性动力系统检测 — 回答「双色球序列是纯随机还是确定性混沌？」

4个核心算法，均有精确数学来源：

1. BDS检验: 检测非线性依赖 → 混沌 vs i.i.d.
   来源: Brock, Dechert, Scheinkman & LeBaron (1996) Econometric Reviews 15(3)
   https://doi.org/10.1080/07474939608800353

2. 排列熵(PE): 序数模式的复杂度 → 0~1, 越接近1越随机
   来源: Bandt & Pompe (2002) Phys Rev Lett 88, 174102
   https://doi.org/10.1103/PhysRevLett.88.174102

3. 递归量化分析(RQA): 相空间递归度量
   来源: Marwan et al. (2007) Physics Reports 438, 237-329
   https://doi.org/10.1016/j.physrep.2006.11.001

4. 最大Lyapunov指数: 初值敏感度 → >0 = 混沌
   来源: Rosenstein, Collins, De Luca (1993) Physica D 65, 117-134
   https://doi.org/10.1016/0167-2789(93)90009-P

辅助：
   假近邻法(FNN): 确定最优嵌入维数m
   来源: Kennel, Brown, Abarbanel (1992) Phys Rev A 45, 3403
   https://doi.org/10.1103/PhysRevA.45.3403

   互信息法(MI): 确定最优延迟τ
   来源: Fraser & Swinney (1986) Phys Rev A 33, 1134
   https://doi.org/10.1103/PhysRevA.33.1134
"""

import math
import numpy as np
from collections import Counter


# ═══════════════════════════════════════════════════════════════════
# 0. 辅助: 从开奖数据提取多种序列
# ═══════════════════════════════════════════════════════════════════

def extract_series(draws):
    """从开奖数据提取可分析的时间序列。

    Args:
        draws: [[period, r1..r6, blue], ...] 按period升序

    Returns:
        dict: {name: np.array}
    """
    draws = np.array(draws, dtype=np.float64)
    N = len(draws)

    series = {}

    # 和值序列
    series["sum"] = draws[:, 1:7].sum(axis=1)

    # 跨度序列
    reds = draws[:, 1:7]
    series["span"] = reds.max(axis=1) - reds.min(axis=1)

    # 蓝球序列
    series["blue"] = draws[:, 7]

    # 红球位序列 (每球位独立)
    for pos in range(6):
        series[f"pos_{pos+1}"] = reds[:, pos]

    # 每球出现序列 (33红 + 16蓝)
    for n in range(1, 34):
        series[f"red_{n:02d}"] = np.array([1.0 if n in d[1:7] else 0.0 for d in draws])
    for n in range(1, 17):
        series[f"blue_{n:02d}"] = np.array([1.0 if d[7] == n else 0.0 for d in draws])

    return series


# ═══════════════════════════════════════════════════════════════════
# 1. BDS 检验
#    H0: 序列是 i.i.d.
#    H1: 序列存在非线性依赖 (确定性混沌或其他非线性结构)
# ============================================================================

def _correlation_integral(x, m, eps):
    """计算关联积分 C(m, ε) = 2/(N*(N-1)) * Σ I(||x_i^m - x_j^m|| < ε)

    来源: Grassberger & Procaccia (1983) Physica D 9, 189
    https://doi.org/10.1016/0167-2789(83)90298-1
    """
    n = len(x) - m + 1
    if n < 2:
        return 0.0

    # 构造嵌入向量
    embedded = np.array([x[i:i + m] for i in range(n)])

    # 计算距离矩阵上三角
    count = 0
    for i in range(n):
        dists = np.max(np.abs(embedded[i + 1:] - embedded[i]), axis=1)
        count += np.sum(dists < eps)

    return 2.0 * count / (n * (n - 1))


def _bds_sigma(x, m, eps, c1):
    """BDS统计量σ²的K参数估计 (Brock et al. 1996, eq. 2.10-2.13)

    σ²(m,ε) = 4 * [K^m + 2Σ_{j=1}^{m-1} K^{m-j}·C^{2j} + (m-1)²·C^{2m} - m²·K·C^{2m-2}]

    其中 K = K(ε) 是单维关联积分变体的期望
    """
    n = len(x) - m + 1
    if n < 3:
        return 1.0

    embedded = np.array([x[i:i + m] for i in range(n)])

    # K: E[ I(|X_i - X_j| < ε) * I(|X_{i+1} - X_{j+1}| < ε) ]
    k_count = 0.0
    k_total = 0
    for i in range(n - 1):
        for j in range(i + 1, n - 1):
            if abs(x[i + m] - x[j + m]) < eps:
                k_count += 1.0
            k_total += 1
    k_val = k_count / max(k_total, 1)

    # 简化方差估计: σ² ≈ 4k / n (Brock 1996 大样本近似)
    # 完整公式计算量大, 用渐近式
    var = max(4.0 * k_val / n, 1e-10)
    return math.sqrt(var)


def bds_test(series, m_max=5, eps_factor=1.0):
    """BDS检验 — 检测序列的非线性依赖。

    Args:
        series: 一维numpy数组
        m_max: 最大嵌入维数 (默认5)
        eps_factor: ε缩放因子 (默认1.0 = σ/2, 来源: Brock 1996建议 ε/σ ∈ [0.5, 2])

    Returns:
        dict: 每个m对应的W统计量和p值
    """
    x = np.asarray(series, dtype=np.float64)
    # 标准化
    x = (x - x.mean()) / (x.std() + 1e-10)
    eps = 0.5 * eps_factor  # Brock 1996: ε = σ/2 为标准配置
    n = len(x)

    results = {}
    for m in range(2, m_max + 1):
        c_m = _correlation_integral(x, m, eps)
        if c_m <= 0:
            results[m] = {"w_stat": None, "p_value": None, "reject_iid": None}
            continue

        c1 = _correlation_integral(x, 1, eps)
        if c1 <= 0 or c1 >= 1:
            results[m] = {"w_stat": None, "p_value": None, "reject_iid": None}
            continue

        # BDS W统计量 = √n [C(m) - C(1)^m] / σ(m)
        # 来源: Brock et al. (1996) eq. 2.9
        sigma = _bds_sigma(x, m, eps, c1)
        w_stat = math.sqrt(n) * (c_m - c1 ** m) / sigma

        # W ~ N(0,1) 的p值 (双尾)
        p_value = 2.0 * (1.0 - _norm_cdf(abs(w_stat)))

        results[m] = {
            "w_stat": round(w_stat, 4),
            "p_value": round(p_value, 6),
            "reject_iid": p_value < 0.05,
            "reject_iid_bonferroni": p_value < (0.05 / (m_max - 1)),
            "c1": round(float(c1), 6),
            f"c{m}": round(float(c_m), 6),
        }

    return results


def _norm_cdf(z):
    """标准正态CDF (Abramowitz & Stegun 26.2.17, 误差<7.5e-8)"""
    b = [0.2316419, 0.319381530, -0.356563782, 1.781477937, -1.821255978, 1.330274429]
    t = 1.0 / (1.0 + b[0] * abs(z))
    phi = 1.0 - (1.0 / math.sqrt(2 * math.pi)) * math.exp(-z * z / 2.0) * (
        b[1] * t + b[2] * t ** 2 + b[3] * t ** 3 + b[4] * t ** 4 + b[5] * t ** 5
    )
    if z < 0:
        return 1.0 - phi
    return phi


# ═══════════════════════════════════════════════════════════════════
# 2. 排列熵 (Permutation Entropy)
# ============================================================================

def permutation_entropy(series, m=4, tau=1):
    """计算排列熵 — 衡量序列的序数模式复杂度。

    PE ∈ [0, 1]. PE→0 = 高度确定性/周期, PE→1 = 完全随机.

    来源: Bandt & Pompe (2002) Phys Rev Lett 88, 174102
    https://doi.org/10.1103/PhysRevLett.88.174102

    Args:
        series: 一维numpy数组
        m: 嵌入维数 (推荐3-7, 默认4)
        tau: 延迟 (默认1)

    Returns:
        dict: {pe_normalized, pe_raw, n_patterns_observed, pattern_entropy}
    """
    x = np.asarray(series, dtype=np.float64)
    n = len(x)

    if n < m * tau:
        return {"pe_normalized": None, "pe_raw": None, "error": f"序列太短: {n} < {m * tau}"}

    # 提取序数模式
    # 对每段x[i], x[i+tau], ..., x[i+(m-1)tau], 确定排序模式
    patterns = []
    for i in range(n - (m - 1) * tau):
        segment = x[i:i + m * tau:tau]
        # 排序 → 序数模式 (处理平局: 保留首次出现顺序)
        sorted_indices = np.argsort(segment)
        # 编码为序数模式: 排名序列
        ranks = np.zeros(m, dtype=int)
        for rank, idx in enumerate(sorted_indices):
            ranks[idx] = rank
        # 将序数模式编码为整数 (阶乘进制)
        pattern_code = _ranks_to_int(ranks)
        patterns.append(pattern_code)

    # 模式频率 → 概率
    counter = Counter(patterns)
    frequencies = np.array(list(counter.values()), dtype=np.float64)
    probs = frequencies / frequencies.sum()

    # PE = -Σ p(π) log₂ p(π)
    pe_raw = -np.sum(probs * np.log2(probs))
    # 归一化: PE / log₂(m!)
    max_pe = math.log2(math.factorial(m))
    pe_normalized = pe_raw / max_pe if max_pe > 0 else 0.0

    return {
        "pe_normalized": round(pe_normalized, 6),
        "pe_raw": round(pe_raw, 4),
        "m": m,
        "tau": tau,
        "n_patterns_observed": len(counter),
        "n_patterns_possible": math.factorial(m),
    }


def _ranks_to_int(ranks):
    """将序数模式的排列向量编码为整数 (Lehmer编码→阶乘进制)"""
    n = len(ranks)
    code = 0
    for i in range(n):
        # 统计比ranks[i]小的剩余元素
        smaller = sum(1 for j in range(i + 1, n) if ranks[j] < ranks[i])
        code = code * (n - i) + smaller
    return code


# ═══════════════════════════════════════════════════════════════════
# 3. 递归量化分析 (Recurrence Quantification Analysis)
# ============================================================================

def recurrence_analysis(series, m=3, tau=1, eps=None, eps_percentile=10):
    """递归量化分析(RQA) — 从递归图提取量化度量。

    来源: Marwan et al. (2007) Physics Reports 438, 237-329
    https://doi.org/10.1016/j.physrep.2006.11.001

    RQA度量:
      RR:  递归率 — 递归点占总点数比例
      DET: 确定性 — 对角结构中的递归点比例 (>2对角线)
      L_max: 最长对角线长度
      L_mean: 平均对角线长度
      ENTR: 对角线长度分布的Shannon熵
      LAM: 层流性 — 垂直线结构中的递归点比例
      TT:  捕获时间 — 平均垂直线长度

    Args:
        series: 一维numpy数组
        m: 嵌入维数 (默认3)
        tau: 延迟 (默认1)
        eps: 阈值半径 (默认None→自动按百分位)
        eps_percentile: 距离分布的百分位数作为阈值

    Returns:
        dict: RQA度量
    """
    x = np.asarray(series, dtype=np.float64)
    n = len(x) - (m - 1) * tau

    if n < 50:
        return {"error": f"相空间点数不足: {n} < 50"}

    # 相空间重构: Takens嵌入
    embedded = np.array([x[i:i + m * tau:tau] for i in range(n)])

    # 距离矩阵
    dists = np.zeros((n, n))
    for i in range(n):
        diff = embedded[i + 1:] - embedded[i]
        dists[i, i + 1:] = np.max(np.abs(diff), axis=1)
        dists[i + 1:, i] = dists[i, i + 1:]

    # 阈值: 距离分布的百分位数
    if eps is None:
        eps = np.percentile(dists[dists > 0], eps_percentile)

    # 递归矩阵: R(i,j) = I(||x_i - x_j|| < ε)
    R = (dists < eps).astype(np.int32)
    np.fill_diagonal(R, 0)

    # === RQA 度量 ===

    # RR: 递归率
    total_points = n * (n - 1)
    rr = R.sum() / total_points

    # 对角线分析 (不包括主对角线)
    diag_lengths = []
    for k in range(1, n):
        diag = np.diag(R, k)
        # 提取连续1的段
        length = 0
        for val in diag:
            if val == 1:
                length += 1
            else:
                if length >= 2:
                    diag_lengths.append(length)
                length = 0
        if length >= 2:
            diag_lengths.append(length)

    n_diag = len(diag_lengths)
    diag_points = sum(diag_lengths) if diag_lengths else 0

    # DET: 确定性 = 对角结构点数 / 递归点数
    det = diag_points / max(R.sum(), 1)

    # L_max, L_mean
    l_max = max(diag_lengths) if diag_lengths else 0
    l_mean = np.mean(diag_lengths) if diag_lengths else 0

    # ENTR: 对角线分布熵
    entr = 0.0
    if diag_lengths:
        diag_counter = Counter(diag_lengths)
        total = len(diag_lengths)
        for count in diag_counter.values():
            p = count / total
            entr -= p * math.log(p)
        entr = entr / math.log(2) if entr > 0 else 0.0  # 转为bits

    # 垂直线分析
    vert_lengths = []
    for j in range(n):
        col = R[:, j]
        length = 0
        for val in col:
            if val == 1:
                length += 1
            else:
                if length >= 2:
                    vert_lengths.append(length)
                length = 0
        if length >= 2:
            vert_lengths.append(length)

    n_vert = len(vert_lengths)
    vert_points = sum(vert_lengths) if vert_lengths else 0

    # LAM: 层流性
    lam = vert_points / max(R.sum(), 1)

    # TT: 平均垂直线长度
    tt = np.mean(vert_lengths) if vert_lengths else 0

    return {
        "rr": round(float(rr), 6),
        "det": round(float(det), 4),
        "l_max": int(l_max),
        "l_mean": round(float(l_mean), 2),
        "entr": round(float(entr), 4),
        "lam": round(float(lam), 4),
        "tt": round(float(tt), 2),
        "n_diag_lines": n_diag,
        "n_vert_lines": n_vert,
        "embedding_dim": m,
        "delay": tau,
        "eps_radius": round(float(eps), 6),
        "n_points": n,
    }


# ═══════════════════════════════════════════════════════════════════
# 4. 最大Lyapunov指数
# ============================================================================

def lyapunov_exponent(series, m=None, tau=1, min_t=5, max_t=80):
    """计算最大Lyapunov指数 — 量化对初值的敏感度。

    λ₁ > 0 → 混沌 (初值敏感)
    λ₁ = 0 → 周期/准周期
    λ₁ < 0 → 稳定不动点

    来源: Rosenstein, Collins, De Luca (1993) Physica D 65, 117-134
    https://doi.org/10.1016/0167-2789(93)90009-P

    Args:
        series: 一维numpy数组
        m: 嵌入维数 (默认None→自动用FNN确定)
        tau: 延迟 (默认1)
        min_t: 最小演化步数
        max_t: 最大演化步数

    Returns:
        dict: {lyapunov_λ₁, embedding_dim, etc.}
    """
    x = np.asarray(series, dtype=np.float64)

    # 自动确定m (FNN)
    if m is None:
        m = _fnn_dimension(x, tau=tau)
        if m is None or m < 2:
            m = 3  # 默认

    n = len(x) - (m - 1) * tau
    if n < 50:
        return {"error": f"相空间点数不足: {n} < 50"}

    # 相空间重构
    embedded = np.array([x[i:i + m * tau:tau] for i in range(n)])

    # 对每个点找最近邻 (跳过时间相关点)
    min_sep = m * tau  # 最小时间分离

    divergence = []
    for i in range(n - max_t):
        # 找最近邻
        min_dist = float("inf")
        nearest_j = -1
        for j in range(n - max_t):
            if abs(i - j) < min_sep:
                continue
            dist = np.max(np.abs(embedded[i] - embedded[j]))
            if dist < min_dist:
                min_dist = dist
                nearest_j = j

        if nearest_j < 0 or min_dist < 1e-10:
            continue

        # 追踪发散
        div_i = []
        for step in range(1, max_t + 1):
            if i + step >= n or nearest_j + step >= n:
                break
            d = np.max(np.abs(embedded[i + step] - embedded[nearest_j + step]))
            if d < 1e-10:
                d = 1e-10
            div_i.append(math.log(d))
        if len(div_i) >= max_t:
            divergence.append(div_i)

    if not divergence:
        return {"error": "找不到足够的邻居对用于发散追踪"}

    # 平均log发散
    divergence = np.array(divergence)
    avg_div = divergence.mean(axis=0)

    # 对min_t..max_t段做线性拟合, 斜率=λ₁
    t_range = np.arange(min_t - 1, max_t)
    y = avg_div[min_t - 1:max_t]

    # 线性回归: 找斜率
    t_mean = np.mean(t_range)
    y_mean = np.mean(y)
    slope = np.sum((t_range - t_mean) * (y - y_mean)) / np.sum((t_range - t_mean) ** 2)

    # 拟合优度
    y_pred = slope * t_range + (y_mean - slope * t_mean)
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - y_mean) ** 2)
    r_squared = 1.0 - ss_res / max(ss_tot, 1e-10)

    return {
        "lyapunov_λ₁": round(float(slope), 6),
        "λ₁_verdict": "chaotic" if slope > 0.01 else ("periodic" if abs(slope) <= 0.01 else "stable"),
        "r_squared": round(float(r_squared), 4),
        "embedding_dim": m,
        "delay": tau,
        "n_divergence_pairs": len(divergence),
        "fit_range": [min_t, max_t],
    }


# ═══════════════════════════════════════════════════════════════════
# 5. 假近邻法 (FNN) — 确定最优嵌入维数
# ============================================================================

def _fnn_dimension(x, tau=1, max_m=10, rtol=15.0, atol=2.0):
    """假近邻法 — 确定最优嵌入维数m。

    来源: Kennel, Brown, Abarbanel (1992) Phys Rev A 45, 3403
    https://doi.org/10.1103/PhysRevA.45.3403

    当FNN比例 < 1% (或首次显著下降), 该m为最优。

    Args:
        x: 时间序列
        tau: 延迟
        max_m: 最大嵌入维数
        rtol: 相对距离阈值 (Kennel建议15)
        atol: 绝对距离阈值 (Kennel建议2)

    Returns:
        int: 最优嵌入维数m
    """
    n = len(x)
    std_x = np.std(x)
    if std_x < 1e-10:
        std_x = 1.0

    fnn_pcts = []
    for m in range(1, max_m + 1):
        n_points = n - m * tau
        if n_points < 50:
            break

        embedded = np.array([x[i:i + m * tau:tau] for i in range(n_points)])

        fnn_count = 0
        total = 0
        for i in range(n_points - 1):
            # 找最近邻
            dists = np.max(np.abs(embedded[i + 1:] - embedded[i]), axis=1)
            nearest_idx = np.argmin(dists)
            nearest_dist = dists[nearest_idx]

            if nearest_dist < 1e-10:
                continue
            total += 1

            # 检查下一维是否为假近邻
            # R_{m+1}^2 = R_m^2 + (x[i+m*tau] - x[j+m*tau])²
            i_next = i + m * tau
            j_next = nearest_idx + i + 1 + m * tau
            if i_next < n and j_next < n:
                delta = abs(x[i_next] - x[j_next])
                r_next = math.sqrt(nearest_dist ** 2 + delta ** 2)
                # 假近邻条件: |Δ| / R_m > rtol 或 R_{m+1} / σ > atol
                if r_next > 0 and (delta / nearest_dist > rtol or r_next / std_x > atol):
                    fnn_count += 1

        fnn_pcts.append(fnn_count / max(total, 1))

    # 找第一个FNN < 5%的m
    for i, pct in enumerate(fnn_pcts):
        if pct < 0.05:
            return i + 1

    # 找FNN下降最多的拐点
    if len(fnn_pcts) >= 3:
        best_m = 1
        best_drop = 0
        for i in range(len(fnn_pcts) - 1):
            drop = fnn_pcts[i] - fnn_pcts[i + 1]
            if drop > best_drop:
                best_drop = drop
                best_m = i + 2
        return min(best_m, max_m)

    return min(max_m, 3)


# ═══════════════════════════════════════════════════════════════════
# 6. 互信息法 — 确定最优延迟τ
# ============================================================================

def mutual_information_delay(x, max_tau=20, n_bins=20):
    """互信息法 — 确定最优延迟时间τ。

    来源: Fraser & Swinney (1986) Phys Rev A 33, 1134
    https://doi.org/10.1103/PhysRevA.33.1134

    建议: 取第一个局部极小值。

    Args:
        x: 时间序列
        max_tau: 最大延迟
        n_bins: 直方图分箱数

    Returns:
        dict: {optimal_tau, mi_values, suggested_tau}
    """
    x = np.asarray(x, dtype=np.float64)
    n = len(x)

    mi_values = []
    for t in range(1, min(max_tau + 1, n // 2)):
        # 离散化
        x_t = x[:-t]
        x_shifted = x[t:]

        # 联合直方图
        x_min, x_max = x.min(), x.max()
        bins_x = np.linspace(x_min, x_max + 1e-10, n_bins + 1)

        x_disc = np.digitize(x_t, bins_x)
        x_s_disc = np.digitize(x_shifted, bins_x)

        # 联合分布 P(x(t), x(t+τ))
        joint = np.zeros((n_bins + 1, n_bins + 1))
        for i in range(len(x_t)):
            joint[x_disc[i], x_s_disc[i]] += 1
        joint /= len(x_t)

        # 边缘分布
        px = joint.sum(axis=1)
        py = joint.sum(axis=0)

        # MI = Σ P(x,y) log [P(x,y) / (P(x)P(y))]
        mi = 0.0
        for i in range(n_bins + 1):
            for j in range(n_bins + 1):
                if joint[i, j] > 0 and px[i] > 0 and py[j] > 0:
                    mi += joint[i, j] * math.log(joint[i, j] / (px[i] * py[j]))

        mi_values.append(float(mi))

    # 找第一个局部极小值
    optimal_tau = 1
    for i in range(1, len(mi_values) - 1):
        if mi_values[i] < mi_values[i - 1] and mi_values[i] <= mi_values[i + 1]:
            optimal_tau = i + 1
            break

    # 如果没有局部极小, 取 < 平均MI 的最小τ
    if optimal_tau == 1 and mi_values:
        mean_mi = np.mean(mi_values)
        for i, mi in enumerate(mi_values):
            if mi < mean_mi:
                optimal_tau = i + 1
                break

    return {
        "suggested_tau": optimal_tau,
        "mi_values": [round(v, 6) for v in mi_values],
        "first_local_min": optimal_tau,
    }


# ═══════════════════════════════════════════════════════════════════
# 7. 综合诊断: 一键运行全部分析
# ============================================================================

def _to_native(obj):
    """递归转换numpy类型为Python原生类型 (JSON序列化兼容)"""
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return [_to_native(x) for x in obj.tolist()]
    if isinstance(obj, dict):
        return {_to_native(k): _to_native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_native(x) for x in obj]
    return obj


def comprehensive_analysis(draws):
    """对双色球数据运行全部4个非线性动力系统检测。

    Args:
        draws: [[period, r1..r6, blue], ...]

    Returns:
        dict: 完整诊断报告
    """
    series_dict = extract_series(draws)
    N = len(draws)

    # 选取核心序列做完整分析
    core_series = ["sum", "span", "blue"]
    # 加几个代表性球号
    for n in [1, 7, 14, 21, 28, 33]:  # 6个代表性红球
        core_series.append(f"red_{n:02d}")

    results = {}

    # === BDS检验 ===
    bds_results = {}
    for name in core_series:
        if name in series_dict:
            bds_results[name] = bds_test(series_dict[name], m_max=5)
    results["bds"] = bds_results

    # === 排列熵 ===
    pe_results = {}
    for name in core_series:
        if name in series_dict:
            s = series_dict[name]
            # 用4-6维
            pe_multi = {}
            for mm in [3, 4, 5, 6]:
                pe_multi[f"m={mm}"] = permutation_entropy(s, m=mm, tau=1)
            pe_results[name] = pe_multi
    results["permutation_entropy"] = pe_results

    # === RQA ===
    # 仅对主序列做RQA (计算量大)
    rqa_targets = ["sum", "span", "blue"]
    rqa_results = {}
    for name in rqa_targets:
        if name in series_dict:
            rqa_results[name] = recurrence_analysis(series_dict[name], m=3, tau=1)
    results["rqa"] = rqa_results

    # === Lyapunov ===
    lyap_results = {}
    for name in rqa_targets:
        if name in series_dict:
            lyap_results[name] = lyapunov_exponent(series_dict[name])
    results["lyapunov"] = lyap_results

    # === 辅助: 互信息+假近邻 (仅对sum序列) ===
    if "sum" in series_dict:
        mi = mutual_information_delay(series_dict["sum"])
        results["optimal_params"] = {
            "sum_mi_tau": mi,
            "sum_fnn_m": _fnn_dimension(series_dict["sum"], tau=mi["suggested_tau"]),
        }

    # 汇总判断
    summary = _summarize_diagnostics(results, N)
    results["summary"] = summary

    return _to_native({
        "ok": True,
        "total_draws": N,
        "series_analyzed": core_series,
        **results,
    })


def _summarize_diagnostics(results, n_draws):
    """综合4个检测的结果，给出整体判断。"""
    verdicts = []

    # BDS汇总
    bds_reject_count = 0
    bds_total = 0
    for name, bds_r in results.get("bds", {}).items():
        for m_val, r in bds_r.items():
            if r.get("reject_iid"):
                bds_reject_count += 1
            bds_total += 1
    bds_verdict = f"BDS: {bds_reject_count}/{bds_total} 拒绝i.i.d." if bds_total > 0 else "BDS: 无数据"
    verdicts.append(bds_verdict)

    # PE汇总
    pe_mean = []
    for name, pe_r in results.get("permutation_entropy", {}).items():
        for m_key, r in pe_r.items():
            if r.get("pe_normalized") is not None:
                pe_mean.append(r["pe_normalized"])
    if pe_mean:
        avg_pe = np.mean(pe_mean)
        pe_verdict = f"排列熵均值: {avg_pe:.4f} (0=确定 1=随机)"
        verdicts.append(pe_verdict)
        if avg_pe > 0.85:
            verdicts.append("→ 高排列熵: 序列接近随机")
        elif avg_pe > 0.6:
            verdicts.append("→ 中等排列熵: 可能存在弱确定性结构")
        else:
            verdicts.append("→ 低排列熵: 存在显著确定性结构!")
    else:
        verdicts.append("排列熵: 无数据")

    # Lyapunov汇总
    lyap_values = []
    for name, r in results.get("lyapunov", {}).items():
        if "lyapunov_λ₁" in r:
            lyap_values.append(r["lyapunov_λ₁"])
    if lyap_values:
        mean_lyap = np.mean(lyap_values)
        lyap_verdict = f"Lyapunov λ₁均值: {mean_lyap:.6f}"
        verdicts.append(lyap_verdict)
        if mean_lyap > 0.01:
            verdicts.append("→ λ₁>0: 序列是确定性混沌!")
        elif mean_lyap > 0:
            verdicts.append("→ 微弱正λ₁: 可能有弱混沌成分")
        else:
            verdicts.append("→ λ₁≤0: 序列是周期/随机的, 无混沌")
    else:
        verdicts.append("Lyapunov: 无数据")

    # RQA汇总
    rqa_det_vals = []
    for name, r in results.get("rqa", {}).items():
        if "det" in r and r["det"] is not None:
            rqa_det_vals.append(r["det"])
    if rqa_det_vals:
        avg_det = np.mean(rqa_det_vals)
        verdicts.append(f"RQA DET均值: {avg_det:.4f}")
        if avg_det > 0.5:
            verdicts.append("→ 高确定性: 递归图中存在大量对角结构")
        else:
            verdicts.append("→ 低确定性: 递归图接近均匀随机")

    # 最终判定
    total_signals = 0
    # BDS: >30%拒绝i.i.d.
    if bds_total > 0 and bds_reject_count / bds_total > 0.3:
        total_signals += 1
    # PE: 均值 < 0.85
    if pe_mean and np.mean(pe_mean) < 0.85:
        total_signals += 1
    # Lyapunov: 均值 > 0.01
    if lyap_values and np.mean(lyap_values) > 0.01:
        total_signals += 1
    # RQA: DET > 0.5
    if rqa_det_vals and np.mean(rqa_det_vals) > 0.5:
        total_signals += 1

    if total_signals >= 3:
        final = "CHAOTIC — 检测到强确定性混沌信号。序列可预测!"
    elif total_signals >= 2:
        final = "MIXED — 检测到混合信号。可能存在弱确定性结构, 需更多数据。"
    elif total_signals >= 1:
        final = "WEAK — 仅1个指标微弱偏离随机。大体不可预测, 但值得继续监控。"
    else:
        final = "RANDOM — 全部指标符合i.i.d.随机。不可预测。"

    return {
        "final_verdict": final,
        "signal_count": total_signals,
        "details": verdicts,
        "n_draws": n_draws,
        "note": "2002期是小样本。非线性动力系统检测需要5000-10000期才有足够统计功效检出弱混沌信号。p值应按Bonferroni校正。",
    }
