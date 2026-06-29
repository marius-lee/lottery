"""贝叶斯偏差发现引擎 — 不预测未来，检测静态物理偏差

核心假设转变:
  旧: P(d_{t+1} | d_t, d_{t-1}, ...) ≠ P(d_{t+1})  [时序预测]
  新: P(号码=i) ≠ 1/33  [静态偏差, i.i.d.但非均匀]

理论基础:
  - 泰国物理实验 (2017): 1%轻球在空气吹球系统中被显著多抽 (p<0.05)
  - 双色球使用重力落球 — 类似物理约束存在
  - 2009期 × 6红球 = 12,054次红球观测
  - 检测灵敏度: ~2%偏差在95%置信水平下可检测 [数学: 比例检验功效分析]

分层模型:
  L1: 号码级 — 33个红球各有潜频率 θ_i, H0: θ_i=1/33
  L2: 位置级 — 6个位置各有不同的33维分布
  L3: 蓝球级 — 16个蓝球各有潜频率 φ_j, H0: φ_j=1/16
  L4: 联合效应 — 独立偏置假设下, C(33,6)组合概率 = ∏偏差因子

推断方法:
  - Beta-Binomial共轭: θ_i ~ Beta(α, β), 后验 = Beta(α+count, β+N-count)
  - 经验贝叶斯收缩: 用全数据估计先验超参数 α, β → 收缩极端值
  - Jeffreys先验: Beta(0.5, 0.5) 无信息基线
  - 95%最高后验密度区间 (HPD)
  - 联合偏差效应: P(组合) / P_uniform(组合) → 投注加权
"""
import math
from collections import Counter


def load_data():
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from server.db import load_draws
    return load_draws()


# ═══════════════════════════════════════════════════════════════
# L1: 号码级偏差 (33个红球)
# ═══════════════════════════════════════════════════════════════

def number_level_analysis(data):
    """Beta-Binomial共轭分析: 每个号码的后验分布."""
    n_draws = len(data)
    n_obs = n_draws * 6  # 每期6个红球

    # 计数
    counts = Counter()
    for row in data:
        for n in row[1:7]:
            counts[n] += 1

    # [统计] 先验选择: Jeffreys Beta(0.5, 0.5) 和 Uniform Beta(1, 1)
    results = {}
    for prior_name, (alpha_prior, beta_prior) in [
        ("Jeffreys", (0.5, 0.5)),
        ("Uniform", (1.0, 1.0)),
    ]:
        post = {}
        for n in range(1, 34):
            k = counts.get(n, 0)
            # 后验 Beta(α+k, β+N-k)
            a_post = alpha_prior + k
            b_post = beta_prior + (n_obs - k)
            posterior_mean = a_post / (a_post + b_post)
            posterior_std = math.sqrt(a_post * b_post / ((a_post + b_post)**2 * (a_post + b_post + 1)))

            # 95% HPD近似 (正态近似) [数学: Beta→正态当a,b>10]
            if a_post > 10 and b_post > 10:
                hpd_lo = posterior_mean - 1.96 * posterior_std
                hpd_hi = posterior_mean + 1.96 * posterior_std
            else:
                hpd_lo = hpd_hi = None

            uniform_prob = 1.0 / 33  # [数学] H0: 均匀分布
            # Bayes因子近似: 后验概率比 / 先验概率比
            deviation_ratio = posterior_mean / uniform_prob

            post[n] = {
                "count": k,
                "expected": n_obs / 33,  # ~365.3
                "posterior_mean": round(posterior_mean, 6),
                "posterior_std": round(posterior_std, 6),
                "hpd_95": (round(hpd_lo, 6) if hpd_lo else None,
                           round(hpd_hi, 6) if hpd_hi else None),
                "deviation_pct": round((deviation_ratio - 1) * 100, 2),
                "significant": (hpd_lo is not None and
                               (hpd_lo > uniform_prob or hpd_hi < uniform_prob)),
            }

        results[prior_name] = post

    return {"n_draws": n_draws, "n_obs": n_obs, "priors": results}


# ═══════════════════════════════════════════════════════════════
# L2: 位置级偏差 (6个位置各自的33维分布)
# ═══════════════════════════════════════════════════════════════

def position_level_analysis(data):
    """每位置独立Beta-Binomial分析.

    位置1-6的开奖号码可能存在不同的物理偏差.
    """
    n_draws = len(data)
    results = {}
    for pos in range(6):
        counts = Counter()
        for row in data:
            reds = sorted(row[1:7])
            counts[reds[pos]] += 1

        post = {}
        for n in range(1, 34):
            k = counts.get(n, 0)
            a_post = 0.5 + k
            b_post = 0.5 + (n_draws - k)
            posterior_mean = a_post / (a_post + b_post)
            posterior_std = math.sqrt(a_post * b_post / ((a_post + b_post)**2 * (a_post + b_post + 1)))

            uniform_prob = 1.0 / 33
            deviation_ratio = posterior_mean / uniform_prob

            post[n] = {
                "count": k,
                "deviation_pct": round((deviation_ratio - 1) * 100, 2),
                "significant": (posterior_mean - 1.96 * posterior_std > uniform_prob or
                               posterior_mean + 1.96 * posterior_std < uniform_prob),
            }
        results[pos] = post

    # 跨位置一致性检验: 如果同一号码在所有6个位置都偏多→强信号
    cross_pos = {}
    for n in range(1, 34):
        deviations = [results[pos][n]["deviation_pct"] for pos in range(6)]
        all_positive = all(d > 0 for d in deviations)
        all_negative = all(d < 0 for d in deviations)
        consensus = "UP" if all_positive else ("DOWN" if all_negative else "MIXED")
        cross_pos[n] = {
            "deviations": deviations,
            "consensus": consensus,
            "mean_deviation": round(sum(deviations) / 6, 2),
        }
    return {"positions": results, "cross_position": cross_pos}


# ═══════════════════════════════════════════════════════════════
# L3: 蓝球级偏差 (16个蓝球)
# ═══════════════════════════════════════════════════════════════

def blue_level_analysis(data):
    """蓝球频率偏差分析."""
    n_draws = len(data)
    counts = Counter()
    for row in data:
        counts[row[7]] += 1

    results = {}
    for n in range(1, 17):
        k = counts.get(n, 0)
        a_post = 0.5 + k
        b_post = 0.5 + (n_draws - k)
        posterior_mean = a_post / (a_post + b_post)
        posterior_std = math.sqrt(a_post * b_post / ((a_post + b_post)**2 * (a_post + b_post + 1)))

        uniform_prob = 1.0 / 16
        deviation_ratio = posterior_mean / uniform_prob
        hpd_lo = posterior_mean - 1.96 * posterior_std
        hpd_hi = posterior_mean + 1.96 * posterior_std

        results[n] = {
            "count": k,
            "expected": n_draws / 16,
            "posterior_mean": round(posterior_mean, 6),
            "deviation_pct": round((deviation_ratio - 1) * 100, 2),
            "significant": (hpd_lo > uniform_prob or hpd_hi < uniform_prob),
        }

    # χ²检验
    expected = n_draws / 16
    chi2 = sum((counts.get(b, 0) - expected)**2 / expected for b in range(1, 17))
    # [统计] df=15, p<0.05临界=25.0, p<0.01临界=30.6
    chi2_significant = chi2 > 25.0

    return {"results": results, "chi2": round(chi2, 2),
            "chi2_significant": chi2_significant,
            "df": 15}


# ═══════════════════════════════════════════════════════════════
# L4: 联合偏差效应 — 单注中奖概率修正
# ═══════════════════════════════════════════════════════════════

def joint_effect_analysis(data, number_posterior):
    """估算偏差对组合概率的影响.

    假设: 红球独立 (简化). 实际中有共现约束, 但作为一阶近似.
    联合偏差因子 = ∏(deviation_ratio_i) for 选中的6个红球
    """
    # 从独立偏差计算选号收益
    # 如果每个号码偏差+2%, 选中6个此类号码:
    #   P(全中) = P_uniform × ∏(1 + 0.02) = P_uniform × 1.02^6 ≈ P_uniform × 1.126
    #   即收益增加12.6% (相对随机选号)

    # 偏差排序
    deviations = []
    for n in range(1, 34):
        d = number_posterior[n]["deviation_pct"]
        deviations.append((n, d))

    deviations.sort(key=lambda x: -x[1])

    # top-6 正偏差号码组合
    top6 = [n for n, _ in deviations[:6]]
    top6_boost = math.prod(1 + number_posterior[n]["deviation_pct"] / 100 for n in top6)

    # bottom-6 负偏差号码 (应回避的)
    bottom6 = [n for n, _ in deviations[-6:]]
    bottom6_penalty = math.prod(1 + number_posterior[n]["deviation_pct"] / 100 for n in bottom6)

    return {
        "top6_bias_numbers": top6,
        "top6_probability_boost_pct": round((top6_boost - 1) * 100, 2),
        "bottom6_avoid_numbers": bottom6,
        "bottom6_probability_penalty_pct": round((1 - bottom6_penalty) * 100, 2),
        "note": "独立假设一阶近似, 实际需考虑组合约束",
    }


# ═══════════════════════════════════════════════════════════════
# 经验贝叶斯收缩
# ═══════════════════════════════════════════════════════════════

def empirical_bayes_shrink(counts, n_total, n_categories):
    """经验贝叶斯: 用全数据估计先验超参数, 收缩极端值.

    先验: Beta(α, β), 超参数通过矩估计法: [统计: 矩估计, Casella+Berger 2002 Ch7]
      μ = 样本均值 = 1/K (均匀)
      方差 = Var(频率) - 二项方差
    """
    K = n_categories
    observed_rates = [counts.get(i, 0) / n_total for i in range(1, K + 1)]
    mean_rate = sum(observed_rates) / K
    var_rate = sum((r - mean_rate)**2 for r in observed_rates) / (K - 1) if K > 1 else 0

    # [数学] 二项方差 = p(1-p)/n. 超出部分来自Beta先验的过离散
    binom_var = mean_rate * (1 - mean_rate) / n_total
    overdispersion = max(0, var_rate - binom_var)

    if overdispersion > 0 and mean_rate > 0:
        # [数学] Beta先验矩估计
        # α/(α+β) = μ, αβ/((α+β)²(α+β+1)) ≈ overdispersion
        alpha_prior = mean_rate * (mean_rate * (1 - mean_rate) / overdispersion - 1)
        beta_prior = (1 - mean_rate) * (mean_rate * (1 - mean_rate) / overdispersion - 1)
        alpha_prior = max(0.1, alpha_prior)
        beta_prior = max(0.1, beta_prior)
    else:
        # [统计] 接近均匀, 用弱先验
        alpha_prior = 1.0
        beta_prior = 1.0

    # 收缩后验
    shrunk = {}
    for i in range(1, K + 1):
        k = counts.get(i, 0)
        a_post = alpha_prior + k
        b_post = beta_prior + (n_total - k)
        shrunk[i] = {
            "count": k,
            "raw_rate": k / n_total,
            "shrunk_mean": a_post / (a_post + b_post),
            "shrinkage_factor": round(alpha_prior / (alpha_prior + n_total), 4),
        }

    return {
        "alpha_prior": round(alpha_prior, 4),
        "beta_prior": round(beta_prior, 4),
        "overdispersion": round(overdispersion, 8),
        "prior_mean": round(alpha_prior / (alpha_prior + beta_prior), 6),
        "shrunk": shrunk,
    }


# ═══════════════════════════════════════════════════════════════
# 蒙特卡洛Bootstrap
# ═══════════════════════════════════════════════════════════════

def bootstrap_significance(data, n_bootstrap=5000):
    """Bootstrap重采样检验频率偏差的统计显著性.

    对2000期做5000次重采样, 计算每号码的经验p值和置信区间.
    [统计] 5000次Bootstrap: 95%CI精度≈±0.7个百分点
    """
    import random
    n = len(data)
    n_obs = n * 6

    # 实际计数
    actual_counts = Counter()
    for row in data:
        for num in row[1:7]:
            actual_counts[num] += 1

    # Bootstrap
    boot_counts = {num: [] for num in range(1, 34)}
    for _ in range(n_bootstrap):
        sample_counts = Counter()
        for _ in range(n):
            idx = random.randint(0, n - 1)
            for num in data[idx][1:7]:
                sample_counts[num] += 1
        for num in range(1, 34):
            boot_counts[num].append(sample_counts.get(num, 0))

    # 经验p值 (双尾)
    results = {}
    for num in range(1, 34):
        actual = actual_counts.get(num, 0)
        boot_dist = sorted(boot_counts[num])
        # 大于等于actual的比例 → 右尾p值
        right_tail = sum(1 for c in boot_counts[num] if c >= actual) / n_bootstrap
        left_tail = sum(1 for c in boot_counts[num] if c <= actual) / n_bootstrap
        p_two_tailed = 2 * min(right_tail, left_tail)

        # Bootstrap CI
        ci_lo = boot_dist[int(n_bootstrap * 0.025)]
        ci_hi = boot_dist[int(n_bootstrap * 0.975)]
        expected = n_obs / 33

        results[num] = {
            "actual": actual,
            "expected": round(expected, 1),
            "boot_mean": round(sum(boot_counts[num]) / n_bootstrap, 1),
            "ci_95": (ci_lo, ci_hi),
            "p_value": round(p_two_tailed, 4),
            "significant_05": p_two_tailed < 0.05,
            "significant_01": p_two_tailed < 0.01,
            # Bonferroni校正 (33重检验)
            "significant_bonf": p_two_tailed < 0.05 / 33,  # ≈ 0.0015
        }

    return results


# ═══════════════════════════════════════════════════════════════
# 主函数
# ═══════════════════════════════════════════════════════════════

def run():
    data = load_data()
    n = len(data)

    print(f"=" * 60)
    print(f"贝叶斯偏差发现引擎")
    print(f"=" * 60)
    print(f"数据: {n} 期, 观测数: {n*6} 红 + {n} 蓝")
    print(f"核心问题: P(号码) 是否 ≠ 均匀分布?")
    print()

    # ── L1: 号码级 ──
    print(f"{'─' * 60}")
    print(f"L1: 红球号码级偏差 (Beta-Binomial, Jeffreys先验)")
    print()
    l1 = number_level_analysis(data)
    jp = l1["priors"]["Jeffreys"]

    sig_up = [(n, jp[n]["deviation_pct"]) for n in range(1, 34) if jp[n]["significant"]]
    sig_up.sort(key=lambda x: -x[1])
    print(f"  显著偏差号码 (95% HPD不包含1/33):")
    if sig_up:
        for n, dev in sig_up[:10]:
            cnt = jp[n]["count"]
            exp = jp[n]["expected"]
            print(f"    #{n:02d}: {cnt}次 (期望{exp:.0f}) | {dev:+.1f}% | 显著")
    else:
        print(f"    无 — 所有号码的95% HPD都包含1/33")

    # Top/Bottom 偏差
    all_dev = [(n, jp[n]["deviation_pct"], jp[n]["count"]) for n in range(1, 34)]
    all_dev.sort(key=lambda x: -x[1])
    print()
    print(f"  Top-5 正偏差:")
    for n, dev, cnt in all_dev[:5]:
        print(f"    #{n:02d}: {cnt}次 | {dev:+.1f}%")
    print(f"  Bottom-5 负偏差:")
    for n, dev, cnt in all_dev[-5:]:
        print(f"    #{n:02d}: {cnt}次 | {dev:+.1f}%")

    # ── L2: 位置级 ──
    print(f"\n{'─' * 60}")
    print(f"L2: 位置级偏差 (6个位置独立分析)")
    l2 = position_level_analysis(data)
    cross = l2["cross_position"]
    consensus_up = [n for n in range(1, 34) if cross[n]["consensus"] == "UP"]
    consensus_down = [n for n in range(1, 34) if cross[n]["consensus"] == "DOWN"]
    print(f"  全位置一致偏多: {consensus_up}")
    print(f"  全位置一致偏少: {consensus_down}")

    # ── L3: 蓝球 ──
    print(f"\n{'─' * 60}")
    print(f"L3: 蓝球偏差")
    l3 = blue_level_analysis(data)
    print(f"  χ² = {l3['chi2']:.2f} (df=15, p<0.05临界=25.0)")
    print(f"  χ²显著: {l3['chi2_significant']}")
    blue_sig = [b for b in range(1, 17) if l3["results"][b]["significant"]]
    if blue_sig:
        for b in blue_sig:
            r = l3["results"][b]
            print(f"   蓝{b:02d}: {r['count']}次 | {r['deviation_pct']:+.1f}% | 显著")
    else:
        print(f"  无显著蓝球偏差")
    # 蓝球top5
    blue_devs = [(b, l3["results"][b]["deviation_pct"]) for b in range(1, 17)]
    blue_devs.sort(key=lambda x: -x[1])
    print(f"  Top-3 蓝球: {[(b, f'{d:+.1f}%') for b, d in blue_devs[:3]]}")

    # ── L4: 联合效应 ──
    print(f"\n{'─' * 60}")
    print(f"L4: 联合偏差效应 (独立假设一阶近似)")
    l4 = joint_effect_analysis(data, jp)
    print(f"  Top-6正偏差号码: {l4['top6_bias_numbers']}")
    print(f"  组合概率增益: {l4['top6_probability_boost_pct']:+.2f}%")
    print(f"  Bottom-6回避号码: {l4['bottom6_avoid_numbers']}")

    # ── 经验贝叶斯 ──
    print(f"\n{'─' * 60}")
    print(f"经验贝叶斯收缩")
    red_counts = Counter()
    for row in data:
        for n in row[1:7]:
            red_counts[n] += 1
    eb = empirical_bayes_shrink(red_counts, n * 6, 33)
    print(f"  先验: Beta({eb['alpha_prior']:.2f}, {eb['beta_prior']:.2f})")
    print(f"  过离散: {eb['overdispersion']:.6f} (0=完全均匀)")
    sf = eb['shrunk'][1]['shrinkage_factor']  # 所有号码收缩因子相同
    print(f"  收缩因子: {sf:.4f} (越小=先验越强=数据偏差越小)")

    # ── Bootstrap ──
    print(f"\n{'─' * 60}")
    print(f"Bootstrap显著性检验 (5000次重采样)")
    boot = bootstrap_significance(data)
    boot_sig = [(n, boot[n]["p_value"]) for n in range(1, 34) if boot[n]["significant_05"]]
    print(f"  p<0.05: {len(boot_sig)}个号码")
    boot_sig_01 = [(n, boot[n]["p_value"]) for n in range(1, 34) if boot[n]["significant_01"]]
    print(f"  p<0.01: {len(boot_sig_01)}个号码")
    boot_sig_bonf = [(n, boot[n]["p_value"]) for n in range(1, 34) if boot[n]["significant_bonf"]]
    print(f"  Bonferroni校正 (p<0.0015): {len(boot_sig_bonf)}个号码")
    if boot_sig_bonf:
        for n, p in boot_sig_bonf[:5]:
            print(f"    #{n:02d}: p={p:.4f} (Bonferroni显著)")

    
# ═══════════════════════════════════════════════════════
    # 综合判定 (系统门禁 — 严格标准)
    # ═══════════════════════════════════════════════════════
    print(f"\n{'═' * 60}")
    print(f"综合判定 (系统门禁)")
    print(f"{'═' * 60}")

    # [门禁] Bootstrap双尾 + Bonferroni校正 同时通过才算偏差
    bonferroni_pass = len(boot_sig_bonf) > 0
    overdispersion_pass = eb["overdispersion"] > 1e-6
    has_bias = bonferroni_pass and overdispersion_pass

    if bonferroni_pass:
        print(f"  Bootstrap Bonferroni: PASS ({len(boot_sig_bonf)}号码显著)")
    else:
        print(f"  Bootstrap Bonferroni: FAIL (0号码通过多重检验)")
    if overdispersion_pass:
        print(f"  经验贝叶斯过离散: PASS ({eb['overdispersion']:.6f} > 0)")
    else:
        print(f"  经验贝叶斯过离散: FAIL (≈0, 接近均匀)")

    print()
    if has_bias:
        print(f"✅ 门禁通过 — 存在统计可靠偏差")
        print(f"  → 偏差号码: {l4['top6_bias_numbers']}")
    else:
        print(f"❌ 门禁不通过 — 无可靠偏差证据")
        print(f"  → 预测策略无效, 纯覆盖设计")
        print(f"  → 选号 = C(33,6)均匀随机")

    # 时间鲁棒性: 偏差应跨时间稳定
    print(f"\n  ── 时间鲁棒性 ──")
    half = len(data) // 2
    recent_boot = bootstrap_significance(data[-half:], n_bootstrap=2000)
    recent_sig = [n for n in range(1, 34) if recent_boot[n].get("significant_bonf", False)]
    print(f"  前半段 Bonferroni: {len(boot_sig_bonf)}个, 后半段: {len(recent_sig)}个")
    time_stable = set(n for n,_ in boot_sig_bonf) & set(recent_sig) if boot_sig_bonf else set()
    if time_stable:
        print(f"  跨时间稳定: {sorted(time_stable)}")
    else:
        print(f"  跨时间不稳定 (非物理偏差)")

    print(f"{'═' * 60}")

    return {
        "verdict": "BIAS_DETECTED" if has_bias else "UNIFORM",
        "has_bias": has_bias,
        "bonferroni_pass": bonferroni_pass,
        "overdispersion_pass": overdispersion_pass,
        "time_stable": sorted(time_stable) if has_bias else [],
        "L1_number": l1,
        "L2_position": l2,
        "L3_blue": l3,
        "L4_joint": l4,
        "empirical_bayes": eb,
        "bootstrap": boot,
    }

if __name__ == "__main__":
    run()
