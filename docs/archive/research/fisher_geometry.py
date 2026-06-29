"""实验5: Fisher信息几何 — 追踪概率分布的缓慢漂移

核心问题: 红球分布是否在缓慢变化?
  - 如果分布是静态的 → 全历史频率就是最优估计
  - 如果分布在漂移 → 近期频率比全历史频率更有预测力

测试方法:
  1. 将2000期分为前半/后半, 比较频率分布
  2. 如果前半频率 ≠ 后半频率 (统计显著), 分布正在漂移
  3. 确定最佳回溯窗口 (short-term vs long-term tradeoff)
  4. 外推: 近期趋势 → 预测近期频率

Fisher度量视角:
  在32-单纯形上, Fisher信息度量 = 概率分布间的"正确"距离.
  对Multinomial: 微分同胚于球面上的欧氏距离 (通过 sqrt 变换).
  关键: 如果分布点在做布朗运动, 距离~sqrt(t). 如果是漂移, 距离~t.

实际方法 (Fisher几何简化):
  对Multinomial(33): 自然参数 = log(θ_i/θ_33)
  Fisher距离 d(θ, θ') = 2 arccos(sum(sqrt(θ_i θ'_i)))
  这等价于 Hellinger距离.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import math
from collections import Counter


def load_data():
    from server.db import load_draws
    return load_draws()


def compute_frequencies(data, window=None, offset=0):
    """计算给定窗口的红球频率."""
    if window is None:
        window = len(data)
    subset = data[offset:offset + window]
    counts = Counter()
    for row in subset:
        for n in row[1:7]:
            counts[n] += 1
    n_obs = len(subset) * 6
    return {n: counts.get(n, 0) / n_obs for n in range(1, 34)}


def hellinger_distance(freq_a, freq_b):
    """Hellinger距离: d² = 1/2 Σ(√p_i - √q_i)² = 1 - Σ√(p_i q_i).

    等价于Fisher球面距离: d_F = 2 arccos(1 - d_H²).
    """
    dot = sum(math.sqrt(freq_a.get(n, 0) * freq_b.get(n, 0)) for n in range(1, 34))
    return math.sqrt(max(0, 1 - dot))


def drift_analysis(data):
    """分析频率分布随时间的变化.

    将数据分成N个窗口, 计算相邻窗口间的Hellinger距离.
    如果距离随窗口增大而增大 → 漂移. 如果稳定 → 静态.
    """
    n = len(data)
    results = {}

    # 1. 前半 vs 后半
    mid = n // 2
    first_half = compute_frequencies(data[:mid])
    second_half = compute_frequencies(data[mid:])
    d_split = hellinger_distance(first_half, second_half)

    # 2. 滑动窗口: 每200期一个窗口, 计算相邻距离
    window = 200
    n_windows = n // window
    window_freqs = []
    for i in range(n_windows):
        wf = compute_frequencies(data[i * window: (i + 1) * window])
        window_freqs.append(wf)

    adj_dists = []
    for i in range(len(window_freqs) - 1):
        d = hellinger_distance(window_freqs[i], window_freqs[i + 1])
        adj_dists.append(d)

    # 3. 置换检验: 打乱窗口顺序, 重算距离
    import random
    shuffled_dists = []
    for _ in range(1000):
        indices = list(range(len(window_freqs)))
        random.shuffle(indices)
        s_dists = []
        for i in range(len(indices) - 1):
            d = hellinger_distance(window_freqs[indices[i]],
                                   window_freqs[indices[i + 1]])
            s_dists.append(d)
        shuffled_dists.append(sum(s_dists) / len(s_dists))

    avg_adj = sum(adj_dists) / len(adj_dists) if adj_dists else 0
    avg_shuffled = sum(shuffled_dists) / len(shuffled_dists)

    # 漂移信号: 相邻窗口距离 > 打乱后距离?
    drift_signal = avg_adj > avg_shuffled

    results["split"] = {
        "first_vs_second_half_distance": round(d_split, 5),
        "n_first": mid,
        "n_second": n - mid,
    }
    results["windows"] = {
        "window_size": window,
        "n_windows": n_windows,
        "adjacent_distances": [round(d, 5) for d in adj_dists],
        "mean_adjacent": round(avg_adj, 5),
        "mean_shuffled": round(avg_shuffled, 5),
        "drift_signal": drift_signal,
    }

    return results


def optimal_lookback(data, windows_to_test=None):
    """找最优回溯窗口: 哪个窗口的近期频率最能预测未来频率.

    对每个窗口大小 w:
      用最近w期的频率 → 与下50期的频率比较
      最短Hellinger距离 = 最佳预测窗口
    """
    n = len(data)
    if windows_to_test is None:
        windows_to_test = [10, 20, 30, 50, 100, 200, 500, 1000]

    results = {}
    future_window = 50
    for w in windows_to_test:
        if w + future_window > n:
            continue
        # 最近w期
        recent = compute_frequencies(data, window=w, offset=n - w - future_window)
        # 接下来50期 (held-out)
        future = compute_frequencies(data, window=future_window, offset=n - future_window)
        d = hellinger_distance(recent, future)
        # 基线: 全历史频率
        all_freq = compute_frequencies(data, window=n - future_window, offset=0)
        d_all = hellinger_distance(all_freq, future)
        results[w] = {
            "distance": round(d, 5),
            "vs_all_history": round(d - d_all, 5),
            "better_than_all": d < d_all,
        }

    best = min(results.items(), key=lambda x: x[1]["distance"])
    return {
        "by_window": results,
        "best_window": best[0],
        "best_distance": best[1]["distance"],
        "all_history_distance": results[1000]["distance"] if 1000 in results else None,
    }


def extrapolate_drift(data, lookback=50):
    """外推法: 用近期偏差预测近期分布.

    方法: 最近N期频率 vs 除最近N期外的频率 → 偏差方向.
    预测: 全历史频率 + 偏差 × 外推因子.
    """
    n = len(data)
    recent = compute_frequencies(data, window=lookback, offset=n - lookback)
    past = compute_frequencies(data, window=n - lookback, offset=0)
    all_freq = compute_frequencies(data)

    # 偏差: recent偏离all_freq的方向
    deviations = {}
    for num in range(1, 34):
        r = recent.get(num, 0)
        p = past.get(num, 0)
        a = all_freq.get(num, 0)
        # 近期相对全历史的偏差
        dev = r - a
        deviations[num] = {
            "recent": round(r, 5),
            "past": round(p, 5),
            "all": round(a, 5),
            "deviation": round(dev, 5),
            "deviation_pct": round(dev / a * 100, 1) if a > 0 else 0,
        }

    top_deviations = sorted(deviations.items(), key=lambda x: -x[1]["deviation"])[:8]
    bottom_deviations = sorted(deviations.items(), key=lambda x: x[1]["deviation"])[:8]

    return {
        "lookback": lookback,
        "top_increasing": [(n, d["deviation_pct"]) for n, d in top_deviations],
        "top_decreasing": [(n, d["deviation_pct"]) for n, d in bottom_deviations],
    }


def run():
    data = load_data()
    n = len(data)

    print(f"=" * 60)
    print(f"实验5: Fisher信息几何 — 分布漂移追踪")
    print(f"=" * 60)
    print(f"数据: {n} 期")
    print()

    # 1. 漂移检测
    print(f"漂移分析:")
    drift = drift_analysis(data)
    s = drift["split"]
    print(f"  前半 vs 后半 Hellinger距离: {s['first_vs_second_half_distance']:.5f}")
    print(f"  (0=完全相同, 1=完全正交. 典型随机波动 0.005-0.02)")

    w = drift["windows"]
    print(f"\n  滑动窗口 ({w['window_size']}期/窗口, {w['n_windows']}个窗口):")
    print(f"  相邻距离: {w['adjacent_distances']}")
    print(f"  平均相邻: {w['mean_adjacent']:.5f}")
    print(f"  打乱平均: {w['mean_shuffled']:.5f}")
    print(f"  漂移信号: {'⚠️  有漂移' if w['drift_signal'] else '无显著漂移'}")

    # 2. 最优回溯窗口
    print(f"\n{'─' * 60}")
    print(f"最优回溯窗口:")
    opt = optimal_lookback(data)
    for w_size, winfo in opt["by_window"].items():
        tag = " ← 最优" if w_size == opt["best_window"] else ""
        vs = f" (vs全历史 {winfo['vs_all_history']:+.5f})" if winfo['vs_all_history'] != 0 else ""
        print(f"  {w_size:>5}期: d={winfo['distance']:.5f}{vs}{tag}")

    # 3. 外推
    print(f"\n{'─' * 60}")
    print(f"近期偏差外推 (最近{opt['best_window']}期):")
    extrap = extrapolate_drift(data, lookback=opt['best_window'])
    print(f"  上升趋势号码 ({opt['best_window']}期频率 > 全历史):")
    for num, pct in extrap["top_increasing"][:5]:
        print(f"    #{num:02d}: {pct:+.1f}%")
    print(f"  下降趋势号码:")
    for num, pct in extrap["top_decreasing"][:5]:
        print(f"    #{num:02d}: {pct:+.1f}%")

    # 4. 综合判定
    print(f"\n{'═' * 60}")
    if w["drift_signal"]:
        print(f"⚠️  检测到分布漂移")
        print(f"  最优回溯窗口: {opt['best_window']}期")
        print(f"  近期频率比全历史频率更好地预测未来")
        print(f"  → 使用近期加权, 而非等权全历史")
    else:
        print(f"无显著漂移 — 分布接近静态")
        print(f"  全历史频率就是最优估计")
    print(f"{'═' * 60}")

    return {"drift": drift, "optimal_lookback": opt, "extrapolation": extrap}


if __name__ == "__main__":
    run()
