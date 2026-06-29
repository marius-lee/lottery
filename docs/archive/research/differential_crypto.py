"""实验4: 差分密码分析 — 攻击抽奖机这个"黑盒密码"

核心假设: 如果抽奖有物理惯性，相邻期的位置变化不是均匀的。
某些"差分路径"从未出现或极少出现 → 可排除 → 缩小候选空间。

方法:
  1. 每对相邻期, 计算6个位置的号码变化量
  2. 构建位置级差分直方图
  3. 与实际数据对比 → 找统计显著的空洞
  4. 基于上期开奖, 排除"不可能差分"对应的候选号码

关键区别 vs 反事实检验(实验3):
  - 实验3: 比较的是整个draw的Jaccard相似度 → 不显著
  - 实验4: 比较的是位置级差分 → 可能发现draw级忽略的pattern
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import random
import math
from collections import Counter, defaultdict


def load_data():
    from server.db import load_draws
    return load_draws()


def compute_differentials(data):
    """计算相邻期各位置的差分分布.

    Returns:
      pos_deltas: list[6] of Counter, 每位置的差分频率
      joint_deltas: Counter, 6维联合差分频率
    """
    pos_deltas = [Counter() for _ in range(6)]
    joint_counts = Counter()

    for t in range(1, len(data)):
        prev = sorted(data[t-1][1:7])
        curr = sorted(data[t][1:7])
        deltas = tuple(curr[p] - prev[p] for p in range(6))
        for p in range(6):
            pos_deltas[p][deltas[p]] += 1
        joint_counts[deltas] += 1

    return pos_deltas, joint_counts


def shuffle_test(data, n_permutations=1000):
    """随机打乱基准: 如果序列真随机, 差分分布应接近打乱后的分布.

    对真实序列计算差分, 再对打乱序列计算差分, 比较分布.
    """
    actual_pos, actual_joint = compute_differentials(data)

    # 提取所有红球, 随机打乱顺序, 重建伪序列
    all_reds = [sorted(row[1:7]) for row in data]
    all_blues = [row[7] for row in data]

    # 用真实差分分布 vs 打乱差分分布 的差异
    # 打乱: 随机重排红球序列
    shuffled_joint_sizes = []
    for _ in range(n_permutations):
        shuffled = all_reds[:]
        random.shuffle(shuffled)
        fake_data = []
        for i, reds in enumerate(shuffled):
            fake_data.append([0] + reds + [all_blues[i]])
        _, sj = compute_differentials(fake_data)
        shuffled_joint_sizes.append(len(sj))

    actual_joint_size = len(actual_joint)
    # 打乱后平均联合差分种类数
    avg_shuffled = sum(shuffled_joint_sizes) / len(shuffled_joint_sizes)

    return {
        "actual_unique_joints": actual_joint_size,
        "shuffled_mean_joints": round(avg_shuffled, 1),
        "shuffled_std_joints": round(
            math.sqrt(sum((x - avg_shuffled)**2 for x in shuffled_joint_sizes) / len(shuffled_joint_sizes)), 1),
    }


def find_impossible_differentials(pos_deltas, min_support=5):
    """找出统计上显著偏少的差分.

    对每个位置, 所有历史出现的差分值 → 范围[min_delta, max_delta].
    在这个范围内但从未出现的差分 → "空洞" → impossible differentials.
    min_support: 最少出现次数 [统计: 5次以下可能是噪声]
    """
    results = {}
    for p in range(6):
        deltas = pos_deltas[p]
        total = sum(deltas.values())
        if total == 0:
            continue

        min_d = min(deltas.keys())
        max_d = max(deltas.keys())
        # 在[min_d, max_d]范围内但出现<min_support的值
        holes = []
        for d in range(min_d, max_d + 1):
            count = deltas.get(d, 0)
            if count < min_support:
                expected = total / (max_d - min_d + 1)  # 均匀分布期望
                holes.append({
                    "delta": d,
                    "count": count,
                    "expected_avg": round(expected, 1),
                    "ratio": round(count / expected, 3) if expected > 0 else 0,
                })

        results[p] = {
            "range": (min_d, max_d),
            "n_possible": max_d - min_d + 1,
            "n_observed": len([d for d in range(min_d, max_d + 1) if deltas.get(d, 0) >= min_support]),
            "n_holes": len(holes),
            "holes": holes[:10],
            "coverage_pct": round(
                len([d for d in range(min_d, max_d + 1) if deltas.get(d, 0) >= min_support])
                / (max_d - min_d + 1) * 100, 1),
            "most_common": deltas.most_common(5),
        }
    return results


def estimate_pool_reduction(pos_deltas, last_reds, pool_size=1107475):
    """估算基于上期号码, 排除'不可能差分'后池子缩小多少.

    对每个位置p: 上期号码 n_p, 本期候选范围 = {n_p + d | d in observed_deltas}.
    缩小因子 = ∏(observed_deltas数 / 理论差分范围).
    """
    last_sorted = sorted(last_reds)

    total_deltas_possible = 1.0
    filtered_deltas = 1.0

    for p in range(6):
        deltas = pos_deltas[p]
        if not deltas:
            continue
        n_p = last_sorted[p]
        min_d = min(deltas.keys())
        max_d = max(deltas.keys())
        # 理论可能范围 (受号码边界约束)
        lo_theory = 1 - n_p
        hi_theory = 33 - n_p
        theory_range = hi_theory - lo_theory + 1

        # 实际观察到的差分种类
        observed_range = len(set(d for d in range(min_d, max_d + 1)
                                 if deltas.get(d, 0) > 0))

        if theory_range > 0:
            total_deltas_possible *= theory_range
            filtered_deltas *= observed_range

    if total_deltas_possible == 0:
        return {"reduction_pct": 0}

    reduction_ratio = filtered_deltas / total_deltas_possible
    # 保守估计: 取平方根 (6维联合 ≠ 独立乘积)
    effective_ratio = math.sqrt(reduction_ratio)

    return {
        "reduction_ratio": round(reduction_ratio, 4),
        "effective_ratio": round(effective_ratio, 4),
        "reduction_pct": round((1 - effective_ratio) * 100, 1),
        "note": "保守估计(联合≠独立), 实际效果可能更好或更差",
    }


def run():
    data = load_data()
    n = len(data)

    print(f"=" * 60)
    print(f"实验4: 差分密码分析")
    print(f"=" * 60)
    print(f"数据: {n} 个连续期 → {n-1} 个差分对")
    print()

    # 1. 差分分布
    pos_deltas, joint_deltas = compute_differentials(data)
    print(f"联合差分种类: {len(joint_deltas)} (最大可能 {n-1})")
    print()

    # 2. 打乱检验
    print(f"打乱检验 (1000次):")
    shuffle_result = shuffle_test(data)
    print(f"  实际联合: {shuffle_result['actual_unique_joints']}")
    print(f"  打乱平均: {shuffle_result['shuffled_mean_joints']} ± {shuffle_result['shuffled_std_joints']}")
    joint_diff = (shuffle_result['actual_unique_joints'] - shuffle_result['shuffled_mean_joints'])
    print(f"  差值: {joint_diff:+.0f} (负=实际差分种类比随机少)")
    print()

    # 3. 位置级空洞分析
    print(f"位置级差分空洞 (出现<5次):")
    holes_analysis = find_impossible_differentials(pos_deltas)
    total_holes = 0
    for p in range(6):
        ha = holes_analysis[p]
        total_holes += ha["n_holes"]
        top3 = ha["most_common"][:3]
        print(f"  位置{p+1}: 范围{ha['range']}, "
              f"观察{ha['n_observed']}/{ha['n_possible']}种差分, "
              f"空洞{ha['n_holes']}个 ({ha['coverage_pct']}%覆盖)")
        print(f"    最常见: {[(d, c) for d, c in top3]}")
    print()

    # 4. 池子缩减估算
    if len(data) >= 2:
        reduction = estimate_pool_reduction(pos_deltas, data[-1][1:7])
        print(f"基于最近一期池子缩减估算:")
        print(f"  独立乘积比: {reduction['reduction_ratio']:.4f}")
        print(f"  保守估计: {reduction['effective_ratio']:.4f}")
        print(f"  估计池子缩小: {reduction['reduction_pct']:.1f}%")
        print(f"  ({reduction['note']})")

    # 5. 反向验证: 差分排除法回溯测试
    print(f"\n{'─' * 60}")
    print(f"反向验证: 在历史数据上测试差分排除效果")
    backtest = backtest_differential_filter(data, pos_deltas)
    print(f"  测试期数: {backtest['n_tested']}")
    print(f"  误杀数: {backtest['false_kill_count']} (共{backtest['n_tested']*6}个位置检查)")
    print(f"  误杀率: {backtest['false_kill_rate']:.2%}")
    killed = backtest.get('killed_positions', {})
    if killed:
        print(f"  被误杀位置: {dict(killed)}")

    print(f"\n{'═' * 60}")
    print(f"综合: 差分排除{'有效' if backtest['false_kill_rate'] < 0.05 else '风险较高'}")
    print(f"{'═' * 60}")

    return {
        "pos_deltas": pos_deltas,
        "joint_deltas": len(joint_deltas),
        "shuffle": shuffle_result,
        "holes": holes_analysis,
        "backtest": backtest,
    }


def backtest_differential_filter(data, pos_deltas, lookback=100):
    """回溯测试: 用差分约束排除候选, 检查是否误杀真实开奖.

    对每期t: 基于t-1期号码+差分约束 → 每个位置的合法候选集.
    如果真实开奖的某个位置号码不在候选集中 → 误杀.
    """
    n = len(data)
    if n < 20:
        return {"n_tested": 0, "false_kill_count": 0, "false_kill_rate": 0}
    start = max(10, n - lookback)
    false_kills = 0
    killed_positions = Counter()

    for t in range(start, n):
        prev_sorted = sorted(data[t-1][1:7])
        actual_reds = sorted(data[t][1:7])

        for p in range(6):
            n_p = prev_sorted[p]
            deltas = pos_deltas[p]
            observed_deltas = {d for d, c in deltas.items() if c > 0}
            candidates = {n_p + d for d in observed_deltas
                         if 1 <= n_p + d <= 33}
            if not candidates:
                continue
            if actual_reds[p] not in candidates:
                false_kills += 1
                killed_positions[p] += 1

    n_tested = n - start
    return {
        "n_tested": n_tested,
        "false_kill_count": false_kills,
        "false_kill_rate": false_kills / n_tested if n_tested > 0 else 0,
        "killed_positions": dict(killed_positions),
    }


if __name__ == "__main__":
    run()
