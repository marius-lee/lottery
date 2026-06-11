"""物理偏差检测 — 每个球号的观察频率 vs 理论期望的卡方检验

如果双色球开奖过程存在微小物理偏差（球重、机器磨损等），
长期统计应该能检测到某些号码偏离理论期望的显著性。
这是唯一可能存在的真实预测信号来源。
"""
import math
from collections import Counter
from server import db


def compute_bias():
    """对全部历史数据做逐球卡方检验。

    Returns:
        dict with red_bias, blue_bias, overall_stats
    """
    all_data = db.load_draws()
    if not all_data or len(all_data) < 50:
        return {"ok": False, "msg": f"数据不足，当前{len(all_data)}期，需要≥50期"}

    N = len(all_data)

    # 红球: 每期6个红球 → 总共 6*N 次抽球机会
    red_count = Counter()
    for row in all_data:
        for r in row[1:7]:
            red_count[r] += 1

    # 理论期望: 每个红球出现次数 = 6*N / 33
    red_expected = 6 * N / 33
    red_bias = []
    red_chi2_total = 0.0
    for n in range(1, 34):
        obs = red_count.get(n, 0)
        chi2 = (obs - red_expected) ** 2 / red_expected if red_expected > 0 else 0
        red_chi2_total += chi2
        ratio = obs / red_expected if red_expected > 0 else 1.0
        # 标记显著性: ratio > 1.15 或 < 0.85 (红球)
        # 蓝球阈值较宽松 (±20% vs ±15%) 因蓝球样本量仅 1/6：
        # 红球每期 6 个观测，蓝球每期 1 个，蓝球标准差 ~1/√(N) 是红球的 √6 倍
        flag = "hot" if ratio > 1.15 else ("cold" if ratio < 0.85 else "neutral")
        red_bias.append({
            "ball": n, "observed": obs,
            "expected": round(red_expected, 2),
            "ratio": round(ratio, 4),
            "chi2_contrib": round(chi2, 4),
            "flag": flag,
        })

    # 蓝球: 每期1个蓝球 → N次抽球
    blue_count = Counter()
    for row in all_data:
        blue_count[row[7]] += 1

    blue_expected = N / 16
    blue_bias = []
    blue_chi2_total = 0.0
    for n in range(1, 17):
        obs = blue_count.get(n, 0)
        chi2 = (obs - blue_expected) ** 2 / blue_expected if blue_expected > 0 else 0
        blue_chi2_total += chi2
        ratio = obs / blue_expected if blue_expected > 0 else 1.0
        flag = "hot" if ratio > 1.2 else ("cold" if ratio < 0.8 else "neutral")
        # 蓝球阈值 ±20% 比红球 ±15% 宽松，因蓝球样本量小 (1/期 vs 6/期)
        blue_bias.append({
            "ball": n, "observed": obs,
            "expected": round(blue_expected, 2),
            "ratio": round(ratio, 4),
            "chi2_contrib": round(chi2, 4),
            "flag": flag,
        })

    # 卡方检验 (df = 32 for red, 15 for blue)
    # 使用 Wilson-Hilferty 近似计算 p-value
    red_df = 32
    blue_df = 15
    # Bonferroni 校正: 33红球+16蓝球=49次独立检验
    # α = 0.05 / 49 ≈ 0.00102
    # 来源: Bonferroni, C.E. (1936) "Teoria statistica delle classi e calcolo delle probabilità"
    # Fisher 0.05 为约定非教条 (Fisher 1925 §43), 多重比较须校正
    BONFERRONI_ALPHA = 0.05 / 49  # ≈ 0.00102

    red_p = _chi2_pvalue(red_chi2_total, red_df)
    blue_p = _chi2_pvalue(blue_chi2_total, blue_df)

    # 逐球Bonferroni校正: 每个球号单独的卡方贡献对应p值
    # df=1, chi2临界值: 3.841(0.05), 6.635(0.01), 8.708(0.003125), 10.138(0.001515)
    # 红球: 33个独立检验 → α=0.05/33≈0.001515 → χ²≈10.1
    # 蓝球: 16个独立检验 → α=0.05/16≈0.003125 → χ²≈8.7
    # 来源: Bonferroni 1936 + scipy.stats.chi2.ppf(1-α, 1) 由 Claude 验证
    RED_BALL_BONFERRONI_CHI2 = 10.1
    BLUE_BALL_BONFERRONI_CHI2 = 8.7

    def _ball_significant(chi2_contrib, threshold):
        """单球卡方贡献是否显著 (各自Bonferroni校正阈值)"""
        return chi2_contrib > threshold

    for b in red_bias:
        b["bonferroni_significant"] = _ball_significant(b["chi2_contrib"], RED_BALL_BONFERRONI_CHI2)
    for b in blue_bias:
        b["bonferroni_significant"] = _ball_significant(b["chi2_contrib"], BLUE_BALL_BONFERRONI_CHI2)

    return {
        "ok": True,
        "total_draws": N,
        "bonferroni_alpha": round(BONFERRONI_ALPHA, 6),
        "bonferroni_n_tests": 49,
        "red": {
            "df": red_df,
            "chi2": round(red_chi2_total, 4),
            "p_value": round(red_p, 6),
            "significant": red_p < BONFERRONI_ALPHA,
            "balls": sorted(red_bias, key=lambda x: -abs(x["ratio"] - 1)),
        },
        "blue": {
            "df": blue_df,
            "chi2": round(blue_chi2_total, 4),
            "p_value": round(blue_p, 6),
            "significant": blue_p < BONFERRONI_ALPHA,
            "balls": sorted(blue_bias, key=lambda x: -abs(x["ratio"] - 1)),
        },
    }


def _chi2_pvalue(chi2, df):
    """Wilson-Hilferty 近似: chi2 p-value (精度 ~0.001 for df > 10)"""
    if df <= 0:
        return 1.0
    # WH transformation: z = ((chi2/df)^(1/3) - 1 + 2/(9*df)) / sqrt(2/(9*df))
    x = chi2 / df
    z = (x ** (1/3) - 1 + 2 / (9 * df)) / math.sqrt(2 / (9 * df))
    # Normal CDF approximation (Abramowitz & Stegun 26.2.17)
    p = _norm_sf(z)
    return p


def _norm_sf(z):
    """标准正态生存函数 P(Z > z), 误差 < 7.5e-8"""
    # Abramowitz & Stegun 7.1.26 approximation
    b0, b1, b2, b3, b4, b5 = 0.2316419, 0.319381530, -0.356563782, 1.781477937, -1.821255978, 1.330274429
    t = 1 / (1 + b0 * abs(z))
    phi = 1 - (1 / math.sqrt(2 * math.pi)) * math.exp(-z * z / 2) * (
        b1 * t + b2 * t**2 + b3 * t**3 + b4 * t**4 + b5 * t**5)
    if z >= 0:
        return 1.0 - phi
    return phi
