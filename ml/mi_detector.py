"""互信息热力图 — 检测红球号码间的非独立结构

当前 bias_detector.py 只检测边际频率偏差 (P(#14) ≠ 1/33)。
本模块检测联合分布偏差 (P(#14, #06) ≠ P(#14)×P(#06))。

理论:
  - 边际均匀 ≠ 联合均匀
  - MI(X,Y) = Σ P(x,y) log₂[P(x,y) / (P(x)P(y))]
  - 真随机 → MI ≈ 0 (bits)
  - 非随机 → MI > 0 (号码间存在依赖)
  - Bootstrap置换检验: 打乱列标签, 重算MI → 经验p值

数学:
  - 2009期 × C(33,2)=528对, 每对2×2列联表
  - Bonferroni: α=0.05/528 ≈ 9.47×10⁻⁵
  - Bootstrap 1000次 → 精度 ±0.03

用法: python3 ml/mi_detector.py
"""
import sys, os, math, random
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_data():
    from server.db import load_draws
    return load_draws()


def co_occurrence_counts(data):
    """计算每对号码的共现计数.
    
    对每期开奖的6个红球中任意一对 (i,j), count[i,j] += 1.
    C(6,2)=15对/期 × 2000期 = 30000对次观测.
    """
    counts = {}
    for i in range(1, 34):
        for j in range(i+1, 34):
            counts[(i, j)] = 0
    
    for row in data:
        reds = sorted(row[1:7])
        for a in range(6):
            for b in range(a+1, 6):
                counts[(reds[a], reds[b])] += 1
    
    return counts


def mutual_information(n_ij, n_i, n_j, n_total):
    """计算一对号码的互信息.
    
    P(i,j) = n_ij / n_total
    P(i) = n_i / n_total
    P(j) = n_j / n_total
    
    如果从未共现: n_ij=0 → 该项贡献为 0 (lim x→0 x log x = 0)
    如果独立: P(i,j) = P(i)P(j) → MI = 0
    """
    n_draws = n_total
    
    # 四个格的计数:
    # (出现, 出现) = n_ij
    # (出现, 不出现) = n_i - n_ij
    # (不出现, 出现) = n_j - n_ij
    # (不出现, 不出现) = n_draws - n_i - n_j + n_ij
    
    mi = 0.0
    cells = [
        n_ij,
        n_i - n_ij,
        n_j - n_ij,
        n_draws - n_i - n_j + n_ij,
    ]
    
    for cell in cells:
        if cell <= 0:
            continue
        p_xy = cell / n_draws
        # 边缘概率
        if cell == n_ij:
            p_x = n_i / n_draws
            p_y = n_j / n_draws
        elif cell == (n_i - n_ij):
            p_x = n_i / n_draws
            p_y = (n_draws - n_j) / n_draws
        elif cell == (n_j - n_ij):
            p_x = (n_draws - n_i) / n_draws
            p_y = n_j / n_draws
        else:
            p_x = (n_draws - n_i) / n_draws
            p_y = (n_draws - n_j) / n_draws
        
        if p_x > 0 and p_y > 0:
            mi += p_xy * math.log2(p_xy / (p_x * p_y))
    
    return mi


def bootstrap_mi_test(pair_counts, n_draws, n_bootstrap=1000):
    """Bootstrap置换检验: 对每对号码打乱列标签, 建立MI零分布."""
    # 计算单号码出现次数
    single_counts = Counter()
    for (i, j), c in pair_counts.items():
        single_counts[i] += c
        single_counts[j] += c
    
    # 每号码总出现次数
    n_i = {}
    for n in range(1, 34):
        # 每期有 C(5,1)种方式与另一个号码配对, ×6个位置选中的概率
        # 更简单: n_i = single_counts[n] / 5 (因为每个号码在C(6,2)中出现了5次)
        n_i[n] = single_counts[n] // 5 if single_counts[n] > 0 else 0
    
    # 实际MI
    actual_mi = {}
    for (i, j), n_ij in pair_counts.items():
        actual_mi[(i, j)] = mutual_information(n_ij, n_i[i], n_i[j], n)
    
    # Bootstrap: 打乱每期红球组合中的列标签 (保持行结构不变)
    boot_mi = {(i, j): [] for (i, j) in pair_counts}
    
    for _ in range(n_bootstrap):
        shuffled_counts = {(i, j): 0 for (i, j) in pair_counts}
        for row in load_data():
            reds = sorted(row[1:7])
            # 打乱: 保持6个红球的存在性, 但随机重新分配号码
            all_nums = list(range(1, 34))
            random.shuffle(all_nums)
            # 生成6个新号码
            shuffled_reds = sorted(random.sample(all_nums, 6))
            for a in range(6):
                for b in range(a+1, 6):
                    shuffled_counts[(shuffled_reds[a], shuffled_reds[b])] += 1
        
        for (i, j), n_ij_shuffled in shuffled_counts.items():
            mi_s = mutual_information(n_ij_shuffled, n_i[i], n_i[j], n_draws)
            boot_mi[(i, j)].append(mi_s)
    
    # 经验p值
    results = {}
    for pair, actual in actual_mi.items():
        null_dist = sorted(boot_mi[pair])
        # 右尾: MI > 实际值的比例
        right_tail = sum(1 for m in null_dist if m >= actual) / n_bootstrap
        results[pair] = {
            "n_ij": pair_counts[pair],
            "mi_bits": round(actual, 6),
            "p_value": round(right_tail, 4),
            "significant_05": right_tail < 0.05,
            "significant_bonf": right_tail < (0.05 / 528),  # ≈ 9.47e-5
        }
    
    return results


def run():
    data = load_data()
    n = len(data)
    pair_counts = co_occurrence_counts(data)
    
    print("=" * 70)
    print("互信息热力图 — 红球号码对非独立检测")
    print("=" * 70)
    print(f"数据: {n} 期, 号码对: C(33,2)=528")
    print(f"Bonferroni 阈值: 0.05/528 = {0.05/528:.6f}")
    print(f"如果号码完全独立 → 所有对 MI ≈ 0")
    print()
    
    # 计算实际MI (不用bootstrap先看分布)
    single_counts = Counter()
    for (i, j), c in pair_counts.items():
        single_counts[i] += c
        single_counts[j] += c
    
    n_i = {num: single_counts[num] // 5 for num in range(1, 34)}
    
    actual_mi = {}
    for (i, j), n_ij in pair_counts.items():
        actual_mi[(i, j)] = mutual_information(n_ij, n_i[i], n_i[j], n)
    
    # 排序
    ranked = sorted(actual_mi.items(), key=lambda x: -x[1])
    
    print("Top-15 互信息最高号码对:")
    for (i, j), mi in ranked[:15]:
        n_ij = pair_counts[(i, j)]
        expected = n_i[i] * n_i[j] / n if n > 0 else 0
        direction = "↑多" if n_ij > expected else "↓少"
        print(f"  ({i:02d},{j:02d}): MI={mi:.6f} bits | "
              f"共现={n_ij}, 期望={expected:.1f} | {direction}")
    
    print()
    print("MI 分布统计:")
    all_mi = [v for v in actual_mi.values()]
    print(f"  均值: {sum(all_mi)/len(all_mi):.6f}")
    print(f"  最大: {max(all_mi):.6f}")
    print(f"  最小: {min(all_mi):.6f}")
    print(f"  标准差: {(sum((x - sum(all_mi)/len(all_mi))**2 for x in all_mi)/len(all_mi))**0.5:.6f}")
    
    # Bootstrap (只用200次, 因为528对 × 200 × 2000期 = 太慢)
    # 改用解析逼近: MI × 2n ~ χ²(1)
    # 计算χ² = 2 × n_draws × MI
    print()
    print("χ² 检验 (MI × 2n ~ χ²(1), 大样本近似):")
    chi2_results = []
    for (i, j), mi in actual_mi.items():
        chi2 = 2 * n * mi
        # χ²(1) p值: p-value = 1 - F(chi2; 1)
        # F(x;1) = erf(sqrt(x/2))
        import math
        if chi2 > 0:
            z = math.sqrt(chi2 / 2)
            p_val = 2 * (1 - _norm_cdf(z))  # 双尾
        else:
            p_val = 1.0
        chi2_results.append(((i, j), mi, chi2, p_val))
    
    chi2_results.sort(key=lambda x: -x[3])  # 按p值升序 (最显著在前)
    
    bonf_pass = [(p, mi, chi2, pv) for p, mi, chi2, pv in chi2_results 
                 if pv < 0.05/528]
    
    if bonf_pass:
        print(f"  Bonferroni 显著对: {len(bonf_pass)}对")
        for (i, j), mi, chi2, pv in bonf_pass[:10]:
            n_ij = pair_counts[(i, j)]
            exp = n_i[i] * n_i[j] / n
            print(f"    ({i:02d},{j:02d}): MI={mi:.6f} χ²={chi2:.2f} p={pv:.6f} "
                  f"共现={n_ij} 期望={exp:.1f}")
    else:
        print(f"  Bonferroni 显著对: 0")
        print(f"  → 号码间无显著依赖结构")
        print(f"  → 边际独立假设成立 (联合=边际乘积)")
        # 看有没有接近显著的
        close = [(p, mi, chi2, pv) for p, mi, chi2, pv in chi2_results if pv < 0.01]
        if close:
            print(f"  → 但 {len(close)} 对在 p<0.01 水平 (未通过Bonferroni)")
            for (i, j), mi, chi2, pv in close:
                print(f"      ({i:02d},{j:02d}): p={pv:.4f}")
    
    return {
        "n_draws": n,
        "n_pairs": 528,
        "top_pairs": [{"pair": [i, j], "mi": round(mi, 6), "n_ij": pair_counts[(i,j)]} 
                       for (i,j), mi in ranked[:20]],
        "bonferroni_significant": len(bonf_pass),
        "verdict": "JOINT_INDEPENDENT" if len(bonf_pass) == 0 else "NON_INDEPENDENT",
    }


def _norm_cdf(x):
    """标准正态CDF."""
    if x < 0:
        return 1 - _norm_cdf(-x)
    b = [0.2316419, 0.319381530, -0.356563782, 1.781477937, -1.821255978, 1.330274429]
    t = 1 / (1 + b[0] * x)
    pdf = math.exp(-x * x / 2) / math.sqrt(2 * math.pi)
    return 1 - pdf * sum(b[i+1] * t**(i+1) for i in range(5))


if __name__ == "__main__":
    run()
