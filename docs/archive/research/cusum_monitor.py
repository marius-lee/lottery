"""CUSUM 在线监控 — 检测红球频率的微小持续漂移

CUSUM (Cumulative Sum Control Chart):
  - 对每个红球号码维护上下两条 CUSUM 曲线
  - H0: p_i = 1/33 (目标频率)
  - H1: p_i 在某个时间点发生了漂移
  - 突破控制线 → 告警

参数:
  - k (参考值/松弛): 允许的微小波动幅度 = 0.5σ
  - h (控制限/决策区间): 5σ (ARL0 ≈ 465期, 即平均465期才误报一次)
  - σ_i = sqrt(p(1-p)/n) ≈ sqrt((1/33)(32/33)/2010) ≈ 0.0038

方法 (Page, 1954):
  C_i⁺ = max(0, C_{i-1}⁺ + (x_i - μ) - k)
  C_i⁻ = max(0, C_{i-1}⁻ + (μ - x_i) - k)
  告警: C_i⁺ > h 或 C_i⁻ > h

用法:
  python3 ml/cusum_monitor.py            # 全量分析
  python3 ml/cusum_monitor.py --latest   # 仅最近一期追加
"""
import sys, os, math, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_data():
    from server.db import load_draws
    return load_draws()


def cusum_init(k=0.5, h=5.0):
    """初始化CUSUM参数. 
    
    k: 参考值 (0.5σ = 微小波动容差)
    h: 控制限 (5σ = ARL_0 ≈ 465)
    p0: 目标频率 1/33
    """
    p0 = 1.0 / 33
    sigma = math.sqrt(p0 * (1 - p0))  # 伯努利标准差 ≈ 0.173
    return {
        "p0": p0, "k": k, "h": h,
        "k_sigma": k * sigma,
        "h_sigma": h * sigma,
        "sigma": sigma,
    }


def compute_cusum(data, params):
    """计算所有33个号码的CUSUM序列."""
    p0 = params["p0"]
    k = params["k_sigma"]
    h = params["h_sigma"]
    
    N = len(data)
    
    # 每个号码的CUSUM状态
    cusum = {n: {"C_plus": [], "C_minus": [], "alerts": []} for n in range(1, 34)}
    
    for t, row in enumerate(data):
        reds = set(row[1:7])
        for n in range(1, 34):
            x = 1 if n in reds else 0
            # 上偏CUSUM: 检测频率上升
            prev_plus = cusum[n]["C_plus"][-1] if cusum[n]["C_plus"] else 0
            c_plus = max(0, prev_plus + (x - p0) - k)
            cusum[n]["C_plus"].append(c_plus)
            
            # 下偏CUSUM: 检测频率下降
            prev_minus = cusum[n]["C_minus"][-1] if cusum[n]["C_minus"] else 0
            c_minus = max(0, prev_minus + (p0 - x) - k)
            cusum[n]["C_minus"].append(c_minus)
            
            # 告警
            if c_plus > h:
                cusum[n]["alerts"].append({
                    "period_idx": t,
                    "direction": "UP",
                    "C_plus": round(c_plus, 4),
                    "running_avg": round(sum(cusum[n]["C_plus"][-10:]) / min(10, len(cusum[n]["C_plus"])), 4),
                })
            if c_minus > h:
                cusum[n]["alerts"].append({
                    "period_idx": t,
                    "direction": "DOWN",
                    "C_minus": round(c_minus, 4),
                })
    
    return cusum


def compute_running_freq(data, num, window=50):
    """计算某号码在滚动窗口内的频率."""
    N = len(data)
    freqs = []
    for t in range(window, N + 1):
        count = sum(1 for row in data[t-window:t] if num in row[1:7])
        freqs.append(count / window)
    return freqs


def run():
    data = load_data()
    N = len(data)
    params = cusum_init()
    
    print("=" * 70)
    print("CUSUM 在线监控 — 红球频率漂移检测 (Page 1954)")
    print("=" * 70)
    print(f"数据: {N} 期, p0=1/33≈{params['p0']:.4f}")
    print(f"ARL₀ ≈ 465 (平均误报间隔) | k={params['k']}σ | h={params['h']}σ")
    print()
    
    cusum = compute_cusum(data, params)
    
    # 汇总告警
    all_alerts = []
    for n in range(1, 34):
        for alert in cusum[n]["alerts"]:
            all_alerts.append({
                "number": n,
                **alert,
            })
    
    # 统计
    alert_counts = {}
    for a in all_alerts:
        alert_counts[a["number"]] = alert_counts.get(a["number"], 0) + 1
    
    if all_alerts:
        print(f"告警总数: {len(all_alerts)} (来自 {len(alert_counts)} 个号码)")
        # Top 告警号码
        sorted_alerts = sorted(alert_counts.items(), key=lambda x: -x[1])
        for num, cnt in sorted_alerts[:8]:
            freq = sum(1 for row in data for n in row[1:7] if n == num) / (N * 6 / 33) * params["p0"]
            latest_plus = cusum[num]["C_plus"][-1] if cusum[num]["C_plus"] else 0
            latest_minus = cusum[num]["C_minus"][-1] if cusum[num]["C_minus"] else 0
            print(f"  #{num:02d}: {cnt}次告警 | "
                  f"C⁺={latest_plus:.4f} C⁻={latest_minus:.4f}")
    else:
        print(f"告警: 无")
        print(f"→ 所有号码均未突破 {params['h']}σ 控制限")
        print(f"→ 频率在均匀分布期望波动范围内")
    
    # 最近100期趋势
    print(f"\n── 最近100期频率趋势 (vs p0={params['p0']:.4f}) ──")
    recent_data = data[-100:]
    recent_freq = {}
    for n in range(1, 34):
        cnt = sum(1 for row in recent_data if n in row[1:7])
        recent_freq[n] = cnt / 100
    
    deviations = [(n, recent_freq[n] - params["p0"]) for n in range(1, 34)]
    deviations.sort(key=lambda x: -x[1])
    
    print(f"  偏多Top-5: {[(f'#{n}={f:.4f}', f'{d:+.4f}') for n,d,f in [(n,d,recent_freq[n]) for n,d in deviations[:5]]]}")
    print(f"  偏少Top-5: {[(f'#{n}={f:.4f}', f'{d:+.4f}') for n,d,f in [(n,d,recent_freq[n]) for n,d in deviations[-5:]]]}")
    
    return {
        "N": N,
        "alerts": len(all_alerts),
        "alert_numbers": list(alert_counts.keys()),
    }


if __name__ == "__main__":
    run()
