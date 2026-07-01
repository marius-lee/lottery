"""模算术/余数类分析 — 在商空间中检测系统性偏差

理论基础:
  - 红球 1-33 按 mod 3 落入 {0,1,2} 三余数类，mod 5 五类，mod 7 七类。
  - 如果开奖存在物理偏差，偏差会在特定余数类中累积——因为物理偏差
    不是均匀散布在 1..33 上，而是集中影响某些号码。
  - 卡方检验检测每类余数的历史频率偏离，显著偏离的余数类中
    的号码获得加权。

与频率统计正交: 频率高的号码如果分散在各余数类中，降维后余数类
分布可能仍均匀。只有在某些余数类集中偏高时才有信号。

用法:
  from ml.modular_math import compute_modular_weights
  red_w, diag = compute_modular_weights(data, window=200)
"""
import math


# 余数类映射: {余数 → [号码列表]}
def _mod_classes(mod):
    """返回 {余数: [号码...]} 和 每类期望概率"""
    classes = {}
    for n in range(1, 34):
        r = n % mod
        classes.setdefault(r, []).append(n)
    return classes


def _chi2_pvalue(chi2, df):
    """卡方分布右尾概率近似 (Wilson-Hilferty)"""
    if df <= 0 or chi2 <= 0:
        return 1.0
    z = ((chi2 / df) ** (1.0 / 3.0) - 1.0 + 2.0 / (9.0 * df)) / (2.0 / (9.0 * df)) ** 0.5
    return 0.5 * math.erfc(z / math.sqrt(2))


def compute_modular_weights(data, window=200, min_weight=0.5, max_weight=2.0):
    """对每个红球号码，基于余数类分析计算权重.

    对 mod 3/5/7 分别做卡方检验，显著偏离的余数类中的号码加权。

    Args:
        data: [[period, r1..r6, blue], ...] 按时间升序
        window: 回溯期数

    Returns:
        weights: [0.0]*34 (1-indexed)
        diag: 诊断信息
    """
    if not data:
        return [1.0] * 34, {"error": "no_data"}

    recent = data[-window:]
    weights = [1.0] * 34
    diag = {"n_periods": len(recent), "modules": {}}

    for mod in [3, 5, 7]:  # 三种模数
        classes = _mod_classes(mod)
        k = len(classes)  # 余数类数量 (mod=3→3类, mod=5→5类, mod=7→7类)

        # 统计每类在最近 window 期的出现次数
        obs = {r: 0 for r in classes}
        total_picks = 0
        for row in recent:
            for r in row[1:7]:
                obs[r % mod] += 1
                total_picks += 1

        # 每类期望 = 每类号码数 / 33 * 总出现数
        exp = {}
        for r, nums in classes.items():
            exp[r] = total_picks * len(nums) / 33.0

        # 卡方检验
        chi2 = 0.0
        for r in classes:
            e = exp[r]
            if e > 0:
                chi2 += (obs[r] - e) ** 2 / e
        df = k - 1
        p_val = _chi2_pvalue(chi2, df)

        mod_diag = {
            "chi2": round(chi2, 3),
            "p_value": round(p_val, 4),
            "significant": p_val < 0.05,
            "residue_counts": {},
        }

        # 若显著 (p<0.05)，对偏离均匀的余数类中的号码加权
        if p_val < 0.05:
            for r in classes:
                e = exp[r]
                if e <= 0:
                    continue
                deviation = (obs[r] - e) / e  # 正→偏多, 负→偏少
                mod_diag["residue_counts"][str(r)] = {
                    "nums": classes[r],
                    "observed": obs[r],
                    "expected": round(e, 1),
                    "deviation": round(deviation, 3),
                }
                if deviation > 0:
                    boost = max(min_weight, min(max_weight, 1.0 + deviation * 0.5))
                    for num in classes[r]:
                        weights[num] = max(weights[num], boost)
                elif deviation < -0.3:
                    # 显著偏少的余数类 → 轻微降权
                    penalty = max(min_weight, 1.0 + deviation * 0.3)
                    for num in classes[r]:
                        weights[num] = min(weights[num], penalty)

        diag["modules"][str(mod)] = mod_diag

    # 汇总
    diag["n_hot"] = sum(1 for n in range(1, 34) if weights[n] > 1.1)
    diag["hot"] = sorted(
        [(n, round(weights[n], 3)) for n in range(1, 34) if weights[n] > 1.1],
        key=lambda x: -x[1])[:8]

    return weights, diag
