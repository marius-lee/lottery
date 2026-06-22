"""李志林《彩票赢家·双色球选号技巧》(2012) 算法实现.

严格按原书公式, 不自行发挥。无成功率数据 — 原书仅举例论证。

实现内容:
  1. 八招定胆 (Part 3 §10, p139-144): 8个精确算术定胆公式
  2. 上期→下期带出表 (Part 2 §8, p111-113): 方向性转移查表
  3. 27个杀号公式 (Part 1 §13, p59-62): 可用的杀号公式
  4. 首位号码判断法 (Part 3 §15, p157-159)
  5. 蓝球: 排五法 + 五期动态 + 十招杀蓝

"""
from ml.ssq_constants import TICKET_PRICE


# ═══════════════════════════════════════════════════════════════════════════
# 6. 定胆3招 (Part 3 §13, p152-154) — 手动定位后实现
# ═══════════════════════════════════════════════════════════════════════════

def generate_dan3_methods(data):
    """定胆3招: 第三位尾数定胆 + 两数中间定胆 + 黄金分割定胆.

    原书 Part 3 §13, p152-154.
    """
    if len(data) < 1:
        return {"ok": False, "msg": "数据不足"}

    last = data[-1]
    reds = sorted(last[1:7])

    # ── 第一招: 第三位尾数定胆 (原书 p153) ──
    # 第3位尾数 → 加4得A, A加3得B, >10取尾 → 两个尾数的号码为候选
    tail = reds[2] % 10
    a = (tail + 4) % 10
    b = (tail + 4 + 3) % 10
    dan1_tails = sorted({a, b})
    dan1_numbers = sorted({n for n in range(1, 34) if n % 10 in dan1_tails})

    # ── 第二招: 两数中间定胆 (原书 p154) ──
    # 相邻两数取中间值 → 候选胆码
    dan2_numbers = set()
    for i in range(5):
        mid = (reds[i] + reds[i+1]) / 2
        dan2_numbers.add(int(mid))  # 向下取整
        if mid != int(mid):
            dan2_numbers.add(int(mid) + 1)  # 向上取整 (书中: 07-08)
    dan2_numbers = sorted(dan2_numbers)

    # ── 第三招: 黄金分割定胆 (原书 p154) ──
    # 每个红球 × 0.618 → 取整数 → 候选
    dan3_numbers = set()
    for n in reds:
        g = n * 0.618
        dan3_numbers.add(int(g))
        if int(g) != g and int(g) + 1 <= 33:
            dan3_numbers.add(int(g) + 1)
    dan3_numbers = sorted(dan3_numbers)

    # 合并去重
    all_dans = sorted(set(dan1_numbers) | set(dan2_numbers) | set(dan3_numbers))

    return {
        "ok": True,
        "algorithm": "LiZhilin-Dan3Methods",
        "candidates": all_dans,
        "candidate_count": len(all_dans),
        "method1_tails": {"third_tail": tail, "dan_tails": dan1_tails, "numbers": dan1_numbers},
        "method2_middle": dan2_numbers,
        "method3_golden": dan3_numbers,
        "source": "原书 Part 3 §13, p152-154",
    }


# ═══════════════════════════════════════════════════════════════════════════
# 辅助: 值映射到有效号码范围
# ═══════════════════════════════════════════════════════════════════════════
# 原书未指定>33或<1时的处理规则, 此处使用标准模运算(工程兜底)

def _to_red(v):
    """映射到1-33."""
    if 1 <= v <= 33:
        return v
    r = abs(v) % 33
    return 33 if r == 0 else r


def _to_blue(v):
    """映射到1-16."""
    if 1 <= v <= 16:
        return v
    r = abs(v) % 16
    return 16 if r == 0 else r


# ═══════════════════════════════════════════════════════════════════════════
# 1. 八招定胆 (Part 3 §10, p139-144)
# ═══════════════════════════════════════════════════════════════════════════

_EIGHT_DAN_FORMULAS = [
    ("第5位-第1位", lambda r: _to_red(r[4] - r[0])),
    ("第1位+第3位", lambda r: _to_red(r[0] + r[2])),
    ("上两期第1位相加", None),  # 需要上期数据, 单独处理
    ("第4位-第1位", lambda r: _to_red(r[3] - r[0])),
    ("18-第1位",     lambda r: _to_red(18 - r[0])),
    ("第2位-第1位", lambda r: _to_red(r[1] - r[0])),
    ("第5位-3",      lambda r: _to_red(r[4] - 3)),
    ("第6位-2",      lambda r: _to_red(r[5] - 2)),
]


def generate_eight_dan(data):
    """八招定胆: 用8个固定算术公式计算候选胆码.

    原书 Part 3 §10, p139-144.
    第3招(上两期第1位相加)需要至少2期数据.
    """
    if len(data) < 2:
        return {"ok": False, "msg": "数据不足"}

    last = data[-1]
    reds = sorted(last[1:7])

    dans = []
    details = {}
    for name, fn in _EIGHT_DAN_FORMULAS:
        if fn is None:
            # 第3招: 上两期第1位相加
            prev = data[-2]
            prev_reds = sorted(prev[1:7])
            v = _to_red(prev_reds[0] + reds[0])
        else:
            v = fn(reds)
        if 1 <= v <= 33:
            dans.append(v)
            details[name] = v

    unique = sorted(set(dans))
    return {
        "ok": True,
        "algorithm": "LiZhilin-EightDan",
        "candidates": unique,
        "candidate_count": len(unique),
        "details": details,
        "source": "原书 Part 3 §10, p139-144",
    }


# ═══════════════════════════════════════════════════════════════════════════
# 2. 上期→下期带出表 (Part 2 §8, p111-113)
# ═══════════════════════════════════════════════════════════════════════════

_TRANSITION_TABLE = {
    1:  [3, 6, 9, 33],
    2:  [2, 4, 6, 7, 10],
    3:  [12, 15, 18, 21],
    4:  [2, 5, 8, 12, 15, 18, 21, 23, 26, 29, 32],  # [修正] 移除11
    5:  [11, 12, 14, 16, 20],
    6:  [6, 7, 14, 27],
    7:  [8, 18, 28, 9, 19, 29],
    8:  [3, 13, 23, 33, 16, 26],     # [修正] 6→26
    9:  [11, 1, 21, 13, 23, 33],
    10: [10, 20, 30, 16],
    11: [1, 11, 21, 31, 13, 23, 33],  # [修正] 移除3
    12: [13, 14, 15, 16, 18, 19, 21], # [修正] 移除17
    13: [16, 19, 25, 31],
    14: [12, 15, 18, 21],
    15: [13, 25, 28, 31],
    16: [2, 12, 22, 4, 14, 18],
    17: [9, 6, 8, 10, 11, 14],       # [修正] 3→9
    18: [9, 13, 23, 33, 6, 16, 26],  # [修正] 3→9
}
# 注: 原书仅列到18, 19-33未列出


def generate_transition(data):
    """上期→下期带出表: 根据上期红球, 查表得出下期可能带出的号码.

    原书 Part 2 §8, p111-113.
    """
    if len(data) < 1:
        return {"ok": False, "msg": "数据不足"}

    last = data[-1]
    reds = sorted(last[1:7])

    all_brought = set()
    by_number = {}
    for n in reds:
        brought = _TRANSITION_TABLE.get(n, [])
        all_brought.update(brought)
        by_number[str(n)] = brought

    candidates = sorted(all_brought)
    return {
        "ok": True,
        "algorithm": "LiZhilin-Transition",
        "candidates": candidates,
        "candidate_count": len(candidates),
        "by_number": by_number,
        "source": "原书 Part 2 §8, p111-113",
        "note": "19-33的带出数据OCR未完整提取, 当前仅1-18",
    }


# ═══════════════════════════════════════════════════════════════════════════
# 3. 27个杀号公式 (Part 1 §13, p59-62)
# ═══════════════════════════════════════════════════════════════════════════
# 注: 公式(13)-(17),(25)使用"出号顺序"(非排序), 无法实现, 已略去.
#     公式(18)-(24)是蓝球杀号, 在蓝球部分单独处理.

_KILL_FORMULAS_RED = [
    # (1) 当期中奖蓝码杀下期红码
    ("蓝码杀红码", lambda r, b: b),
    # (2) 第1位与第6位的差
    ("第1位第6位差", lambda r, b: abs(r[5] - r[0])),
    # (3) 第2位与第3位的差
    ("第2位第3位差", lambda r, b: abs(r[2] - r[1])),
    # (4) 第2位与第5位的差
    ("第2位第5位差", lambda r, b: abs(r[4] - r[1])),
    # (5) 第1位×4 - 2
    ("第1位×4-2", lambda r, b: _to_red(r[0] * 4 - 2)),
    # (6) (第1位+蓝号) × 3
    ("(第1位+蓝)×3", lambda r, b: _to_red((r[0] + b) * 3)),
    # (7) 第1位 + 09
    ("第1位+09", lambda r, b: _to_red(r[0] + 9)),
    # (8) 第2位 + 05
    ("第2位+05", lambda r, b: _to_red(r[1] + 5)),
    # (9) 第3位 + 04
    ("第3位+04", lambda r, b: _to_red(r[2] + 4)),
    # (10) 第3位 + 07
    ("第3位+07", lambda r, b: _to_red(r[2] + 7)),
    # (11) 第6位 + 04
    ("第6位+04", lambda r, b: _to_red(r[5] + 4)),
    # (12) (第4位-第5位) + 蓝号 + 01
    ("(第4-第5)+蓝+01", lambda r, b: _to_red((r[3] - r[4]) + b + 1)),
    # (26) 蓝号 + 第2位 - 01
    ("蓝+第2位-01", lambda r, b: _to_red(b + r[1] - 1)),
]

# 使用出号顺序的公式 (无法实现, 保留记录)
_KILL_FORMULAS_DRAW_ORDER = [
    "(13) 出号顺序第1位+第2位",
    "(14) 出号顺序第3位+第5位",
    "(15) (出号顺序首尾差)+蓝号-03",
    "(16) (出号顺序第1第3差)+蓝号+02",
    "(17) (出号顺序1+2+3位)+蓝号-01",
    "(25) 出号顺序第2位-第3位",
]


def generate_kill_formulas(data):
    """27个杀号公式中可用的部分.

    原书 Part 1 §13, p59-62.
    """
    if len(data) < 1:
        return {"ok": False, "msg": "数据不足"}

    last = data[-1]
    reds = sorted(last[1:7])
    blue = last[7]

    kills = []
    details = {}
    for name, fn in _KILL_FORMULAS_RED:
        v = fn(reds, blue)
        v = _to_red(v)
        kills.append(v)
        details[name] = v

    unique = sorted(set(k for k in kills if 1 <= k <= 33))
    return {
        "ok": True,
        "algorithm": "LiZhilin-KillFormulas",
        "excluded": unique,
        "excluded_count": len(unique),
        "details": details,
        "unimplemented": _KILL_FORMULAS_DRAW_ORDER,
        "source": "原书 Part 1 §13, p59-62",
    }


# ═══════════════════════════════════════════════════════════════════════════
# 4. 首位号码判断法 (Part 3 §15, p157-159)
# ═══════════════════════════════════════════════════════════════════════════

def generate_first_position(data):
    """首位号码判断法: 用上期6红依次相减→相加→减5→直到单数.

    原书 Part 3 §15, p157-159.
    作者自述准确率仅30%.
    """
    if len(data) < 1:
        return {"ok": False, "msg": "数据不足"}

    last = data[-1]
    reds = sorted(last[1:7])

    # 依次相减得5个数字
    diffs = [reds[i+1] - reds[i] for i in range(5)]
    # 5个数字相加
    total = sum(diffs)
    # 减5
    result = total - 5
    # >10则个位+十位相加, 直到单数
    while result >= 10:
        result = sum(int(d) for d in str(result))

    return {
        "ok": True,
        "algorithm": "LiZhilin-FirstPosition",
        "first_position": result,
        "calculation": f"diffs={diffs}, sum={total}, -5={total-5}, →{result}",
        "accuracy": "30% (作者自述)",
        "source": "原书 Part 3 §15, p157-159",
    }


# ═══════════════════════════════════════════════════════════════════════════
# 5. 蓝球方法 (Part 5)
# ═══════════════════════════════════════════════════════════════════════════

def generate_paiwu_blue(data):
    """排五法: 排除前五期出现过的蓝球.

    原书 Part 5 §3, p229.
    方法: 查看前五期蓝球 → 全部排除.
    """
    if len(data) < 5:
        return {"ok": False, "msg": "数据不足(需≥5期)"}

    recent5 = [row[7] for row in data[-5:]]
    excluded = sorted(set(recent5))
    candidates = sorted(set(range(1, 17)) - set(excluded))

    return {
        "ok": True,
        "algorithm": "LiZhilin-PaiwuBlue",
        "excluded": excluded,
        "candidates": candidates,
        "candidate_count": len(candidates),
        "source": "原书 Part 5 §3, p229",
    }


def generate_five_period_dynamic_blue(data):
    """五期动态分析法: 上五期蓝号和→用和值分析下期蓝球.

    原书 Part 5 §4, p232-236.
    计算方法: 将上五期蓝号相加, 看和值.
    """
    if len(data) < 5:
        return {"ok": False, "msg": "数据不足(需≥5期)"}

    recent5 = [row[7] for row in data[-5:]]
    total = sum(recent5)
    # [修正] 原书: 和值→均值→中心→±2范围=5个预选号
    avg = total / 5
    center = round(avg)
    candidates = sorted({b for b in range(max(1, center-2), min(16, center+2)+1)})

    return {
        "ok": True,
        "algorithm": "LiZhilin-FivePeriodBlue",
        "five_period_sum": total,
        "center": center,
        "candidates": candidates,
        "recent_blues": recent5,
        "source": "原书 Part 5 §4, p232-236",
    }


# 十招杀蓝球 (Part 5 §5, p237-241)
def _accumulate_reds(reds):
    """红球累加到不超过16的和值 [原书 p237]."""
    s = 0
    for r in reds:
        if s + r > 16:
            return s
        s += r
    return s

_TEN_BLUE_KILLS = [
    ("连续两期蓝号相减", lambda blues: abs(blues[-1] - blues[-2])),
    ("隔两期蓝号相减", lambda blues: abs(blues[-1] - blues[-3]) if len(blues) >= 3 else 0),
    ("隔三期蓝号相减", lambda blues: abs(blues[-1] - blues[-4]) if len(blues) >= 4 else 0),
    ("最大红球减当期蓝号", lambda blues, reds: abs(max(reds) - blues[-1])),
    ("两期蓝号相加减最大蓝号", lambda blues: (blues[-1] + blues[-2]) - max(blues[-1], blues[-2])),
    ("红球依次相加最接近最大蓝号", lambda blues, reds: _accumulate_reds(reds)),  # [修正]
    ("当期最大红减最小红(>16减16)", lambda blues, reds: _to_blue(max(reds) - min(reds))),
    ("两期蓝号相加取个位", lambda blues: (blues[-1] + blues[-2]) % 10),
    # [修正] 9/10需全量数据, 在函数体内单独处理
]


def generate_ten_blue_kills(data):
    """十招杀蓝球: 10个蓝球排除方法.

    原书 Part 5 §5, p237-241.
    """
    if len(data) < 5:
        return {"ok": False, "msg": "数据不足"}

    blues = [row[7] for row in data]
    last = data[-1]
    reds = sorted(last[1:7])

    excluded = set()
    details = {}
    for name, fn in _TEN_BLUE_KILLS:
        if fn is None:
            continue
        try:
            if '红球' in name or '红' in name:
                v = _to_blue(fn(blues, reds))
            else:
                v = _to_blue(fn(blues))
            excluded.add(v)
            details[name] = v
        except Exception:
            pass

    # [修正] 方法9: 当期期数尾排除同尾蓝号
    try:
        period_tail = int(str(data[-1][0])[-1])
        for b in range(1, 17):
            if b % 10 == period_tail:
                excluded.add(b)
        details["(9)期数尾排除"] = period_tail
    except: pass

    # [修正] 方法10: 排除同期尾出现过的蓝号
    try:
        pt = str(data[-1][0])[-1]
        for row in data:
            if str(row[0]).endswith(pt):
                excluded.add(row[7])
        details["(10)同期尾蓝号"] = len(excluded)
    except: pass

    candidates = sorted(set(range(1, 17)) - excluded)
    return {
        "ok": True,
        "algorithm": "LiZhilin-TenBlueKills",
        "excluded": sorted(excluded),
        "candidates": candidates,
        "candidate_count": len(candidates),
        "details": details,
        "source": "原书 Part 5 §5, p237-241",
    }


# ═══════════════════════════════════════════════════════════════════════════
# 6. 12种杀号锁定蓝球 (Part 5 §9, p252-258)
# ═══════════════════════════════════════════════════════════════════════════

def _blue_tails_to_kill(data):
    """12种方法各自产出要杀的蓝球尾数.

    每个方法返回一个尾数(0-9, 0=10), 杀掉所有该尾数的蓝球.
    原书 Part 5 §9, p252-258.
    """
    if len(data) < 3:
        return {}, {}

    blues = [row[7] for row in data]
    last = blues[-1]
    prev = blues[-2]
    prev2 = blues[-3] if len(blues) >= 3 else last

    details = {}
    killed_tails = set()

    def add_tail(method_name, tail_val):
        tail = tail_val % 10
        details[method_name] = tail
        killed_tails.add(tail)

    # (1) 15 - 上期蓝球 = 杀其尾数
    add_tail("(1)15-上期蓝球", abs(15 - last) % 10)

    # (2) 19 - 上期蓝球 = 杀其尾数
    add_tail("(2)19-上期蓝球", abs(19 - last) % 10)

    # (3) 21 - 上期蓝球 = 杀其尾数
    add_tail("(3)21-上期蓝球", abs(21 - last) % 10)

    # (4) 上两期蓝球头+尾 = 杀其尾数 (如15→头1, 04→尾4, 1+4=5)
    add_tail("(4)两期头+尾", (prev // 10) + (last % 10))

    # (5) 上两期尾+头 = 杀其尾数
    add_tail("(5)两期尾+头", (prev % 10) + (last // 10))

    # (6) 上两期尾+尾 = 杀其尾数
    add_tail("(6)两期尾+尾", (prev % 10) + (last % 10))

    # (7) 上期尾 + 隔一期尾 = 杀其尾数
    add_tail("(7)上期尾+隔期尾", (last % 10) + (prev2 % 10))

    # (8) 上期蓝球 × 2 = 杀其尾数
    add_tail("(8)上期蓝球×2", (last * 2) % 10)

    # (9) 上期蓝球尾 × 4 = 杀其尾数
    add_tail("(9)上期尾×4", ((last % 10) * 4) % 10)

    # (10) 上期蓝球 ±7 (>14减, <14加) = 杀其尾数
    v10 = last - 7 if last > 14 else last + 7
    add_tail("(10)上期蓝球±7", abs(v10) % 10)

    # (11) 上期蓝球 + 2 = 杀其尾数
    add_tail("(11)上期蓝球+2", (last + 2) % 10)

    # (12) 上期蓝球 + 6 = 杀其尾数
    add_tail("(12)上期蓝球+6", (last + 6) % 10)

    # 被杀尾数对应的蓝球
    killed_numbers = {n for n in range(1, 17) if (n % 10) in killed_tails}
    survived = sorted(set(range(1, 17)) - killed_numbers)

    return {
        "details": details,
        "killed_tails": sorted(killed_tails),
        "killed_numbers": sorted(killed_numbers),
        "survived": survived,
        "survived_count": len(survived),
    }


# ═══════════════════════════════════════════════════════════════════════════
# 7. 运用期号排除蓝球 (Part 5 §10, p259-261)
# ═══════════════════════════════════════════════════════════════════════════

def _period_based_blue_kill(data):
    """6种运用期号排除蓝球的方法.

    原书 Part 5 §10, p259-261.
    """
    if len(data) < 3:
        return {}

    last = data[-1]
    period = last[0]
    reds = sorted(last[1:7])
    blues = [row[7] for row in data]
    last_blue = blues[-1]
    prev_blue = blues[-2]
    prev2_blue = blues[-3] if len(blues) >= 3 else last_blue

    excluded = set()
    details = {}

    # 1. 上期期号个位 + 1 → 排除该尾数蓝球
    unit = period % 10
    tail1 = (unit + 1) % 10
    details["(1)期号个位+1→排除尾"] = tail1
    for n in range(1, 17):
        if n % 10 == tail1:
            excluded.add(n)

    # 2. 上两期蓝球相加 (>16减10) → 排除 [修正] 原书减10非减16
    v2 = prev_blue + last_blue
    while v2 > 16:
        v2 -= 10
    details["(2)两期蓝球相加"] = v2
    if 1 <= v2 <= 16:
        excluded.add(v2)

    # 3. 上期第1位红球 + 3 → 排除
    v3 = reds[0] + 3
    if v3 > 16:
        v3 = v3 % 16 or 16
    details["(3)第1位红球+3"] = v3
    if 1 <= v3 <= 16:
        excluded.add(v3)

    # 4. 上期蓝球个十位互换 (>16减16) → 排除
    tens = last_blue // 10
    ones = last_blue % 10
    v4 = ones * 10 + tens
    while v4 > 16:
        v4 -= 16
    details["(4)蓝球个十位互换"] = v4
    if 1 <= v4 <= 16:
        excluded.add(v4)

    # 5. 上上期蓝球除3余数 + 上期蓝球 → 排除
    rem = prev2_blue % 3
    v5 = rem + last_blue
    if v5 > 16:
        v5 = v5 % 16 or 16
    details["(5)隔期余数+上期蓝球"] = v5
    if 1 <= v5 <= 16:
        excluded.add(v5)

    # 6. 上两期蓝球尾数相加/相减, 取左右各3位, 不在范围内的同尾号排除
    tail_a = prev_blue % 10
    tail_b = last_blue % 10
    sum_tail = (tail_a + tail_b) % 10
    diff_tail = abs(tail_a - tail_b) % 10

    range_sum = {(sum_tail + i) % 10 for i in range(-3, 4)}
    range_diff = {(diff_tail + i) % 10 for i in range(-3, 4)}
    # [修正] 原书用对称差(XOR): 同尾号排除, 非补集
    excluded_tails = range_sum ^ range_diff

    details["(6)尾数和差排除"] = {
        "sum_tail": sum_tail, "diff_tail": diff_tail,
        "excluded_tails": sorted(excluded_tails),
    }
    for n in range(1, 17):
        if n % 10 in excluded_tails:
            excluded.add(n)

    survived = sorted(set(range(1, 17)) - excluded)

    return {
        "details": details,
        "excluded": sorted(excluded),
        "survived": survived,
        "survived_count": len(survived),
    }


# ═══════════════════════════════════════════════════════════════════════════
# [修正] 27杀号公式(18)-(24): 蓝球杀号 (Part 1 §13, p84-85, 原遗漏)
# ═══════════════════════════════════════════════════════════════════════════

def _kill_blue_18_to_24(data):
    """27杀号公式中的蓝球杀号(18)-(24). 原代码标注"蓝球部分单独处理"但未实现."""
    if len(data) < 2:
        return {"ok": False}
    last = data[-1]
    reds = sorted(last[1:7])
    blue = last[7]
    prev = data[-2]
    prev_blue = prev[7]

    killed = set()
    # (18) 蓝号+第1位红球 (若与上期蓝相同则-1)
    v = blue + reds[0]
    if v == prev_blue:
        v -= 1
    killed.add(_to_red(v))

    # (19) 蓝号-第4位红球+1
    killed.add(_to_red(blue - reds[3] + 1))

    # (20) 蓝号-第5位红球
    killed.add(_to_red(blue - reds[4]))

    # (21) 蓝号×第1位红球
    killed.add(_to_red(blue * reds[0]))

    # (22) 蓝号+7
    killed.add(_to_red(blue + 7))

    # (23) 蓝号+9
    killed.add(_to_red(blue + 9))

    # (24) 蓝偶×2+2, 蓝奇×5+2 → 蓝球杀
    if blue % 2 == 0:
        killed_blue = _to_blue(blue * 2 + 2)
    else:
        killed_blue = _to_blue(blue * 5 + 2)
    return {"ok": True, "killed_red": sorted(k for k in killed if 1 <= k <= 33),
            "killed_blue": killed_blue if 1 <= killed_blue <= 16 else None,
            "source": "原书 Part 1 §13, 公式(18)-(24)"}


# ═══════════════════════════════════════════════════════════════════════════
# [修正] 趣味杀蓝球 8公式 (Part 5 §6, p264-265, 原遗漏)
# ═══════════════════════════════════════════════════════════════════════════

def _funny_blue_kills(data):
    """趣味杀蓝球: 8个用期号×N+红球位置÷16余数公式."""
    if len(data) < 1:
        return {"ok": False}
    last = data[-1]
    reds = sorted(last[1:7])
    try:
        period = int(str(last[0]))
    except:
        return {"ok": False}

    killed = set()
    for red_pos in range(1, 7):
        r = reds[red_pos - 1]
        for N in [1, 2, 3, 4, 5, 6, 7, 8]:
            v = (period * N + r) % 16
            killed.add(v if v != 0 else 16)
            if len(killed) >= 16:
                break
        if len(killed) >= 16:
            break

    survived = [b for b in range(1, 17) if b not in killed]
    return {"ok": True, "killed": sorted(killed), "survived": survived,
            "source": "原书 Part 5 §6, p264-265"}


# ═══════════════════════════════════════════════════════════════════════════
# 组合出号
# ═══════════════════════════════════════════════════════════════════════════

def generate_tickets(data, n_tickets=3,
                     use_dan8=True, use_dan3=True,
                     use_transition=True, use_kill=True,
                     use_blue_tail12=True, use_blue_ten=False,
                     use_blue_period=False):
    """综合出号: 用户按原书各方法独立勾选组合.

    Args:
        use_dan8: 八招定胆
        use_dan3: 定胆3招 (尾数/中间/黄金分割)
        use_transition: 上期→下期带出表
        use_kill: 27杀号公式排除
        use_blue_tail12: 12种尾数杀号锁定蓝球
        use_blue_ten: 十招杀蓝
        use_blue_period: 运用期号排除蓝球
    """
    if len(data) < 5:
        return {"ok": False, "msg": "数据不足"}

    import random
    rng = random.Random(data[-1][0])

    # 1. 定胆候选
    dan_pool = set()
    dan8_result = None
    dan3_result = None
    if use_dan8:
        dan8_result = generate_eight_dan(data)
        if dan8_result and dan8_result["ok"]:
            dan_pool.update(dan8_result["candidates"])
    if use_dan3:
        dan3_result = generate_dan3_methods(data)
        if dan3_result and dan3_result["ok"]:
            dan_pool.update(dan3_result["candidates"])

    # 2. 带出表候选
    trans_result = generate_transition(data) if use_transition else None
    trans_pool = set(trans_result["candidates"]) if (trans_result and trans_result["ok"]) else set()

    # 3. 杀号排除
    kill_result = generate_kill_formulas(data) if use_kill else None
    kill_set = set(kill_result["excluded"]) if (kill_result and kill_result["ok"]) else set()

    # 合并红球候选池
    red_pool = dan_pool | trans_pool
    red_pool = red_pool - kill_set
    if len(red_pool) < 6:
        red_pool = set(range(1, 34)) - kill_set

    red_list = sorted(red_pool)

    # 4. 蓝球: 三套独立方法, 各自产出候选
    blue_tail = _blue_tails_to_kill(data) if use_blue_tail12 else {"survived": list(range(1,17))}
    blue_ten = generate_ten_blue_kills(data) if use_blue_ten else None
    blue_period = _period_based_blue_kill(data) if use_blue_period else {"survived": list(range(1,17))}

    # 从用户选中的蓝球方法中取交集(都选中才缩小)或各自独立范围
    blue_sets = []
    if use_blue_tail12:
        blue_sets.append(set(blue_tail.get("survived", range(1,17))))
    if use_blue_ten and blue_ten and blue_ten.get("ok"):
        blue_sets.append(set(blue_ten.get("candidates", range(1,17))))
    if use_blue_period:
        blue_sets.append(set(blue_period.get("survived", range(1,17))))

    if blue_sets:
        blue_candidates = sorted(set.intersection(*blue_sets))
    else:
        blue_candidates = list(range(1, 17))
    if not blue_candidates:
        blue_candidates = list(range(1, 17))

    # 生成票
    tickets = []
    used_reds = set()
    used_blues = set()

    for _ in range(n_tickets):
        for _ in range(200):  # [工程] 重试上限: 防止无限循环
            if len(red_list) >= 6:
                reds = tuple(sorted(rng.sample(red_list, 6)))
            else:
                reds = tuple(sorted(rng.sample(range(1, 34), 6)))
            if reds not in used_reds:
                used_reds.add(reds)
                break
        else:
            reds = tuple(sorted(rng.sample(range(1, 34), 6)))

        for _ in range(50):  # [工程] 重试上限: 防止无限循环
            b = rng.choice(blue_candidates)
            if b not in used_blues:
                used_blues.add(b)
                break
        else:
            b = rng.choice(list(range(1, 17)))

        tickets.append({"reds": list(reds), "blue": b})

    return {
        "ok": True,
        "algorithm": "LiZhilin-Combined",
        "tickets": tickets,
        "budget": n_tickets,
        "cost_rmb": n_tickets * TICKET_PRICE,
        "red_pool": red_list,
        "red_pool_size": len(red_list),
        "dan_pool": sorted(dan_pool) if dan_pool else [],
        "trans_pool": sorted(trans_pool) if trans_pool else [],
        "kill_excluded": sorted(kill_set) if kill_set else [],
        "blue_candidates": blue_candidates,
        "blue_methods": {
            "tail12": {
                "survived": blue_tail.get("survived", []),
                "killed_tails": blue_tail.get("killed_tails", []),
                "details": blue_tail.get("details", {}),
                "source": "原书 Part 5 §9, p252-258",
            },
            "ten_kill": {
                "survived": blue_ten.get("candidates", []) if blue_ten and blue_ten.get("ok") else [],
                "excluded": blue_ten.get("excluded", []) if blue_ten and blue_ten.get("ok") else [],
                "source": "原书 Part 5 §5, p237-241",
            },
            "period": {
                "survived": blue_period.get("survived", []),
                "excluded": blue_period.get("excluded", []),
                "source": "原书 Part 5 §10, p259-261",
            },
        },
        "unimplemented": {},
    }
