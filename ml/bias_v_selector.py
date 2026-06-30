"""偏差驱动的动态热号池大小选择器 — 替代硬编码 v=15

理论基础:
  - EV ∝ P(6红全在池) ∝ C(v,6)/C(33,6) — v 越大越好 (数学)
  - 信噪比 ∝ 1/v — v 越大, 越后面的号码偏差越弱 (经验)
  - 最优 v = argmax_{v} P(6红全在池) × 贪心覆盖率 × 信号折扣(v)

信号折扣: 如果第 i 个排名号码的偏差降到了噪声水平以下,
那从 i 开始往后的号码不再提供预测信号, 只是随机噪声。

三层判定:
  L1: Bootstrap Bonferroni — 硬门禁 (多重检验校正后的可靠信号)
  L2: HPD 95% — 软信号 (贝叶斯后验区间不包含均匀值的号码)
  L3: 偏差幅度排序 — 信号强度连谱

决策表:
  - Bonferroni ≥ 3 个 AND 时间鲁棒 → v = 8-10 (强信号, 窄池高命中)
  - Bonferroni 1-2 个 → v = 11-13 (中信号)
  - Bonferroni 0 个 BUT HPD ≥ 3 个 → v = 14-16 (弱信号, 稍放宽)
  - Bonferroni 0 个 AND HPD < 3 个 → v = 15 (纯覆盖, 无信号)
"""
import math
from typing import Tuple, List, Dict, Optional
from dataclasses import dataclass


@dataclass
class BiasVResult:
    """偏差驱动的 v 选择结果."""
    v: int                          # 推荐的热号池大小
    signal_level: str               # "strong" | "moderate" | "weak" | "none"
    fdr_count: int                  # BH-FDR 显著号码数 [Benjamini & Hochberg 1995]
    hpd_count: int                  # HPD 95% 显著号码数
    time_stable_count: int          # 跨时间稳定号码数
    top_numbers: List[int]          # 推荐的热号 (v个)
    deviation_scores: Dict[int, float]  # 所有号码的偏差% (已排序)
    reasoning: str                  # 人类可读的理由


def _run_bias_detection(data) -> dict:
    """运行偏差检测引擎, 返回关键信号."""
    from ml.bias_detector import (
        number_level_analysis, bootstrap_significance,
        empirical_bayes_shrink,
    )
    from collections import Counter
    
    n = len(data)
    l1 = number_level_analysis(data)
    boot = bootstrap_significance(data)
    red_counts = Counter()
    for row in data:
        for num in row[1:7]:
            red_counts[num] += 1
    eb = empirical_bayes_shrink(red_counts, n * 6, 33)
    
    # BH-FDR 显著 [Benjamini & Hochberg 1995, JRSS-B 57(1):289-300]
    from ml.bias_detector import fdr_significant_flags
    p_values = [boot[num]["p_value"] for num in range(1, 34)]
    fdr_flags = fdr_significant_flags(p_values)
    fdr_sig = [(num, boot[num]["p_value"], boot[num]["actual"])
               for num in range(1, 34) if fdr_flags[num-1]]
    
    # HPD 95% 显著 (Jeffreys 先验)
    jp = l1["priors"]["Jeffreys"]
    hpd_sig = [(num, jp[num]["deviation_pct"])
               for num in range(1, 34) if jp[num]["significant"]]
    
    # 偏差幅度排序
    all_devs = [(num, jp[num]["deviation_pct"]) for num in range(1, 34)]
    all_devs.sort(key=lambda x: -x[1])
    
    # 时间鲁棒性 — FDR 校正 [Benjamini & Hochberg 1995]
    half = n // 2
    boot_recent = bootstrap_significance(data[-half:])
    recent_pvals = [boot_recent[num]["p_value"] for num in range(1, 34)]
    recent_flags = fdr_significant_flags(recent_pvals)
    recent_sig = [num for num in range(1, 34) if recent_flags[num-1]]
    time_stable = [num for num, _, _ in fdr_sig if num in recent_sig]
    
    return {
        "fdr_count": len(fdr_sig),
        "fdr_numbers": [num for num, _, _ in fdr_sig],
        "hpd_count": len(hpd_sig),
        "hpd_numbers": [num for num, _ in hpd_sig],
        "time_stable": time_stable,
        "time_stable_count": len(time_stable),
        "overdispersion": eb["overdispersion"],
        "deviation_ranking": all_devs,
        "deviation_map": {num: dev for num, dev in all_devs},
    }


def _signal_discount(rank: int, v: int, signal_strength: str) -> float:
    """第 rank 位的信号折扣因子.

    1.0 = 完全可信, 0.0 = 纯噪声.

    Args:
        rank: 1-based 排名 (1 = 最强信号)
        v: 总池大小
        signal_strength: "strong" | "moderate" | "weak" | "none"
    """
    if signal_strength == "none":
        return 1.0  # 无信号时, 所有号码等权 → 不折扣
    
    # 折扣曲线: sigmoid 型, 在 cutoff 点快速衰减
    # 折扣截止点 [工程]: 基于偏差检测经验校准, 非数学推导
    # 强信号时偏差幅度排序稳定 → 可信任排名较后的号码
    # 弱信号时仅前14个有微弱大于零的偏差 → 向后折扣加重
    if signal_strength == "strong":
        cutoff = 22
    elif signal_strength == "moderate":
        cutoff = 18
    else:  # weak
        cutoff = 14
    steepness = 1.0     # 统一衰减速度
    
    # Logistic 衰减: 1 - 1/(1 + exp(-steepness*(rank - cutoff)))
    try:
        return max(0.0, min(1.0, 1.0 - 1.0 / (1.0 + math.exp(-steepness * (rank - cutoff)))))
    except OverflowError:
        return 0.0 if rank > cutoff else 1.0


def determine_optimal_v(data, n_tickets: int = 3) -> BiasVResult:
    """从偏差检测结果推断最优热号池大小 v.

    Args:
        data: 历史开奖数据 [[period, r1..r6, blue], ...]
        n_tickets: 每期注数预算

    Returns:
        BiasVResult with recommended v, top numbers, and reasoning
    """
    n = len(data)
    if n < 100:
        return BiasVResult(
            v=15, signal_level="none",
            fdr_count=0, hpd_count=0, time_stable_count=0,
            top_numbers=list(range(1, 16)),
            deviation_scores={i: 0.0 for i in range(1, 34)},
            reasoning=f"数据不足({n}期 < 100), 回退 v=15 纯覆盖",
        )
    
    signals = _run_bias_detection(data)
    
    fdr = signals["fdr_count"]
    hpd = signals["hpd_count"]
    time_stable = signals["time_stable_count"]
    overdisp = signals["overdispersion"]
    
    # ── 决策树 [工程]: 阈值来自偏差检测的经验校准, 非数学推导
    # fdr>=3 = 至少3个号码通过 BH-FDR q=0.05; time_stable>=1 = 跨时间稳定
    if fdr >= 3 and time_stable >= 1:
        # 强信号: Bonferroni 可靠 + 跨时间稳定
        v = min(12, 8 + fdr)
        signal_level = "strong"
        reasoning = (f"BH-FDR {fdr}个号显著, {time_stable}个跨时间稳定. "
                     f"信号强 → v={v} (窄池高命中)")
    elif fdr >= 1:
        # 中信号: Bonferroni 通过但不够强/不稳定
        v = min(15, 11 + fdr)
        signal_level = "moderate"
        reasoning = (f"BH-FDR {fdr}个号显著, 时间不稳定. "
                     f"信号中等 → v={v}")
    elif hpd >= 5:
        # 弱信号: HPD>=5 [工程]: >=5个号后验95%区间排除均匀值, 虽未达 FDR 标准但超偶然预期
        v = 16
        signal_level = "weak"
        reasoning = (f"BH-FDR 0个, HPD {hpd}个号显著. "
                     f"弱信号 → v={v} (稍放宽池, 利用HPD信息)")
    else:
        # 无信号: 纯覆盖
        v = 15  # [工程] 回退默认值, 与 La Jolla C(15,6,4) 已知表对齐
        signal_level = "none"
        reasoning = (f"BH-FDR {fdr}个, HPD {hpd}个. "
                     f"无可靠偏差 → v={v} 纯覆盖设计")
    
    # ── 选热号 ──
    devs = signals["deviation_ranking"]
    
    if signal_level == "none":
        # 无信号: 取偏差排名前 v 个 (虽然是噪声, 但至少有点方向)
        top_numbers = [num for num, _ in devs[:v]]
    else:
        # 有信号: 按折扣加权取号
        # 每个号码的有效分 = 偏差幅度 × 信号折扣
        effective_scores = []
        for i, (num, dev) in enumerate(devs, start=1):
            discount = _signal_discount(i, v, signal_level)
            effective = dev * discount
            effective_scores.append((num, dev, discount, effective))
        
        # 取有效分最高的 v 个
        effective_scores.sort(key=lambda x: -x[3])
        top_numbers = [num for num, _, _, _ in effective_scores[:v]]
    
    deviation_map = {num: dev for num, dev in devs}
    
    return BiasVResult(
        v=v,
        signal_level=signal_level,
        fdr_count=fdr,
        hpd_count=hpd,
        time_stable_count=time_stable,
        top_numbers=sorted(top_numbers),
        deviation_scores=deviation_map,
        reasoning=reasoning,
    )


# ═══════════════════════════════════════════════════════════
# 便捷函数: 直接从 db 加载数据并给出 v
# ═══════════════════════════════════════════════════════════

def auto_v() -> BiasVResult:
    """自动从数据库加载数据, 返回最优 v.

    这是主入口 — 替代所有 hardcoded k=15 的地方。
    """
    from server.db import load_draws
    data = load_draws()
    return determine_optimal_v(data)


# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    result = auto_v()
    print(f"推荐 v = {result.v}")
    print(f"信号级别: {result.signal_level}")
    print(f"BH-FDR显著: {result.fdr_count}个")
    print(f"HPD显著: {result.hpd_count}个")
    print(f"时间稳定: {result.time_stable_count}个")
    print(f"热号: {result.top_numbers}")
    print(f"理由: {result.reasoning}")
    
    # 展示前30个号的偏差
    print(f"\n偏差排名 (前30):")
    for num in result.top_numbers[:30] if len(result.top_numbers) >= 30 else result.top_numbers:
        dev = result.deviation_scores.get(num, 0)
        marker = "→" if num in result.top_numbers[:result.v] else " "
        print(f"  {marker} #{num:02d}: {dev:+.1f}%")
