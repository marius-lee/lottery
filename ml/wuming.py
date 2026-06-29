"""吴明 算法实现 — 蓝球排除 + 红球战法 (2006, 2006.9, 2010)

  2006 《双色球核心秘密与排除大法》: 5期重号/9期冷号/6区间排除
  2006.9 《双色球细节战法与蓝球攻略》: 位置战法/重号战法/极值优先/胆码
  2010 《和值大法》: 八分法+除8余数复合战法
  2010 《双色球擒号绝技》续: 蓝球循环振荡/遗漏警报/顺时针/大小单双尾
"""

from server.db import load_draws

# ═══════════════════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════════════════

# [原书] 吴明2010 Ch15 §4: 顺时针法 — 蓝球4区新排法
BLUE_CLOCKWISE = {
    "zone1": {1, 12, 11, 10},
    "zone2": {2, 13, 16, 9},
    "zone3": {3, 14, 15, 8},
    "zone4": {4, 5, 6, 7},
}

# [原书] 吴明2010 Ch15 §5: 大小单双尾法 — 蓝球4维交叉分类
BLUE_BSD_TAIL = {
    "小单尾": {1, 3, 11, 13},
    "小双尾": {2, 4, 12, 14},
    "大单尾": {5, 7, 9, 15},
    "大双尾": {6, 8, 10, 16},
}

# [原书] Ch4 p104-123: 6位置"有价值区域"
POSITION_VALUABLE = {
    1: (1, 19),
    2: (2, 22),
    3: (3, 28),
    4: (5, 31),
    5: (8, 32),
    6: (11, 33),
}

# ═══════════════════════════════════════════════════════════════════════════
# 蓝球排除 (2010)
# ═══════════════════════════════════════════════════════════════════════════

def wuming_cyclic_oscillation():
    """蓝球循环振荡预测 [吴明2010 Ch13 §2: 0-8半幅环距]."""
    data = load_draws()
    if len(data) < 20:
        return {"ok": False, "msg": "数据不足"}
    blues = [row[7] for row in data]
    last_blue = blues[-1]
    osc = [min(abs(blues[i] - blues[i-1]), 16 - abs(blues[i] - blues[i-1])) for i in range(1, len(blues))]
    avg = sum(osc[-20:]) / 20
    candidates = set()
    for v in range(max(1, int(avg)), min(8, int(avg + 2))):
        candidates.add((last_blue + v - 1) % 16 + 1)
        candidates.add((last_blue - v + 15) % 16 + 1)
    return {"ok": True, "last_blue": last_blue, "avg_oscillation": round(avg, 1),
            "osc_history_5": osc[-5:], "candidates": sorted(candidates),
            "candidate_count": len(candidates), "source": "吴明2010 Ch13: 循环振荡法"}


def wuming_blue_extreme_alert():
    """蓝球遗漏警报 [吴明2010 Ch17: 博彩基本公式].

    N = ln(1-D) / ln(1-P). D=99.9%, P=1/16 → N=107期(理论极值).
    """
    data = load_draws()
    if len(data) < 60:
        return {"ok": False, "msg": "数据不足"}
    blues = [row[7] for row in data]
    ci = len(blues) - 1
    alerts = []
    for b in range(1, 17):
        om = ci
        for i in range(ci - 1, -1, -1):
            if blues[i] == b:
                om = ci - i
                break
        alerts.append({"blue": b, "omission": om,
                       "pct_to_extreme": round(om / 107 * 100, 1),
                       "alert": om > 59})
    alerts.sort(key=lambda x: -x["omission"])
    return {"ok": True, "theoretical_extreme": 107,
            "formula": "N = ln(1-D) / ln(1-P)",
            "alerts": alerts, "source": "吴明2010 Ch17: 博彩基本公式"}


def wuming_clockwise_weights():
    """顺时针法蓝球加权 [吴明2010 Ch15 §4]."""
    data = load_draws()
    if len(data) < 2:
        return [1.0] * 16
    last = data[-1][7]
    weights = [1.0] * 16
    for zone_name, nums in BLUE_CLOCKWISE.items():
        if last in nums:
            for n in nums:
                weights[n - 1] = 0.3
            break
    return weights


def wuming_bsd_tail_weights():
    """大小单双尾法蓝球加权 [吴明2010 Ch15 §5]."""
    data = load_draws()
    if len(data) < 2:
        return [1.0] * 16
    last = data[-1][7]
    weights = [1.0] * 16
    for cat, nums in BLUE_BSD_TAIL.items():
        if last in nums:
            for n in nums:
                weights[n - 1] = 0.3
            break
    return weights


# ═══════════════════════════════════════════════════════════════════════════
# 红球排除 (2006)
# ═══════════════════════════════════════════════════════════════════════════

def period5_hotness():
    """5期重号摆动预测 [吴明2006 Ch1: 5大定理]."""
    data = load_draws()
    if len(data) < 6:
        return {"ok": False}
    recent5 = set()
    for row in data[-5:]:
        recent5.update(row[1:7])
    pool_size = len(recent5)
    prev5 = set()
    for row in data[-6:-1]:
        prev5.update(row[1:7])
    prev_size = len(prev5)
    direction = "up" if pool_size > prev_size else ("down" if pool_size < prev_size else "flat")
    return {"ok": True, "hot_numbers": sorted(recent5), "pool_size": pool_size,
            "prev_size": prev_size, "direction": direction,
            "recommend": "偏多→跟热" if pool_size >= 20 else "偏少→博冷",
            "source": "吴明2006 Ch1: 5期重号理论"}


def period9_cold():
    """9期冷号策略 [吴明2006 Ch3: 63.15%转化率]."""
    data = load_draws()
    if len(data) < 10:
        return {"ok": False}
    last_seen = {}
    for i, row in enumerate(data):
        for n in row[1:7]:
            last_seen[n] = i
    ci = len(data) - 1
    cold = [{"number": n, "omission": ci - last_seen.get(n, 0)} for n in range(1, 34) if ci - last_seen.get(n, 0) >= 9]
    cold.sort(key=lambda x: -x["omission"])
    return {"ok": True, "cold_numbers": cold, "count": len(cold),
            "note": "63%冷号5期内转热 [吴明2006 p71-82]", "source": "吴明2006 Ch3: 9期冷号理论"}


def zone6_exclusion():
    """6区间排除法 [吴明2006 Ch4: 100%安全排1区]."""
    data = load_draws()
    if len(data) < 2:
        return {"ok": False}
    ZONES = [(1, set(range(1, 6))), (2, set(range(6, 12))), (3, set(range(12, 17))),
             (4, set(range(17, 23))), (5, set(range(23, 28))), (6, set(range(28, 34)))]
    last_reds = set(data[-1][1:7])
    empty_zones = [zid for zid, nums in ZONES if not (last_reds & nums)]
    killed = set()
    for zid in empty_zones:
        killed.update(next(nums for z, nums in ZONES if z == zid))
    return {"ok": True, "empty_zones": empty_zones, "killed": sorted(killed),
            "killed_count": len(killed), "note": "100%安全排空区 [吴明2006 p90-130]",
            "source": "吴明2006 Ch4: 6区间排除法"}


def position_filter(candidates):
    """位置战法: 每位置号码必须在有价值区域内 [吴明2006.9 Ch4]."""
    filtered = []
    for c in candidates:
        valid = True
        for p in range(6):
            lo, hi = POSITION_VALUABLE[p + 1]
            if not (lo <= c[p] <= hi):
                valid = False
                break
        if valid:
            filtered.append(c)
    return filtered if filtered else candidates


def wu_sum_compound():
    """复合战法: 八区间+除8余数交集定位和值 [吴明和值大法 Ch4]."""
    data = load_draws()
    if len(data) < 50:
        return {"ok": False}
    sums = [sum(row[1:7]) for row in data]
    step = 21
    zone8 = {i: (21 + i * step, min(183, 21 + (i + 1) * step - 1)) for i in range(8)}
    zone_om = {}
    for zid, (lo, hi) in zone8.items():
        om = 0
        for s in reversed(sums):
            if lo <= s <= hi: break
            om += 1
        zone_om[zid] = om
    mod_om = {}
    for r in range(8):
        om = 0
        for s in reversed(sums):
            if s % 8 == r: break
            om += 1
        mod_om[r] = om
    best_z = max(zone_om, key=zone_om.get)
    best_m = max(mod_om, key=mod_om.get)
    lo, hi = zone8[best_z]
    candidates = [s for s in range(lo, hi + 1) if s % 8 == best_m]
    return {"ok": True, "candidates": candidates, "zone_id": best_z,
            "zone_range": [lo, hi], "mod_remainder": best_m,
            "zone_omission": zone_om[best_z], "mod_omission": mod_om[best_m],
            "source": "吴明《和值大法》: 八分法+除8余数复合战法"}


def extreme_value_dan(data):
    """极值优先原理 [吴明胆码篇 p15-16]."""
    if len(data) < 60:
        return {"ok": False, "msg": "数据不足"}
    window = min(200, len(data))
    recent = data[-window:]
    pos_stats = {}
    for p in range(6):
        current_omissions = {}
        for n in range(1, 34):
            om = 0
            for i in range(len(recent) - 1, -1, -1):
                r = sorted(recent[i][1:7])
                if r[p] == n:
                    break
                om += 1
            current_omissions[n] = om
        lo, hi = POSITION_VALUABLE[p + 1]
        candidates = [(n, om) for n, om in current_omissions.items() if lo <= n <= hi and om > 15]
        candidates.sort(key=lambda x: -x[1])
        pos_stats[p] = [{"number": n, "omission": om, "alert": om > 30} for n, om in candidates[:5]]
    return {"ok": True, "positions": pos_stats, "source": "吴明《胆码篇》: 极值优先原理"}


def repeat_method(data):
    """重号战法 [吴明2006.9 Ch4 p124-134]."""
    if len(data) < 2:
        return {"ok": False}
    last = set(data[-1][1:7])
    prev = set(data[-2][1:7])
    repeats = len(last & prev)
    if repeats <= 2:
        return {"ok": True, "repeat_count": repeats, "level": 1,
                "recommend": "0-2重复", "extreme": 26, "source": "吴明2006.9 Ch4: 重号战法"}
    else:
        return {"ok": True, "repeat_count": repeats, "level": 2,
                "recommend": "≥3重复(罕见)", "extreme": 35, "source": "吴明2006.9 Ch4: 重号战法"}
