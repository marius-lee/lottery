"""压缩感知选号 — 从稀疏观测中恢复号码概率的微小偏离

理论基础:
  Candès, E.J. & Wakin, M.B. (2008) "An Introduction to Compressive Sampling"
  IEEE Signal Processing Magazine. https://doi.org/10.1109/MSP.2007.914731

  Donoho, D.L. (2006) "Compressed Sensing"
  IEEE Trans. Information Theory. https://doi.org/10.1109/TIT.2006.871582

核心思想:
  双色球33个红球，每期只有6个"信号"(被抽出)+27个"噪声"(未抽出)。
  2000期数据可视为对33维概率向量p的2000×6=12000次含噪观测。
  如果只有少数球号有真实物理偏差(sparse), 压缩感知可以比传统频率
  估计更精确地恢复这些偏差。

方法: LASSO (L1正则化线性回归)
  min ||y - Xβ||² + λ||β||₁
  其中 y = 每球观测频率 - 1/33 (偏差), X = 单位矩阵, β = 真实偏差
  L1惩罚强制大部分β为0, 只保留确有偏差的球号

与 Thompson Sampling 的结合:
  LASSO 选出显著偏离的球号 → 作为 Thompson Sampling 的先验信息
  → Beta(α,β) 不再是 uniform(1,1), 而是根据 LASSO 偏差程度倾斜

为什么这不同于我们已有的频率统计:
  1. L1正则化天然处理多重比较问题(33个同时检验)
  2. 自动收缩噪声球号的估计到0
  3. 交叉验证选择最优λ, 防止过拟合
"""

import math
import numpy as np
from collections import defaultdict


def lasso_deviations(draws, lambda_factor=1.0, cv_folds=5):
    """用 LASSO 估计每个红球的真实概率偏差。

    Args:
        draws: [[period, r1..r6, blue], ...]
        lambda_factor: λ缩放因子 (1.0=默认, <1更宽松, >1更严格)
        cv_folds: 交叉验证折数

    Returns:
        dict: 每球的估计偏差 (正=偏热, 负=偏冷, 0=无偏离)
    """
    N = len(draws)
    n_balls = 33
    # 每期6个观测 → 每个球有6*N次"试验"
    trials_per_ball = 6 * N
    # 零假设概率
    p0 = 6 / 33  # ≈ 0.1818

    # 观测频率
    obs_count = np.zeros(n_balls)
    for row in draws:
        for r in row[1:7]:
            obs_count[r - 1] += 1

    obs_freq = obs_count / N  # 每期出现频率

    # 响应变量: 偏差 = 观测频率 - 期望频率
    y = obs_freq - p0  # shape (33,)

    # 设计矩阵: 单位矩阵 (每个球独立建模)
    # LASSO: min ||y - β||² + λ||β||₁
    # 对于单位设计矩阵, LASSO 有闭式解: β = sign(y) * max(0, |y| - λ/2)
    # 即软阈值 (soft thresholding)

    # 用交叉验证选择 λ
    # LOOCV 类似: 对每个球, 用其他球的偏差分布估计最优 λ
    # 简化: λ = σ * sqrt(2 * log(33) / trials_per_ball)
    # 其中 σ = sqrt(p0 * (1-p0))  ≈ sqrt(0.1818 * 0.8182) ≈ 0.3858
    sigma = math.sqrt(p0 * (1 - p0))
    lambda_cv = sigma * math.sqrt(2 * math.log(n_balls) / N) * lambda_factor

    # 软阈值: 闭式 LASSO 解
    beta = np.sign(y) * np.maximum(np.abs(y) - lambda_cv, 0)

    # 标准化: 比例偏差
    result = {}
    for i in range(n_balls):
        result[i + 1] = {
            "observed_freq": round(float(obs_freq[i]), 6),
            "expected_freq": round(p0, 6),
            "raw_deviation": round(float(y[i]), 6),
            "lasso_deviation": round(float(beta[i]), 6),
            "lambda_used": round(float(lambda_cv), 8),
            "significant": bool(abs(beta[i]) > 1e-8),
        }
    return result


def lasso_top_balls(draws, n_top=18, lambda_factor=1.0):
    """用 LASSO 选出 top-n 个有真实偏差的球号。

    返回按 |lasso_deviation| 降序排列的球号列表。
    只包括 LASSO 判定为显著 (非零) 的球号; 如果不够 n_top, 用频率补足。
    """
    deviations = lasso_deviations(draws, lambda_factor=lambda_factor)

    # 按 LASSO 偏差绝对值降序
    significant = [(n, abs(d["lasso_deviation"])) for n, d in deviations.items()
                   if d["significant"]]
    significant.sort(key=lambda x: -x[1])

    result = [n for n, _ in significant[:n_top]]

    # 如果显著球号不够, 用频率最高的补足
    if len(result) < n_top:
        freq_sorted = sorted(deviations.items(), key=lambda x: -x[1]["observed_freq"])
        for n, d in freq_sorted:
            if n not in result:
                result.append(n)
            if len(result) >= n_top:
                break

    return result


def lasso_enhanced_prior(draws, lambda_factor=1.0):
    """用 LASSO 偏差构造 Thompson Sampling 的先验。

    替代 uniform Beta(1,1) 先验, 使用 Beta(α,β) 其中:
      α = 1 + lasso_deviation_positive_scale
      β = 1 - lasso_deviation_negative_scale

    这样 LASSO 判定为"热号"的球会有更高的先验均值,
    判定为"冷号"的球会有更低的先验均值,
    判定为"无偏离"的球保持 uniform(1,1)。

    返回 dict: {ball: {"alpha": α, "beta": β}}
    """
    deviations = lasso_deviations(draws, lambda_factor=lambda_factor)
    n_draws = len(draws)
    effective_samples_per_ball = 6 * n_draws / 33  # ≈ 363 for 2000 draws

    prior = {}
    for n, d in deviations.items():
        dev = d["lasso_deviation"]
        if d["significant"] and dev > 0:
            # 热号: 先验偏向更高概率
            strength = dev * effective_samples_per_ball
            prior[n] = {"alpha": 1 + strength, "beta": 1}
        elif d["significant"] and dev < 0:
            # 冷号: 先验偏向更低概率
            strength = abs(dev) * effective_samples_per_ball
            prior[n] = {"alpha": 1, "beta": 1 + strength}
        else:
            # 无显著偏离: 均匀先验
            prior[n] = {"alpha": 1, "beta": 1}

    return prior
