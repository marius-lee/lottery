"""曾献忠《双色球解密方法与技巧》(2014, 194页) — 曾氏模块理论完整实现

全书结构:
  p1-17: 概论+建模+模块建立 — 理论框架
  p18-43: 内部运动 — 衡值轮盘+行列组合+江恩螺旋+集合
  p44-116: 各维度详细分析+四大定律应用
  p117-186: 外部运动 — 01号追踪, V/O系统, 外部遗传定律

核心体系:
  1. 衡值轮盘 — 33为圆心, 互补对排成4圈×4线
  2. 内部运动四大定律 — 标准值/正常值/边缘值/极端边缘值
  3. 外部运动三大定律 — 外部遗传值大数/边缘遗传值间歇/极端不复出
  4. V/O追踪系统 — 逐项检查上期是否匹配模块预期
  5. 邻距+质号连续 — 补充分析维度
"""

import math
from typing import List, Dict, Set, Tuple, Optional
from collections import Counter


# ═══════════════════════════════════════════════════════════════════════════════
# 1. 衡值轮盘 — p19-20
# ═══════════════════════════════════════════════════════════════════════════════

WHEEL_LINES = {
    'a': {1, 2, 15, 16, 17, 18, 31, 32},
    'b': {3, 4, 13, 14, 19, 20, 29, 30},
    'c': {5, 6, 11, 12, 21, 22, 27, 28},
    'd': {7, 8, 9, 10, 23, 24, 25, 26},
}

WHEEL_CIRCLES = {
    'A': {1, 2, 3, 4, 5, 6, 7, 8},
    'B': {9, 10, 11, 12, 13, 14, 15, 16},
    'C': {17, 18, 19, 20, 21, 22, 23, 24},
    'D': {25, 26, 27, 28, 29, 30, 31, 32},
}

# 互补对 [p19]: 01+32=33, 02+31=33...
WHEEL_PAIRS = {n: 33 - n for n in range(1, 33)}
WHEEL_PAIRS[33] = 33


def wheel_analysis(reds: List[int]) -> Dict:
    """衡值轮盘分布分析 [p19-20]."""
    rs = set(reds)
    lines_hit = {name: len(rs & nums) for name, nums in WHEEL_LINES.items()}
    circles_hit = {name: len(rs & nums) for name, nums in WHEEL_CIRCLES.items()}

    pairs_found = []
    for n in reds:
        c = WHEEL_PAIRS[n]
        if c in rs and n < c:
            pairs_found.append((n, c))

    # [p29-32]: 遗传值规则
    # 圈遗传值: 0,1,2,3; 其他不遗传
    # 线遗传值: 0,1,2; 边缘遗传值: 3
    circle_anomalies = [name for name, cnt in circles_hit.items() if cnt > 3]
    line_anomalies = [name for name, cnt in lines_hit.items() if cnt > 3]

    return {
        "lines": lines_hit, "circles": circles_hit,
        "pairs": pairs_found,
        "circle_anomalies": circle_anomalies,
        "line_anomalies": line_anomalies,
        # [p31]: 7/8项目为0=极端边缘, 3/8项目为0=边缘
        "zero_count": sum(1 for v in list(lines_hit.values()) + list(circles_hit.values()) if v == 0),
        "balanced": len(circle_anomalies) == 0 and len(line_anomalies) == 0,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 2. 邻距 + 质号连续 + 号码散度 — p122
# ═══════════════════════════════════════════════════════════════════════════════

def compute_linju(reds: List[int]) -> List[int]:
    """邻距: 相邻两个红球号码之差, 有5个 [p122].

    与间距的区别: 邻距=相邻差, 间距=相邻差-1
    """
    s = sorted(reds)
    return [s[i+1] - s[i] for i in range(5)]


def compute_prime_consecutive(reds: List[int]) -> int:
    """质号连续: 最大连续质号个数 [p122].

    质数: 2,3,5,7,11,13,17,19,23,29,31
    """
    PRIMES = {2,3,5,7,11,13,17,19,23,29,31}
    s = sorted(reds)
    max_run = 0
    run = 0
    for n in s:
        if n in PRIMES:
            run += 1
            max_run = max(max_run, run)
        else:
            run = 0
    return max_run


# ═══════════════════════════════════════════════════════════════════════════════
# 3. 四大定律 — p24-25 (内部运动)
# ═══════════════════════════════════════════════════════════════════════════════

def compute_value_zones(stats: List[int]) -> Dict:
    """计算标准值/正常值/边缘值/极端边缘值范围 [p16, p24-25].

    标准值 = 按数学比例确定(均值整数)
    正常值 = 标准值±1
    边缘值 = 正常值±1
    极端边缘值 = 边缘值±1
    """
    if not stats:
        return {}
    n = len(stats)
    mean = sum(stats) / n
    std_val = int(round(mean))
    return {
        "standard": std_val,
        "normal": [max(0, std_val - 1), std_val + 1],
        "edge": [max(0, std_val - 2), std_val + 2],
        "extreme": [max(0, std_val - 3), std_val + 3],
        "mean": round(mean, 1), "samples": n,
    }


def apply_four_laws(current_val: int, zones: Dict) -> Dict:
    """应用四大定律 [p24-25].

    定律1 (标准值大数定律): 标准值几乎不间断重复 → 追
    定律2 (正常值间歇性定律): 正常值有双周期(S1,S2) → 查周期后可能回补
    定律3 (边缘值不连续定律): 边缘值不重复 → 排除
    定律4 (极端边缘值不复出定律): 十年一遇 → 全面回避
    """
    if not zones:
        return {"zone": "unknown", "action": "无数据"}
    std = zones["standard"]
    n_lo, n_hi = zones["normal"]
    e_lo, e_hi = zones["edge"]
    if current_val == std:
        return {"zone": "standard", "law": "定律1:标准值大数定律", "action": "追"}
    elif n_lo <= current_val <= n_hi:
        return {"zone": "normal", "law": "定律2:正常值间歇性定律", "action": "关注"}
    elif e_lo <= current_val <= e_hi:
        return {"zone": "edge", "law": "定律3:边缘值不连续定律", "action": "排除"}
    else:
        return {"zone": "extreme", "law": "定律4:极端边缘值不复出", "action": "全面回避"}


# ═══════════════════════════════════════════════════════════════════════════════
# 4. 外部运动三大定律 — p125 (外部遗传)
# ═══════════════════════════════════════════════════════════════════════════════

def external_genetic_laws(module_items: Dict, prev_draw_values: Dict) -> Dict:
    """外部遗传分析 — 检查上期各项值是否匹配模块预期 [p125].

    外部遗传值大数定律: 多数项值与上期相同 → 追(V)
    外部边缘遗传值间歇性定律: 少数项值间歇性相同 → 关注(周期N1,N2)
    外部极端边缘遗传值不重复定律: 极少数相同 → 排除(O)

    V/O系统: V=符合外部遗传要求(保留), O=不符合(过滤掉)
    """
    results = {}
    for key, expected in module_items.items():
        actual = prev_draw_values.get(key)
        if actual is None:
            results[key] = {"status": "?", "signal": "无数据"}
            continue
        if actual == expected:
            results[key] = {"status": "V", "signal": "保留 — 外部遗传值大数定律",
                           "expected": expected, "actual": actual}
        elif abs(actual - expected) <= 1:
            results[key] = {"status": "~", "signal": "关注 — 外部边缘遗传值间歇性定律",
                           "expected": expected, "actual": actual}
        else:
            results[key] = {"status": "O", "signal": "排除 — 外部极端不重复",
                           "expected": expected, "actual": actual}
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# 5. 曾氏模块建立 — p16-17
# ═══════════════════════════════════════════════════════════════════════════════

def build_module(data: List, odd_count: int = 3, big_count: int = 3,
                 zone_ratio: Optional[Tuple[int, int, int]] = None) -> Dict:
    """曾氏模块建立: 选稳定条件过滤历史, 得到分析样本 [p16-17].

    流程:
      1. 选稳定条件 → 过滤历史 → 得到样本(年均3-5次)
      2. 对样本从7个维度分析
      3. 应用内部四大定律 + 外部三大定律
      4. 排除法缩小候选范围
    """
    sample = []
    for row in data:
        reds = row[1:7]
        if sum(1 for n in reds if n % 2 == 1) != odd_count: continue
        if sum(1 for n in reds if n >= 17) != big_count: continue
        if zone_ratio:
            z1 = sum(1 for n in reds if n <= 11)
            z2 = sum(1 for n in reds if 12 <= n <= 22)
            z3 = sum(1 for n in reds if 23 <= n <= 33)
            if (z1, z2, z3) != zone_ratio: continue
        sample.append(row)

    if len(sample) < 5:
        return {"ok": False, "msg": f"样本不足: {len(sample)}期 (需≥5)"}

    # 7维分析 [p16]
    # ① 号码分布——区间与集合
    zones = {1: Counter(), 2: Counter(), 3: Counter()}
    for row in sample:
        for n in row[1:7]:
            if n <= 11: zones[1][n] += 1
            elif n <= 22: zones[2][n] += 1
            else: zones[3][n] += 1

    # ② 邻距 + 位势
    linju_stats = []
    for row in sample:
        lj = compute_linju(row[1:7])
        linju_stats.append({"max": max(lj), "min": min(lj), "avg": round(sum(lj)/5, 1)})
    linju_maxes = [x["max"] for x in linju_stats]
    linju_zones = compute_value_zones(linju_maxes)

    # ③ 和值
    sums = [sum(row[1:7]) for row in sample]
    sum_zones = compute_value_zones(sums)

    # ④ 衡值轮盘
    wheel_line_stats = {line: [] for line in WHEEL_LINES}
    for row in sample:
        wa = wheel_analysis(row[1:7])
        for line, cnt in wa["lines"].items():
            wheel_line_stats[line].append(cnt)
    wheel_line_zones = {line: compute_value_zones(counts) for line, counts in wheel_line_stats.items()}

    # ⑤ 冷热号集合 [p16定义]
    # A=上期号码, B=6-10期未出(温), C=10期+未出(冷), D=B+C, E=热号
    hot = set(); warm = set(); cold = set()
    for n in range(1, 34):
        count = sum(1 for row in sample if n in row[1:7])
        rate = count / len(sample)
        if rate > 0.22: hot.add(n)
        elif rate > 0.08: warm.add(n)
        else: cold.add(n)

    # ⑥ 重号统计
    repeats = []
    for i in range(1, len(sample)):
        repeats.append(len(set(sample[i-1][1:7]) & set(sample[i][1:7])))
    repeat_zones = compute_value_zones(repeats)

    # ⑦ 质号连续统计
    prime_runs = [compute_prime_consecutive(row[1:7]) for row in sample]
    prime_zones = compute_value_zones(prime_runs)

    # 当前期分析
    latest = data[-1] if data else None
    current_sum = sum(latest[1:7]) if latest else 0
    current_wheel = wheel_analysis(latest[1:7]) if latest else None
    current_linju = compute_linju(latest[1:7]) if latest else []
    current_prime = compute_prime_consecutive(latest[1:7]) if latest else 0
    current_repeats = len(set(latest[1:7]) & set(data[-2][1:7])) if latest and len(data) >= 2 else 0

    predictions = {
        "sum": apply_four_laws(current_sum, sum_zones) if sum_zones else None,
        "linju_max": apply_four_laws(current_linju[-1] if current_linju else 0, linju_zones) if linju_zones else None,
        "repeat": apply_four_laws(current_repeats, repeat_zones) if repeat_zones else None,
        "prime_consecutive": apply_four_laws(current_prime, prime_zones) if prime_zones else None,
    }

    # 外部遗传分析 [p125]
    external = None
    if latest and len(sample) >= 2:
        prev = data[-2] if len(data) >= 2 else latest
        ext_module = {
            "sum": sum_zones.get("standard"),
            "linju_max": linju_zones.get("standard"),
            "repeat": repeat_zones.get("standard"),
            "prime": prime_zones.get("standard"),
        }
        ext_prev = {
            "sum": sum(prev[1:7]),
            "linju_max": max(compute_linju(prev[1:7])) if prev else 0,
            "repeat": len(set(prev[1:7]) & set(latest[1:7])) if prev and latest else 0,
            "prime": compute_prime_consecutive(prev[1:7]) if prev else 0,
        }
        external = external_genetic_laws(ext_module, ext_prev)

    return {
        "ok": True,
        "conditions": {"odd": odd_count, "big": big_count, "zone_ratio": zone_ratio},
        "sample_size": len(sample), "total_periods": len(data),
        "avg_per_year": round(len(sample) / (len(data) / 154), 1),
        "zones": {
            "sum": sum_zones, "linju": linju_zones,
            "repeat": repeat_zones, "prime": prime_zones,
            "wheel_lines": wheel_line_zones,
        },
        "collections": {"hot": sorted(hot), "warm": sorted(warm), "cold": sorted(cold)},
        "predictions": predictions,
        "external_genetic": external,
        "current_wheel": current_wheel,
        "current_linju": current_linju,
        "current_prime": current_prime,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 6. 模块出号 — 曾氏模块选号法
# ═══════════════════════════════════════════════════════════════════════════════

def generate_from_module(data: List, odd_count: int = 3, big_count: int = 3,
                         n_tickets: int = 3) -> Dict:
    """基于曾氏模块的热号优先出号 [p16-17, p125].

    流程:
      1. 建立模块(选稳定条件过滤历史)
      2. 取模块内的热号+温号作为候选池
      3. 从候选池随机组合, 用衡值轮盘检查分布均衡性
      4. 排除含极端冷号的组合
    """
    mod = build_module(data, odd_count=odd_count, big_count=big_count)
    if not mod.get("ok"):
        return {"ok": False, "msg": mod.get("msg", "模块建立失败")}

    hot = set(mod["collections"]["hot"])
    warm = set(mod["collections"]["warm"])
    cold_set = set(mod["collections"]["cold"])

    # 候选池: 热号+温号, 排除极端冷号
    candidate_pool = sorted(hot | warm)
    if len(candidate_pool) < 7:
        candidate_pool = sorted(hot | warm | cold_set)  # 不够时全用

    import random
    rng = random.Random()
    try:
        rng.seed(int(str(data[-1][0]) + str(odd_count) + str(big_count)))
    except (ValueError, IndexError):
        pass

    tickets = []
    max_attempts = n_tickets * 500
    attempts = 0

    # 获取和值/邻距的预期范围用于过滤
    sum_zones = mod["zones"].get("sum", {})
    linju_zones = mod["zones"].get("linju", {})

    while len(tickets) < n_tickets and attempts < max_attempts:
        attempts += 1

        if len(candidate_pool) >= 6:
            reds = sorted(rng.sample(candidate_pool, 6))
        else:
            reds = sorted(rng.sample(range(1, 34), 6))

        # 检查是否含极端冷号 (全面回避原则)
        if set(reds) & set(mod["collections"]["cold"][:5]):
            continue

        # 衡值轮盘均衡性检查
        wa = wheel_analysis(reds)
        if wa["circle_anomalies"] or wa["line_anomalies"]:
            continue

        # 和值/邻距在正常范围内
        if sum_zones:
            s = sum(reds)
            n_lo, n_hi = sum_zones.get("normal", [0, 200])
            if s < n_lo or s > n_hi:
                continue

        # 蓝球: 频率加权
        blue_weights = [1.0/16] * 16
        for row in mod.get("_sample", data[-252:]):
            b = row[7]
            if 1 <= b <= 16:
                blue_weights[b-1] += 0.5
        total = sum(blue_weights)
        blue_weights = [w/total for w in blue_weights]

        blue = rng.choices(range(1, 17), weights=blue_weights, k=1)[0]
        tickets.append({"reds": reds, "blue": blue})

    return {
        "ok": True,
        "algorithm": f"曾氏模块(奇{odd_count}大{big_count})",
        "tickets": tickets,
        "module_info": {
            "sample_size": mod["sample_size"],
            "avg_per_year": mod["avg_per_year"],
            "hot_count": len(hot),
            "warm_count": len(warm),
            "cold_count": len(cold_set),
        },
        "laws_applied": {
            "avoid_extreme_cold": sorted(set(mod["collections"]["cold"][:5])),
            "wheel_balanced": True,
            "sum_range": sum_zones.get("normal") if sum_zones else None,
        },
    }


def dashboard(data: List) -> Dict:
    """曾献忠完整仪表盘."""
    latest = data[-1] if data else None
    wheel = wheel_analysis(latest[1:7]) if latest else None
    linju = compute_linju(latest[1:7]) if latest else []
    prime_run = compute_prime_consecutive(latest[1:7]) if latest else 0

    # 模块A: 奇3大3 (最常见)
    mod_a = build_module(data, odd_count=3, big_count=3)
    # 模块B: 奇3大3区间2:2:2 (更精细)
    mod_b = build_module(data, odd_count=3, big_count=3, zone_ratio=(2, 2, 2))

    laws_summary = {}
    if mod_a.get("ok"):
        for key, p in mod_a.get("predictions", {}).items():
            if p: laws_summary[key] = {"zone": p["zone"], "law": p["law"], "action": p["action"]}

    ext_summary = mod_a.get("external_genetic", {})
    v_count = sum(1 for v in ext_summary.values() if v.get("status") == "V")
    o_count = sum(1 for v in ext_summary.values() if v.get("status") == "O")

    return {
        "wheel": wheel,
        "linju": linju,
        "prime_run": prime_run,
        "module_a": {"sample_size": mod_a.get("sample_size", 0),
                     "avg_per_year": mod_a.get("avg_per_year", 0),
                     "collections": mod_a.get("collections", {})},
        "module_b": {"sample_size": mod_b.get("sample_size", 0),
                     "avg_per_year": mod_b.get("avg_per_year", 0)},
        "laws_summary": laws_summary,
        "external_genetic": {"items": ext_summary, "v_count": v_count, "o_count": o_count},
        "total_periods": len(data),
    }
