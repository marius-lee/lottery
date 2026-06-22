"""张委铭《双色球杀号定胆选号方法与技巧超级大全》(2015) 算法实现.

十二值选号法 (Ch6§3, p228-236):
  用胜率最低的18种前区杀号方法每期所杀号码反向选红球.
  平均每期~12.4个候选号码, 按位置策略选号:
    - 位置1-2: 优先从候选池前8个选
    - 位置3-4: 从候选池剩余+相邻号码(±1)选
    - 位置5: 避开候选池, 选相邻号码
    - 位置6: 避开候选池, 主选30-33
  1767期回测: 平均选中4.95个/期, ≥4个占93.44%.

八值选号法 (Ch8§1, p294-300):
  用胜率最低的11种后区杀号方法每期所杀号码反向选蓝球.
  平均每期~7.8个候选蓝球, 成功率53.68% (理论48.62%).
  连续出错≤1次后下期正确率>52%.
"""
from ml.ssq_constants import TICKET_PRICE
import random


# ═══════════════════════════════════════════════════════════════════════════
# 杀号规则 — 将计算值映射到有效号码范围
# ═══════════════════════════════════════════════════════════════════════════

def _map_to_red(value):
    """将任意整数映射到1-33红球范围 (杀号规则, 原书第3章).

    规则 (通过p238示例推导并验证):
      - 1≤value≤33: 直接使用
      - value<1: 取绝对值
        · |v|≤33: 直接使用 (如 -4→4, -29→29)
        · |v|>33: 取个位数, 0→10 (如 -58→8, -64→4)
      - value>33: 取个位数, 0→10 (如 35→5)
    验证: 18种方法对2003004期计算, 全部18个杀号值均命中书中结果.
    """
    if 1 <= value <= 33:
        return value
    av = abs(value)
    if av <= 33:
        return av
    unit = av % 10
    return 10 if unit == 0 else unit


def _map_to_blue(value):
    """将任意整数映射到1-16蓝球范围 (杀号规则, 原书第4章).

    规则: 1-16直接使用; >16取个位数(原书U型方法); <1取绝对值后同样处理.
    来源: 原书第4章, 通过p238八值选号法示例验证:
      24→4, 19→9, 36→6 (取个位数); -10→10 (取绝对值).
    """
    v = abs(value)
    if 1 <= v <= 16:
        return v
    # >16: 取个位数, 0→10 (没有蓝球0)
    unit = v % 10
    return 10 if unit == 0 else unit


# ═══════════════════════════════════════════════════════════════════════════
# 围号选号法 — 18种最低胜率前区杀号方法 (2017版 Ch7§1, 表7.2, p168-169)
# ═══════════════════════════════════════════════════════════════════════════

# 胜率最低的18种前区杀号方法 (按对应号码出现次数从低到高排序)
# 来源: 原书2017版第七章第一节 表7.2, 统计周期2003001-2016105共2004期
# 注: 本表替换2015版十二值选号法的18种方法 (因2017版新增260+种杀号方法)
# 符号约定: C=前区减常数, D=前区加常数, I=后区减常数, J=后区加常数,
#           A=前区互减, K=前区-后区

_RED_KILL_METHODS_18 = [
    ("D2+38",  lambda r, b: _map_to_red(r[1] + 38)),      # 第2个+38, 出现400次
    ("I13",    lambda r, b: _map_to_red(b - 13)),          # 后区-13, 出现400次
    ("J7",     lambda r, b: _map_to_red(b + 7)),           # 后区+7, 出现400次
    ("A4-2",   lambda r, b: _map_to_red(r[3] - r[1])),    # 第4个-第2个, 出现401次
    ("J2",     lambda r, b: _map_to_red(b + 2)),           # 后区+2, 出现401次
    ("C5-49",  lambda r, b: _map_to_red(r[4] - 49)),      # 第5个-49, 出现402次
    ("D1+1",   lambda r, b: _map_to_red(r[0] + 1)),       # 第1个+1, 出现402次
    ("K3",     lambda r, b: _map_to_red(r[2] - b)),        # 第3个-后区, 出现402次
    ("C1-9",   lambda r, b: _map_to_red(r[0] - 9)),       # 第1个-9, 出现403次
    ("I22",    lambda r, b: _map_to_red(b - 22)),          # 后区-22, 出现403次
    ("C6-62",  lambda r, b: _map_to_red(r[5] - 62)),      # 第6个-62, 出现405次
    ("C1-69",  lambda r, b: _map_to_red(r[0] - 69)),      # 第1个-69, 出现406次
    ("D1+15",  lambda r, b: _map_to_red(r[0] + 15)),      # 第1个+15, 出现408次
    ("I32",    lambda r, b: _map_to_red(b - 32)),          # 后区-32, 出现408次
    ("C2-2",   lambda r, b: _map_to_red(r[1] - 2)),       # 第2个-2, 出现417次
    ("C4-14",  lambda r, b: _map_to_red(r[3] - 14)),      # 第4个-14, 出现417次
    ("C6-7",   lambda r, b: _map_to_red(r[5] - 7)),       # 第6个-7, 出现418次
    ("C6-11",  lambda r, b: _map_to_red(r[5] - 11)),      # 第6个-11, 出现426次
]


def _compute_weihao_values(data):
    """计算围号选号法的候选号码池 (2017版替代十二值选号法).

    Args:
        data: 最近一期开奖数据 [period, r1..r6, blue]

    Returns:
        (candidates_sorted, method_details):
          candidates_sorted: 排序去重后的候选号码列表
          method_details: {method_name: killed_number}
    """
    last = data[-1]
    reds = sorted(last[1:7])
    blue = last[7]

    kills = []
    method_details = {}
    for name, fn in _RED_KILL_METHODS_18:
        killed = fn(reds, blue)
        kills.append(killed)
        method_details[name] = killed

    # 去重排序 (原书 p238: "去掉重复项并按由小到大的顺序进行排列")
    unique = sorted(set(k for k in kills if 1 <= k <= 33))
    return unique, method_details


def generate_weihao(data, n_tickets=3, locked_dans=None):
    """围号选号法 (2017版替代十二值选号法): 生成红球候选+位置策略选号.

    原书2017版 七、具体运用 (p232-233):
      (1) 位置1-2: 从候选池前8个号码中选
      (2) 位置3-4: 从池剩余号码+相邻号码(±1)中选
      (3) 位置5: 避开候选池, 选相邻号码
      (4) 位置6: 避开候选池, 主选30-33

    Args:
        data: 全部历史开奖数据
        n_tickets: 生成注数
        locked_dans: 锁定的定胆号码列表 (来自Ch5定胆法), None=不锁定
                     锁定后这些号码必定出现在每注中, 排序后自然落位

    Returns:
        dict with candidates, tickets (位置策略选号), method_details, stats
    """
    if len(data) < 5:
        return {"ok": False, "msg": "数据不足(需≥5期)"}

    candidates, method_details = _compute_weihao_values(data)

    if len(candidates) < 6:
        return {"ok": False, "msg": f"候选池太小({len(candidates)}个号码), 无法选号"}

    # 位置策略选号 (原书六、具体运用 p232-233)
    rng = random.Random(data[-1][0])  # 用最近期号做种子, 可复现

    # 候选池的前8个 (原书: "最好从胜率最低的18种杀号方法每期所杀的号码里面前8个号码中...")
    first8 = candidates[:8]

    # 相邻号码池 (候选池所有号码的±1)
    adjacent = set()
    for n in candidates:
        if n > 1: adjacent.add(n - 1)
        if n < 33: adjacent.add(n + 1)
    adjacent = sorted(adjacent)

    # 位置3-4候选: 池中未用作位置1-2的号码 + 相邻号码
    pool_rest = [n for n in candidates if n not in first8] if len(first8) >= 2 else candidates

    # 位置6候选: 30-33 (原书: "主要在30~33这四个号码中选择")
    pos6_pool = [30, 31, 32, 33]

    def _safe_choice(candidates_list, exclude_set=None):
        """安全选号: 候选非空则选, 否则从全范围回退."""
        cands = [n for n in candidates_list if n not in (exclude_set or set())]
        if cands:
            return rng.choice(cands)
        fb = [n for n in range(1, 34) if n not in (exclude_set or set())]
        if fb:
            return rng.choice(fb)
        return 1

    tickets = []
    used_reds = set()

    dans = locked_dans or []
    n_dan = len(dans)
    need = 6 - n_dan  # 有胆码时, 只需选6-N个补充号码

    for _ in range(n_tickets):
        reds = []
        used = set()

        # 锁定定胆 (原书 Ch5: 胆码=该号码必定在下期出现, 不指定位置)
        for d in dans:
            if d not in used:
                reds.append(d)
                used.add(d)

        # 按位置策略选补充号码, 直到凑齐6个 (原书 p232-233)
        positions = [
            lambda: _safe_choice([n for n in first8 if n not in used]),
            lambda: _safe_choice(
                [n for n in first8 if n > reds[-1] and n not in used] or
                [n for n in candidates if n > reds[-1] and n not in used],
                used),
            lambda: _safe_choice(
                list(set([n for n in (pool_rest + adjacent) if n > reds[-1]])),
                used),
            lambda: _safe_choice(
                list(set([n for n in (pool_rest + adjacent) if n > reds[-1]])),
                used),
            lambda: _safe_choice(
                [n for n in adjacent if n > reds[-1] and n not in candidates],
                used),
            lambda: _safe_choice(
                [n for n in pos6_pool if n > reds[-1]],
                used),
        ]

        for i in range(need):
            fn = positions[min(i, len(positions)-1)]
            pick = fn()
            used.add(pick)
            reds.append(pick)

        # 排序 (原书: 胆码出现在其自然位置, 不强制特定位置)
        reds.sort()

        reds_tuple = tuple(reds)
        if reds_tuple in used_reds:
            continue
        used_reds.add(reds_tuple)

        tickets.append({
            "reds": list(reds),
            "blue": None,  # 蓝球由调用方分配
        })

    # 统计 (原书 p233 结论)
    return {
        "ok": True,
        "algorithm": "ZhangWeiming-Weihao",
        "candidates": candidates,
        "candidate_count": len(candidates),
        "first8": first8,
        "adjacent_pool": adjacent,
        "method_details": method_details,
        "tickets": tickets,
        "budget": len(tickets),
        "cost_rmb": len(tickets) * TICKET_PRICE,
        "position_strategy": {
            "pos1_2": "候选池前8个",
            "pos3_4": "候选池剩余+相邻±1",
            "pos5": "避开候选池,选相邻",
            "pos6": "30-33",
        },
        "historical_stats": {
            "avg_hits_per_period": 2.53,
            "pct_ge_3": 50.22,
            "pct_ge_4": 17.88,
            "pct_ge_5": 3.10,
            "six_hits": "6次/2004期",
            "source": "原书2017版表7.2, 2004期回测, p169-170",
            "validation": "57期外样本验证, ≥4占~20%",
        },
        "locked_dans": dans,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 后区围号选号法 — 10种最低胜率后区杀号方法 (2017版 Ch8§1, 表8.1, p209)
# ═══════════════════════════════════════════════════════════════════════════

# 胜率最低的10种后区杀号方法 (按对应号码出现次数从低到高排序)
# 来源: 原书2017版第八章第一节 表8.1, 统计周期2003001-2016105共2004期
# 注: 本表替换2015版八值选号法的11种方法 (因2017版新增440+种后区杀号方法)
# 符号约定: C=前区减常数, D=前区加常数, I=后区减常数, J=后区加常数

_BLUE_KILL_METHODS_10 = [
    ("D1+10",  lambda r, b, r_prev: _map_to_blue(r[0] + 10)),       # 第1个+10, 出现146次
    ("C4-6",   lambda r, b, r_prev: _map_to_blue(r[3] - 6)),         # 第4个-6, 出现146次
    ("I25",    lambda r, b, r_prev: _map_to_blue(b - 25)),           # 后区-25, 出现146次
    ("J20",    lambda r, b, r_prev: _map_to_blue(b + 20)),           # 后区+20, 出现146次
    ("C5-12",  lambda r, b, r_prev: _map_to_blue(r[4] - 12)),       # 第5个-12, 出现147次
    ("D6+5",   lambda r, b, r_prev: _map_to_blue(r[5] + 5)),        # 第6个+5, 出现147次
    ("J4",     lambda r, b, r_prev: _map_to_blue(b + 4)),            # 后区+4, 出现148次
    ("C3-30",  lambda r, b, r_prev: _map_to_blue(r[2] - 30)),       # 第3个-30, 出现150次
    ("C6-47",  lambda r, b, r_prev: _map_to_blue(r[5] - 47)),       # 第6个-47, 出现154次
    ("C5-51",  lambda r, b, r_prev: _map_to_blue(r[4] - 51)),       # 第5个-51, 出现166次
]


def _compute_weihao_blue_values(data):
    """计算后区围号选号法的候选蓝球池 (2017版替代八值选号法).

    Args:
        data: 全部历史开奖数据

    Returns:
        (candidates_sorted, method_details, consecutive_errors):
          candidates_sorted: 排序去重后的候选蓝球列表
          method_details: {method_name: killed_number}
          consecutive_errors: 最近连续出错次数 (用于判断何时使用)
    """
    last = data[-1]
    reds = sorted(last[1:7])
    blue = last[7]

    # 所有方法仅需当期数据, 无上期依赖
    kills = []
    method_details = {}
    for name, fn in _BLUE_KILL_METHODS_10:
        killed = fn(reds, blue, None)
        kills.append(killed)
        method_details[name] = killed

    # 去重排序
    unique = sorted(set(k for k in kills if 1 <= k <= 16))

    # 计算连续出错次数
    consecutive_errors = 0
    for i in range(len(data) - 1, max(0, len(data) - 20), -1):
        period_data = data[i]
        period_reds = sorted(period_data[1:7])
        period_blue = period_data[7]

        period_kills = set()
        for name, fn in _BLUE_KILL_METHODS_10:
            period_kills.add(fn(period_reds, period_blue, None))

        if i + 1 < len(data):
            next_blue = data[i+1][7]
            if next_blue in period_kills:
                break
            else:
                consecutive_errors += 1
        else:
            break

    return unique, method_details, consecutive_errors


def generate_weihao_blue(data, n_tickets=3):
    """后区围号选号法 (2017版替代八值选号法): 生成蓝球候选池及选号.

    原书2017版第八章第一节 p206-210.

    Args:
        data: 全部历史开奖数据
        n_tickets: 生成注数

    Returns:
        dict with candidates, tickets (蓝球分配), method_details, stats
    """
    if len(data) < 3:
        return {"ok": False, "msg": "数据不足(需≥3期)"}

    candidates, method_details, consecutive_errors = _compute_weihao_blue_values(data)

    if len(candidates) < 1:
        return {"ok": False, "msg": "候选池为空"}

    # 连续出错判断 (原书2017版: 八值法成功率53.68%)
    # [数学] 连续错4次概率: (1-0.5368)^4 = 0.4632^4 ≈ 4.6% < 5%显著性阈值
    use_recommendation = "建议使用" if consecutive_errors >= 1 else "正常使用"
    if consecutive_errors >= 4:
        use_recommendation = "强烈建议使用 (连续错≥4次,概率<5%)"

    # 蓝球分配: 从候选池中随机选
    rng = random.Random(data[-1][0])

    tickets = []
    used_blues = set()
    for _ in range(n_tickets):
        available = [b for b in candidates if b not in used_blues]
        if not available:
            available = candidates
        blue = rng.choice(available)
        used_blues.add(blue)
        tickets.append({
            "reds": [],  # 红球由调用方分配
            "blue": blue,
        })

    return {
        "ok": True,
        "algorithm": "ZhangWeiming-WeihaoBlue",
        "candidates": candidates,
        "candidate_count": len(candidates),
        "method_details": method_details,
        "tickets": tickets,
        "budget": len(tickets),
        "cost_rmb": len(tickets) * TICKET_PRICE,
        "consecutive_errors": consecutive_errors,
        "use_recommendation": use_recommendation,
        "historical_stats": {
            "success_rate_pct": 54.47,
            "theoretical_rate_pct": 47.93,
            "avg_candidates": 7.67,
            "total_tests": 2003,
            "source": "原书2017版2003期回测, p210",
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# 定胆方法 (2017版 Ch5, p117-129)
# ═══════════════════════════════════════════════════════════════════════════

def generate_dan1_alternating(data):
    """一四定胆法 (Ch5 §5.2.3, p117-120).

    按开奖期号奇偶轮流使用两种杀号方法, 每期锁定1个胆码:
      - 奇数期: C2-2 (第2个号码-2)
      - 偶数期: C6-11 (第6个号码-11)
    成功率: 21.57% (2003期回测), 超过理论18.18%.

    来源: 原书表5.3, 一四定胆法 432胜/1571败 = 21.57%
    """
    if len(data) < 2:
        return {"ok": False, "msg": "数据不足"}

    last = data[-1]
    period = last[0]
    reds = sorted(last[1:7])

    # 期号奇偶决定用哪个方法
    if period % 2 == 1:  # 奇数期
        dan = _map_to_red(reds[1] - 2)  # C2-2: "四"
        method = "C2-2(四)"
    else:  # 偶数期
        dan = _map_to_red(reds[5] - 11)  # C6-11: "一"
        method = "C6-11(一)"

    return {
        "ok": True,
        "algorithm": "ZhangWeiming-Dan1-Alternating",
        "dan": dan,
        "method_used": method,
        "period": period,
        "period_parity": "奇数→C2-2" if period % 2 == 1 else "偶数→C6-11",
        "historical_stats": {
            "success_rate_pct": 21.57,
            "theoretical_rate_pct": 18.18,
            "wins": 432,
            "losses": 1571,
            "source": "原书2017版表5.3, 2003期回测, p119",
        },
    }


def generate_dan1_range(data, method_count=7):
    """X.X定胆法 (Ch5 §5.2.4, p121-124): 用胜率最低N种杀号→候选池→至少定1胆.

    候选池大小与成功率:
      7种(6.4定胆法): ~6.5候选, 81.66%成功率
      6种(5.6定胆法): ~5.6候选, 76.51%
      5种(4.7定胆法): ~4.8候选, 70.06%
      4种(3.8定胆法): ~3.9候选, 62.25%
      3种(2.9定胆法): ~3.0候选, 51.84%
      2种(1.9定胆法): ~2.0候选, 39.16%

    来源: 原书2017版 §5.2.4, p121-124
    """
    if len(data) < 2:
        return {"ok": False, "msg": "数据不足"}

    last = data[-1]
    reds = sorted(last[1:7])
    blue = last[7]

    # 胜率最低的7种方法 (按优先级, 来源: 原书p123-124)
    method_pool = _RED_KILL_METHODS_18[:method_count]

    kills = []
    for name, fn in method_pool:
        kills.append(fn(reds, blue))

    unique = sorted(set(k for k in kills if 1 <= k <= 33))

    return {
        "ok": True,
        "algorithm": f"ZhangWeiming-Dan1-Range{len(unique)}",
        "candidates": unique,
        "candidate_count": len(unique),
        "method_count": method_count,
        "historical_stats": {
            7: {"label": "6.4定胆法", "candidates": 6.5, "rate": 81.66},
            6: {"label": "5.6定胆法", "candidates": 5.6, "rate": 76.51},
            5: {"label": "4.7定胆法", "candidates": 4.8, "rate": 70.06},
            4: {"label": "3.8定胆法", "candidates": 3.9, "rate": 62.25},
            3: {"label": "2.9定胆法", "candidates": 3.0, "rate": 51.84},
            2: {"label": "1.9定胆法", "candidates": 2.0, "rate": 39.16},
        }.get(method_count, {}),
        "source": "原书2017版 §5.2.4, p121-124",
    }


def generate_dan2_optimal(data):
    """定两个胆码最优方法 (Ch5 §5.3.3, p127-129).

    用杀号方法两两组合形成两号组合, 按优先级:
      1. 组合A: C6-11 + C2-2 (86次/2003期, 4.29%)
      2. 组合B: C1-9 + D1+15 (85次)
      3. 组合C: C1-69 + D1+15 (83次)
      4. 组合D: C6-11 + J2 (82次)
      5. 组合E: C6-7 + K3 (82次)
    若高优先级组合两方法得出同一号码 → 降级使用下一组合.

    来源: 原书2017版 §5.3.3, 表5.4, p127-129
    """
    if len(data) < 2:
        return {"ok": False, "msg": "数据不足"}

    last = data[-1]
    reds = sorted(last[1:7])
    blue = last[7]

    # 5个组合, 按优先级
    combos = [
        ("A", _map_to_red(reds[5] - 11), _map_to_red(reds[1] - 2),   86),  # C6-11 + C2-2
        ("B", _map_to_red(reds[0] - 9),  _map_to_red(reds[0] + 15),  85),  # C1-9 + D1+15
        ("C", _map_to_red(reds[0] - 69), _map_to_red(reds[0] + 15),  83),  # C1-69 + D1+15
        ("D", _map_to_red(reds[5] - 11), _map_to_red(blue + 2),      82),  # C6-11 + J2
        ("E", _map_to_red(reds[5] - 7),  _map_to_red(reds[2] - blue), 82),  # C6-7 + K3
    ]

    selected = None
    for name, a, b, count in combos:
        if a != b:  # 两个方法得出不同号码
            selected = (name, sorted([a, b]), count)
            break

    if selected is None:
        return {"ok": False, "msg": "所有组合均得出同一号码, 无法定2胆"}

    return {
        "ok": True,
        "algorithm": "ZhangWeiming-Dan2-Optimal",
        "combo_name": selected[0],
        "dan2": selected[1],
        "historical_count": selected[2],
        "historical_stats": {
            "combo_A": {"pair": "C6-11 + C2-2", "count": 86, "pct": 4.29},
            "combo_B": {"pair": "C1-9 + D1+15", "count": 85, "pct": 4.24},
            "combo_C": {"pair": "C1-69 + D1+15", "count": 83, "pct": 4.14},
            "combo_D": {"pair": "C6-11 + J2", "count": 82, "pct": 4.09},
            "combo_E": {"pair": "C6-7 + K3", "count": 82, "pct": 4.09},
            "theoretical_rate_pct": 2.84,
            "source": "原书2017版 §5.3.3, p127-129, 2003期回测",
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# 行列选号法 (Ch7§12, p285-293) — 3行11列网格自动断区
# ═══════════════════════════════════════════════════════════════════════════

# 3行11列表 (原书表7-29, p286)
# 每行11个号码, 每列3个号码 — 行列之间号码分布均匀
ROW_3x11 = {
    1: list(range(1, 12)),    # 01-11
    2: list(range(12, 23)),   # 12-22
    3: list(range(23, 34)),   # 23-33
}
COL_3x11 = {c: [c, c + 11, c + 22] for c in range(1, 12)}


def _get_breaks_3x11(reds):
    """计算一组红球在3×11网格中的断行/断列."""
    rows_with = {r for r in range(1, 4)
                 if any(n in ROW_3x11[r] for n in reds)}
    cols_with = {c for c in range(1, 12)
                 if any(n in COL_3x11[c] for n in reds)}
    break_rows = {1, 2, 3} - rows_with
    break_cols = set(range(1, 12)) - cols_with
    return break_rows, break_cols


def _auto_detect_grid_breaks(data):
    """自动检测下期应断哪些行/列。

    原书使用全部1798期统计得出以下规则 (p291-293):
      - 行规则: 某行本期断→下期93%不再断 → 不断该行
      - 列规则: 连续断1-2次→继续断; 连续断≥3次→停止断

    本函数使用全部可用历史数据计算列连续断次数, 与原书全量统计方法一致.

    Returns:
        (break_rows, break_cols, mode, mode_desc):
          break_rows: 应断的行号集合
          break_cols: 应断的列号集合
          mode: '0r6c' | '1r7c' | '0r5c' | 'auto'
          mode_desc: 模式描述
    """
    if len(data) < 2:
        return set(), set(), 'auto', '数据不足'

    last = data[-1]
    last_reds = sorted(last[1:7])
    last_br, last_bc = _get_breaks_3x11(last_reds)

    # ── 行自动检测 (原书 p291) ──
    # "约93%的情况下某一行本期断行之后，下期就不会再断了"
    # 来源: 原书对1798期全量统计
    break_rows = set()  # 默认断0行

    # 检查是否有行连续断2次+ (仅7%), 如果有则继续断
    # 来源: 原书p291 "一行连续断2次及2次以上的情况不超过7%"
    for r in range(1, 4):
        streak = 0
        for period in reversed(data):
            period_reds = sorted(period[1:7])
            br, _ = _get_breaks_3x11(period_reds)
            if r in br:
                streak += 1
            else:
                break
        if streak >= 2:
            break_rows.add(r)

    # ── 列自动检测 (原书 p292-293) ──
    # 原书对第一列和第二列全量1798期统计得出:
    #   断1次→53.25%继续 | 断2次→75.3%继续 | 断3次+→<16%继续
    col_streaks = {}
    for c in range(1, 12):
        streak = 0
        for period in reversed(data):
            period_reds = sorted(period[1:7])
            _, bc = _get_breaks_3x11(period_reds)
            if c in bc:
                streak += 1
            else:
                break
        col_streaks[c] = streak

    # 应用规则 (原书 p293):
    # streak=1或2 → 继续断 (53.25%/75.3%继续)
    # streak≥3 → 停止断 (<16%继续)
    # streak=0 → 不主动断, 除非列热度极低
    break_cols = set()
    for c, streak in col_streaks.items():
        if streak in (1, 2):
            break_cols.add(c)  # 继续断
        # streak≥3: 不加入 (停止断)
        # streak=0: 不加入

    # ── 确定模式 ──
    n_rows = len(break_rows)
    n_cols = len(break_cols)

    # 计算剩余号码数 (断行和断列的排除可能有重叠, 要正确处理)
    all_excluded = set()
    for r in break_rows:
        all_excluded.update(ROW_3x11[r])
    for c in break_cols:
        all_excluded.update(COL_3x11[c])
    remaining = 33 - len(all_excluded)
    remaining_numbers = sorted(set(range(1, 34)) - all_excluded)

    # 模式判断
    if n_rows == 0 and 5 <= n_cols <= 6:
        mode = '0r6c'
        mode_desc = f'断0行{n_cols}列 · {remaining}个号码 · 概率约41%'
    elif n_rows == 1 and n_cols >= 6:
        mode = '1r7c'
        mode_desc = f'断1行{n_cols}列 · {remaining}个号码 · 概率约2.5%'
    elif n_rows == 0 and n_cols >= 7:
        mode = '0r7c'
        mode_desc = f'断0行{n_cols}列 · {remaining}个号码 · 概率约16%'
    elif n_rows == 0 and n_cols <= 4:
        mode = 'wide'
        mode_desc = f'断0行{n_cols}列 · {remaining}个号码 · 条件较宽'
    else:
        mode = 'auto'
        mode_desc = f'断{n_rows}行{n_cols}列 · {remaining}个号码'

    return break_rows, break_cols, mode, mode_desc, remaining_numbers


def generate_grid_selection(data, n_tickets=3):
    """行列选号法: 3×11网格自动断区 → 缩小候选池 → 选号.

    原书第七章第十二节 p285-293.
    全自动 — 不依赖用户手动选择断区码.

    Args:
        data: 全部历史开奖数据
        n_tickets: 生成注数

    Returns:
        dict with tickets, grid_info, mode
    """
    if len(data) < 10:  # [工程] 行列网格最少需要10期数据做断区统计
        return {"ok": False, "msg": "数据不足(需≥10期)"}

    break_rows, break_cols, mode, mode_desc, remaining_numbers = \
        _auto_detect_grid_breaks(data)

    if len(remaining_numbers) < 6:
        # 候选太少, 放宽条件: 不断行, 只断明确该断的列
        _, bc, _, _ = _get_breaks_3x11(sorted(data[-1][1:7]))
        break_rows = set()
        break_cols = {c for c in bc if c in break_cols}  # 只保留同时在上期断了且规则建议断的
        # 重新计算
        all_ex = set()
        for c in break_cols:
            all_ex.update(COL_3x11[c])
        remaining_numbers = sorted(set(range(1, 34)) - all_ex)
        if len(remaining_numbers) < 6:
            remaining_numbers = list(range(1, 34))

    # 从剩余号码中采样
    rng = random.Random(data[-1][0])

    tickets = []
    used_reds = set()

    pool = remaining_numbers

    for _ in range(n_tickets):
        for _ in range(200):
            if len(pool) >= 6:
                reds = tuple(sorted(rng.sample(pool, 6)))
            else:
                reds = tuple(sorted(rng.sample(range(1, 34), 6)))
            if reds not in used_reds:
                used_reds.add(reds)
                tickets.append({"reds": list(reds), "blue": None})
                break
        else:
            reds = tuple(sorted(rng.sample(range(1, 34), 6)))
            tickets.append({"reds": list(reds), "blue": None})

    # 蓝球分配
    from ml.micro_portfolio import _blue_freq_weights, _pick_blue
    bw = _blue_freq_weights()
    for t in tickets:
        t["blue"] = _pick_blue(bw)

    return {
        "ok": True,
        "algorithm": "ZhangWeiming-Grid-3x11",
        "tickets": tickets,
        "budget": len(tickets),
        "cost_rmb": len(tickets) * TICKET_PRICE,
        "grid": {
            "layout": "3行×11列",
            "break_rows": sorted(break_rows),
            "break_cols": sorted(break_cols),
            "mode": mode,
            "mode_desc": mode_desc,
            "remaining_count": len(remaining_numbers),
            "remaining_numbers": remaining_numbers,
        },
        "auto_rules": {
            "row_rule": "本期断行→下期93%不断 (原书p291)",
            "col_rule_streak_1_2": "继续断 (53-75%概率, 原书p292-293)",
            "col_rule_streak_ge_3": "停止断 (<16%概率, 原书p293)",
        },
        "historical_reference": {
            "mode_0r6c": "断0行6列·15号码·概率40.99% (原书表7-35)",
            "mode_0r5c": "断0行5列·18号码·概率22.14%",
            "mode_0r7c": "断0行7列·12号码·概率15.96%",
            "mode_1r6c": "断1行6列·10号码·概率9.45%",
            "mode_1r7c": "断1行7列·8号码·概率2.45%",
            "source": "原书1798期统计, p291",
        },
    }

def generate_combined(data, n_tickets=3, locked_dans=None):
    """围号红球 + 后区围号蓝球 组合模式 (2017版).

    原书2017版: 围号选号法(Ch7§1) + 后区围号选号法(Ch8§1)
    """
    if len(data) < 5:
        return {"ok": False, "msg": "数据不足"}

    red_result = generate_weihao(data, n_tickets, locked_dans=locked_dans)
    blue_result = generate_weihao_blue(data, n_tickets)

    if not red_result["ok"]:
        return red_result
    if not blue_result["ok"]:
        return blue_result

    tickets = []
    for i in range(n_tickets):
        reds = red_result["tickets"][i]["reds"] if i < len(red_result["tickets"]) else []
        blue = blue_result["tickets"][i]["blue"] if i < len(blue_result["tickets"]) else 1
        tickets.append({"reds": reds, "blue": blue})

    return {
        "ok": True,
        "algorithm": "ZhangWeiming-Weihao-Combined",
        "tickets": tickets,
        "budget": n_tickets,
        "cost_rmb": n_tickets * TICKET_PRICE,
        "weihao": {
            "candidates": red_result["candidates"],
            "candidate_count": red_result["candidate_count"],
            "position_strategy": red_result["position_strategy"],
            "stats": red_result["historical_stats"],
        },
        "weihao_blue": {
            "candidates": blue_result["candidates"],
            "candidate_count": blue_result["candidate_count"],
            "consecutive_errors": blue_result["consecutive_errors"],
            "use_recommendation": blue_result["use_recommendation"],
            "stats": blue_result["historical_stats"],
        },
    }
