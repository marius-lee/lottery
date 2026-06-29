#!/usr/bin/env python3
"""策略回溯验证 — 每期开奖后自动评估所有策略 vs 随机基线

运行: python3 tools/validate_strategies.py
用途: cron job, 每期开奖后自动运行, 检测策略偏差是否统计显著

门禁规则:
  - 滑动窗口 (默认100期): 统计每个策略的红球命中数和蓝球命中率
  - 随机基线: μ_red = 6×6/33 = 1.09, μ_blue = 1/16 = 0.0625
  - 单样本t检验 vs 基线, p < 0.05/Bonferroni 才算显著
  - 未通过 → 自动降权至 0.0 (停用该策略)
  - 通过 → 权重按 effect size 缩放 (max 2.0)
"""
import sys, os, json, math
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# 理论基线
RED_BASELINE = 6 * 6 / 33  # 1.0909 红球期望命中数
BLUE_BASELINE = 1 / 16     # 0.0625 蓝球命中率


def load_performance_log():
    from server.db import get_db
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT period, strategy, red_hits, blue_hits, tries FROM strategy_performance_log ORDER BY period"
        ).fetchall()
    except Exception:
        # Table might not exist
        conn.close()
        return []
    conn.close()
    return rows


def validate(window=100):
    """滑动窗口验证所有策略，返回调整后的权重。"""
    rows = load_performance_log()
    if len(rows) < 30:
        print("数据不足 (需要 ≥30 条记录)")
        return {"ok": False, "msg": "数据不足"}

    # 按策略分组
    strategies = defaultdict(list)
    for r in rows:
        strategies[r["strategy"]].append({
            "period": r["period"],
            "red_hits": r["red_hits"],
            "blue_hits": r["blue_hits"],
            "tries": r["tries"],
        })

    results = {}
    for strat_name, history in strategies.items():
        # 取最近 window 期
        recent = history[-window:]
        n = len(recent)

        # 汇总
        total_red = sum(h["red_hits"] for h in recent)
        total_blue = sum(h["blue_hits"] for h in recent)
        total_tries = sum(h["tries"] for h in recent)

        if total_tries < 5:
            results[strat_name] = {"weight": 0.0, "reason": "样本不足 (<5注)", "n": total_tries}
            continue

        avg_red = total_red / total_tries if total_tries else 0
        avg_blue = total_blue / total_tries if total_tries else 0

        # 单样本 t 检验 (简化: 用 z 检验, 大样本近似)
        # H0: μ = baseline
        se_red = math.sqrt(RED_BASELINE * (1 - RED_BASELINE / 6) / total_tries) if total_tries else 1
        z_red = (avg_red - RED_BASELINE) / se_red if se_red > 0 else 0
        p_red = 2 * (1 - _norm_cdf(abs(z_red)))  # 双尾

        se_blue = math.sqrt(BLUE_BASELINE * (1 - BLUE_BASELINE) / total_tries) if total_tries else 1
        z_blue = (avg_blue - BLUE_BASELINE) / se_blue if se_blue > 0 else 0
        p_blue = 2 * (1 - _norm_cdf(abs(z_blue)))

        # Bonferroni 校正 (按策略数)
        n_strategies = len(strategies)
        bonf_threshold = 0.05 / n_strategies if n_strategies > 0 else 0.05

        red_sig = p_red < bonf_threshold
        blue_sig = p_blue < bonf_threshold

        # Effect size (Cohen's d)
        d_red = (avg_red - RED_BASELINE) / max(0.01, se_red * math.sqrt(total_tries))
        d_blue = (avg_blue - BLUE_BASELINE) / max(0.01, se_blue * math.sqrt(total_tries))

        # 权重: 显著 → 按 effect size; 不显著 → 0.0 (停用)
        if red_sig and avg_red > RED_BASELINE:
            weight = min(2.0, max(0.5, 1.0 + d_red))
        elif blue_sig and avg_blue > BLUE_BASELINE:
            weight = min(2.0, max(0.5, 1.0 + d_blue))
        else:
            weight = 0.0

        results[strat_name] = {
            "n": total_tries,
            "avg_red": round(avg_red, 4),
            "avg_blue": round(avg_blue, 4),
            "z_red": round(z_red, 3),
            "z_blue": round(z_blue, 3),
            "p_red": round(p_red, 4),
            "p_blue": round(p_blue, 4),
            "red_sig": red_sig,
            "blue_sig": blue_sig,
            "bonf_threshold": round(bonf_threshold, 6),
            "weight": round(weight, 2),
            "active": weight > 0,
        }

    # 排序输出
    active = {k: v for k, v in results.items() if v["active"]}
    inactive = {k: v for k, v in results.items() if not v["active"]}

    print(f"策略回溯验证 (窗口={window}期)")
    print(f"{'='*70}")
    print(f"Bonferroni 阈值: p < {1/len(strategies):.6f} (n_strategies={len(strategies)})")
    print()

    if active:
        print(f"✅ 活跃策略 ({len(active)}):")
        for name, r in sorted(active.items(), key=lambda x: -x[1]["weight"]):
            print(f"  {name}: w={r['weight']:.2f} | "
                  f"红={r['avg_red']:.3f} (z={r['z_red']:.2f}, p={r['p_red']:.4f}) | "
                  f"蓝={r['avg_blue']:.3f} | n={r['n']}")
    else:
        print(f"✅ 活跃策略: 无")
        print(f"  → 所有策略未通过统计显著性检验 (p > Bonferroni 阈值)")
        print(f"  → 回归随机基线 (均匀概率)")
        print(f"  → 建议: 仅使用覆盖设计, 不依赖策略加权")

    if inactive:
        print(f"\n❌ 停用策略 ({len(inactive)}):")
        for name, r in sorted(inactive.items(), key=lambda x: x[1]["p_red"]):
            print(f"  {name}: w=0.00 | "
                  f"红={r['avg_red']:.3f} (p={r['p_red']:.4f}) | n={r['n']}")

    return {
        "ok": True,
        "window": window,
        "bonferroni_threshold": round(bonf_threshold, 6),
        "active": active,
        "inactive": inactive,
        "summary": f"{len(active)}/{len(results)} 活跃, {len(inactive)} 停用",
    }


def _norm_cdf(x):
    """标准正态 CDF 近似 (Abramowitz & Stegun 26.2.17)."""
    if x < 0:
        return 1 - _norm_cdf(-x)
    # Constants
    b0, b1, b2, b3, b4, b5 = 0.2316419, 0.319381530, -0.356563782, 1.781477937, -1.821255978, 1.330274429
    t = 1 / (1 + b0 * x)
    pdf = math.exp(-x * x / 2) / math.sqrt(2 * math.pi)
    return 1 - pdf * (b1 * t + b2 * t**2 + b3 * t**3 + b4 * t**4 + b5 * t**5)


if __name__ == "__main__":
    result = validate()
    if result["ok"]:
        # 可选: 写入权重文件供 ml_bridge 或 ensemble 使用
        weights = {}
        for name, r in {**result["active"], **result["inactive"]}.items():
            weights[name] = r["weight"]
        print(f"\n{'='*70}")
        print(f"权重输出: {json.dumps(weights, indent=2, ensure_ascii=False)}")
    else:
        print(result["msg"])
