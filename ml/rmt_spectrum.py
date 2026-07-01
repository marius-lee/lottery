"""随机矩阵谱分析 (RMT) — 33×33 相关矩阵对角化 + Marchenko-Pastur 离群检测

用幂迭代法求最大特征值及特征向量，检测非随机信号结构。
"""
import math
import random


def _correlation_matrix(data, window=200):
    """从近 window 期数据构建 33×33 标准化相关矩阵.

    每球每期: 1=出现, 0=未出现。返回 (C, means, stds).
    """
    recent = data[-window:] if len(data) > window else data
    T = len(recent)
    N = 33

    # 观测矩阵 X[T x 33]
    X = [[0.0] * N for _ in range(T)]
    for t, row in enumerate(recent):
        for r in row[1:7]:
            X[t][r - 1] = 1.0

    # 均值和标准差
    means = [0.0] * N
    for t in range(T):
        for i in range(N):
            means[i] += X[t][i]
    for i in range(N):
        means[i] /= T

    stds = [0.0] * N
    for t in range(T):
        for i in range(N):
            diff = X[t][i] - means[i]
            stds[i] += diff * diff
    for i in range(N):
        stds[i] = math.sqrt(stds[i] / T) if stds[i] > 0 else 0.001

    # 相关矩阵 C = (1/T) X^T X (标准化后)
    C = [[0.0] * N for _ in range(N)]
    for i in range(N):
        for j in range(i, N):
            s = 0.0
            for t in range(T):
                s += ((X[t][i] - means[i]) / stds[i]) * ((X[t][j] - means[j]) / stds[j])
            C[i][j] = s / T
            C[j][i] = C[i][j]

    return C, means, stds


def _power_iteration(A, n_iter=200):
    """幂迭代法求对称矩阵 A 的最大特征值和特征向量."""
    N = len(A)
    v = [1.0 / math.sqrt(N)] * N
    # 加一点随机扰动打破对称退化
    for i in range(N):
        v[i] += random.uniform(-0.001, 0.001)
    norm = math.sqrt(sum(x * x for x in v))
    v = [x / norm for x in v]

    for _ in range(n_iter):
        # w = A @ v
        w = [sum(A[i][j] * v[j] for j in range(N)) for i in range(N)]
        # 归一化
        norm = math.sqrt(sum(x * x for x in w))
        if norm < 1e-12:
            break
        v_new = [x / norm for x in w]
        # 检查收敛
        change = math.sqrt(sum((v_new[i] - v[i]) ** 2 for i in range(N)))
        v = v_new
        if change < 1e-6:
            break

    # Rayleigh 商: λ = v^T A v
    Av = [sum(A[i][j] * v[j] for j in range(N)) for i in range(N)]
    lam = sum(v[i] * Av[i] for i in range(N))
    return lam, v


def _deflate(A, lam, v):
    """从 A 中减去 λ * v * v^T."""
    N = len(A)
    return [[A[i][j] - lam * v[i] * v[j] for j in range(N)] for i in range(N)]


def compute_rmt_signals(data, window=200, top_k=15):
    """RMT 分析: 计算相关矩阵, 检测离群特征值, 提取信号向量.

    Args:
        data: [[period, r1..r6, blue], ...]
        window: 回溯窗口
        top_k: 报告前 K 个信号号码

    Returns:
        signal_nums: [num, ...]  最高权重号码
        eigenvalue: 最大特征值
        mp_bound: Marchenko-Pastur 上界
        diagnostics: dict
    """
    C, means, stds = _correlation_matrix(data, window)
    T = min(window, len(data))
    N = 33
    Q = N / T  # aspect ratio

    # Marchenko-Pastur 上界
    mp_upper = (1 + math.sqrt(Q)) ** 2

    # 幂迭代求最大特征值
    lam1, v1 = _power_iteration(C)

    # 对特征向量取绝对值做信号权重
    weights = [abs(v1[i]) for i in range(N)]
    ranked = sorted([(i + 1, weights[i]) for i in range(N)], key=lambda x: -x[1])

    signal_nums = [num for num, w in ranked[:top_k] if w > 1.0 / 33 * 1.2]

    return signal_nums, lam1, mp_upper, {
        "window": T,
        "Q": round(Q, 4),
        "mp_upper": round(mp_upper, 4),
        "max_eigenvalue": round(lam1, 4),
        "is_signal": lam1 > mp_upper,
        "signal_strength": round(lam1 / mp_upper, 4) if mp_upper > 0 else 0,
        "top_weights": [(num, round(w, 4)) for num, w in ranked[:15]],
    }


# ═══ 红蓝互相关 ═══

def compute_red_blue_cross_signal(data, window=200, top_k=6):
    """33×16 红蓝互相关: 哪个红球的出现与哪个蓝球的出现有非随机耦合.

    构建 33×16 标准化的互相关矩阵 R。
    对 R * R^T (33×33) 做幂迭代, 提取第一个特征向量作为红球信号权重,
    对 R^T * R (16×16) 做幂迭代, 提取第一个特征向量作为蓝球信号权重.

    这是 CCA (典型相关分析) 的简化版——找红球和蓝球之间
    最显著的线性协变模式。

    Returns:
        red_weights: [0.0]*34 (1-indexed)  红球信号权重
        blue_weights: [0.0]*17 (1-indexed) 蓝球信号权重
        diagnostics: dict
    """
    recent = data[-window:] if len(data) > window else data
    T = len(recent)
    N_RED, N_BLUE = 33, 16

    # 构建观测矩阵
    X_red = [[0.0] * N_RED for _ in range(T)]
    X_blue = [[0.0] * N_BLUE for _ in range(T)]
    for t, row in enumerate(recent):
        for r in row[1:7]:
            X_red[t][r - 1] = 1.0
        X_blue[t][row[7] - 1] = 1.0

    # 均值和标准差
    def _standardize(X, N):
        means = [sum(X[t][i] for t in range(T)) / T for i in range(N)]
        stds = [0.0] * N
        for t in range(T):
            for i in range(N):
                diff = X[t][i] - means[i]
                stds[i] += diff * diff
        for i in range(N):
            stds[i] = math.sqrt(stds[i] / T) if stds[i] > 0 else 0.001
        Xs = [[(X[t][i] - means[i]) / stds[i] for i in range(N)] for t in range(T)]
        return Xs

    Xs_red = _standardize(X_red, N_RED)
    Xs_blue = _standardize(X_blue, N_BLUE)

    # 互相关矩阵 R[33×16]: R[i][j] = (1/T) Σ_t Xs_red[t][i] * Xs_blue[t][j]
    R = [[0.0] * N_BLUE for _ in range(N_RED)]
    for t in range(T):
        for i in range(N_RED):
            for j in range(N_BLUE):
                R[i][j] += Xs_red[t][i] * Xs_blue[t][j]
    for i in range(N_RED):
        for j in range(N_BLUE):
            R[i][j] /= T

    # R * R^T → 幂迭代 → 红球权重
    RRt = [[sum(R[i][k] * R[j][k] for k in range(N_BLUE)) for j in range(N_RED)] for i in range(N_RED)]
    lam_red, v_red = _power_iteration(RRt)
    red_w = [abs(v_red[i]) for i in range(N_RED)]
    # 归一化到均值 1.0
    mean_r = sum(red_w) / N_RED
    red_weights = [0.0] * 34
    for i in range(N_RED):
        red_weights[i + 1] = max(0.5, min(2.0, red_w[i] / mean_r if mean_r > 0 else 1.0))

    # R^T * R → 幂迭代 → 蓝球权重
    RtR = [[sum(R[k][i] * R[k][j] for k in range(N_RED)) for j in range(N_BLUE)] for i in range(N_BLUE)]
    lam_blue, v_blue = _power_iteration(RtR)
    blue_w = [abs(v_blue[i]) for i in range(N_BLUE)]
    mean_b = sum(blue_w) / N_BLUE
    blue_weights = [0.0] * 17
    for i in range(N_BLUE):
        blue_weights[i + 1] = max(0.5, min(2.0, blue_w[i] / mean_b if mean_b > 0 else 1.0))

    return red_weights, blue_weights, {
        "window": T,
        "lam_red": round(lam_red, 4),
        "lam_blue": round(lam_blue, 4),
        "top_red": sorted([(i + 1, round(red_weights[i + 1], 3)) for i in range(N_RED)],
                          key=lambda x: -x[1])[:8],
        "top_blue": sorted([(i + 1, round(blue_weights[i + 1], 3)) for i in range(N_BLUE)],
                           key=lambda x: -x[1])[:6],
    }
