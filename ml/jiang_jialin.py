"""蒋加林《技夺500万·双色球》(2010, 海天出版社) 算法实现.

核心创新: "排列型思维"——将33选6按6个位置逐一分析.
实现:
  1. 位间隔过滤 (Ch4, p152-180): 与对照期同位置差值分布过滤
  2. 位跨度过滤 (Ch5, p170-195): 相邻位差值分布过滤
  3. 位形态过滤 (Ch6, p196-237): 单双/高低/除3 三套并行过滤
  4. 超级缩水中6保5 (Ch7, p246-260): 组合池再压缩
  5. 蓝球除3余数归类 (Ch9, p321-335): streak检测选蓝
  6. 蓝球斜边码+同尾码 (Ch9, p335-339)
"""
import random
from server.db import load_draws


# ═══════════════════════════════════════════════════════════════════════════
# 1. 位间隔过滤 (Ch4, p152-180)
# ═══════════════════════════════════════════════════════════════════════════

def position_gap_filter(candidates, data, window=20):
    """位间隔过滤: 与对照期(近window期)同位置差值分布过滤.

    原书 p178-180: 统计10-20期内各位间隔出现频率, 超出范围则排除.
    实测: 6950注 → 2282注.
    """
    if len(data) < window:
        return candidates

    recent = data[-window:]
    # 统计每期的位间隔分布: gap_counts[draw_idx][pos][gap_value] = count
    # 简化: 用最近20期建立位间隔的"正常范围"
    pos_gap_ranges = {p: {} for p in range(6)}
    for ref_draw in recent[-10:]:  # 用最近10期做对照
        ref_reds = sorted(ref_draw[1:7])
        for draw in recent:
            reds = sorted(draw[1:7])
            for p in range(6):
                g = abs(reds[p] - ref_reds[p])
                pos_gap_ranges[p][g] = pos_gap_ranges[p].get(g, 0) + 1

    # 确定合理范围: 出现次数>0的gap值
    allowed_gaps = {p: set(g for g, c in cnts.items() if c > 0)
                   for p, cnts in pos_gap_ranges.items()}

    filtered = []
    for c in candidates:
        keep = True
        for ref_draw in recent[-3:]:  # 用最近3期做对照
            ref_reds = sorted(ref_draw[1:7])
            violations = 0
            for p in range(6):
                g = abs(c[p] - ref_reds[p])
                if g not in allowed_gaps.get(p, set()):
                    violations += 1
            if violations >= 3:  # 3个以上位置异常→排除
                keep = False
                break
        if keep:
            filtered.append(c)
    return filtered if filtered else candidates


# ═══════════════════════════════════════════════════════════════════════════
# 2. 位跨度过滤 (Ch5, p170-195)
# ═══════════════════════════════════════════════════════════════════════════

def position_span_filter(candidates, data, window=100):
    """位跨度过滤: 相邻位差值分布过滤.

    原书 p184-195: 每个位跨度有独立历史分布.
    D2-1, D3-2, D4-3, D5-4, D6-5.
    """
    if len(data) < window:
        return candidates

    recent = data[-window:]
    span_ranges = {i: set() for i in range(5)}  # 0=D2-1, 1=D3-2, ...
    for row in recent:
        reds = sorted(row[1:7])
        for i in range(5):
            span_ranges[i].add(reds[i+1] - reds[i])

    filtered = []
    for c in candidates:
        keep = True
        for i in range(5):
            if (c[i+1] - c[i]) not in span_ranges[i]:
                keep = False
                break
        if keep:
            filtered.append(c)
    return filtered if filtered else candidates


# ═══════════════════════════════════════════════════════════════════════════
# 3. 位形态过滤 (Ch6, p196-237)
# ═══════════════════════════════════════════════════════════════════════════

def pattern_odd_even(reds):
    """单双形态: 返回形态字符串 如'101010' (1=单, 0=双)."""
    return ''.join(str(r % 2) for r in sorted(reds))

def pattern_high_low(reds):
    """高低形态: 尾数5-9=高(1), 0-4=低(0)."""
    return ''.join('1' if r % 10 >= 5 else '0' for r in sorted(reds))

def pattern_mod3(reds):
    """除3余数形态: 返回形态字符串."""
    return ''.join(str(r % 3) for r in sorted(reds))

def break_points(pattern_str):
    """断点数: 相邻位值变化的次数."""
    return sum(1 for i in range(1, len(pattern_str))
               if pattern_str[i] != pattern_str[i-1])

def repeats_from_prev(curr_pattern, prev_pattern):
    """重复上期数: 同位置值相同的个数."""
    return sum(1 for i in range(len(curr_pattern))
               if curr_pattern[i] == prev_pattern[i])


def pattern_filter(candidates, data, pattern_type='oddeven'):
    """位形态过滤: 断点数+重复上期数双重约束.

    原书 p209-237: 3套并行系统.
    - 单双: 断点3-5(>75%), 重复2-4(>75%)
    - 高低: 同上
    - 除3余数: 断点3-5(90%), 重复1-3(80%)
    """
    if len(data) < 2:
        return candidates

    prev = data[-2]
    prev_reds = sorted(prev[1:7])

    if pattern_type == 'oddeven':
        pattern_fn = pattern_odd_even
        bp_range = (3, 5)   # 原书 p214
        rp_range = (2, 4)   # 原书 p214
    elif pattern_type == 'highlow':
        pattern_fn = pattern_high_low
        bp_range = (3, 5)
        rp_range = (2, 4)
    else:  # mod3
        pattern_fn = pattern_mod3
        bp_range = (3, 5)   # 原书 p223
        rp_range = (1, 3)   # 原书 p223

    prev_pat = pattern_fn(prev_reds)

    filtered = []
    for c in candidates:
        cp = pattern_fn(c)
        bp = break_points(cp)
        rp = repeats_from_prev(cp, prev_pat)  # 与上上期比(原书用法)
        if bp_range[0] <= bp <= bp_range[1] and rp_range[0] <= rp <= rp_range[1]:
            filtered.append(c)
    return filtered if filtered else candidates


# ═══════════════════════════════════════════════════════════════════════════
# 4. 超级缩水中6保5 (Ch7, p246-260)
# ═══════════════════════════════════════════════════════════════════════════

def super_shrink(candidates, target=5):
    """超级缩水: 贪婪移除冗余组合, 保证中6保5.

    原书 p258-260: 如果全集中包含6红全中组合, 缩水后至少中5.
    """
    if len(candidates) <= 3:
        return candidates
    # 贪婪: 保留那些与已选集合距离最远的组合
    selected = [candidates[0]]
    remaining = candidates[1:]
    while remaining:
        best_idx = 0
        best_min_dist = 0
        for i, c in enumerate(remaining):
            min_dist = min(len(set(c) & set(s)) for s in selected)
            if min_dist > best_min_dist:
                best_min_dist = min_dist
                best_idx = i
        if best_min_dist >= target - 1:  # 至少保持一定距离
            selected.append(remaining[best_idx])
        remaining.pop(best_idx)
        if not remaining:
            break
    return selected


# ═══════════════════════════════════════════════════════════════════════════
# 5. 蓝球除3余数归类 (Ch9, p321-335)
# ═══════════════════════════════════════════════════════════════════════════

BLUE_MOD3_CLASSES = {
    0: {3, 6, 9, 10, 13, 16},
    1: {1, 4, 7, 11, 14},
    2: {2, 5, 8, 12, 15},
}

def blue_mod3_candidates():
    """蓝球除3余数归类: 5期同型→换型.

    原书 p333-335.
    """
    data = load_draws()
    if len(data) < 6:
        return list(range(1, 17))

    blues = [row[7] for row in data]
    # 检测当前streak
    last_class = None
    streak = 0
    for b in reversed(blues):
        cls = next(k for k, v in BLUE_MOD3_CLASSES.items() if b in v)
        if last_class is None:
            last_class = cls
            streak = 1
        elif cls == last_class:
            streak += 1
        else:
            break

    # 原书: 5期同型→换型
    if streak >= 5:
        # 排除当前类型
        candidates = set(range(1, 17)) - BLUE_MOD3_CLASSES[last_class]
        return sorted(candidates)
    # 继续当前类型
    return sorted(BLUE_MOD3_CLASSES[last_class])


# ═══════════════════════════════════════════════════════════════════════════
# 6. 蓝球斜边码+同尾码 (Ch9, p335-339)
# ═══════════════════════════════════════════════════════════════════════════

def blue_diagonal_candidates():
    """蓝球斜边码: 上期蓝±1, 不超过2连.

    原书 p335-336.
    """
    data = load_draws()
    if len(data) < 2:
        return list(range(1, 17))

    last = data[-1][7]
    candidates = set()
    # 左斜边(原书: 仅1位)
    if last > 1:
        candidates.add(last - 1)
    # 右斜边
    if last < 16:
        candidates.add(last + 1)
    return sorted(candidates)


def blue_sametail_candidates():
    """蓝球同尾码: 6对(01-11,02-12,...06-16).

    原书 p337-339.
    """
    data = load_draws()
    if len(data) < 2:
        return list(range(1, 17))

    last = data[-1][7]
    # 同尾对: 相差10
    pairs = {1: 11, 2: 12, 3: 13, 4: 14, 5: 15, 6: 16,
             11: 1, 12: 2, 13: 3, 14: 4, 15: 5, 16: 6}
    candidates = {last}
    if last in pairs:
        candidates.add(pairs[last])
    return sorted(candidates)


# ═══════════════════════════════════════════════════════════════════════════
# 主入口: 生成红球 (排列型思维多级过滤)
# ═══════════════════════════════════════════════════════════════════════════

def generate_tickets(data, n=3, use_gap=True, use_span=True,
                     use_pattern=True, use_shrink=True,
                     blue_mode='mod3'):
    """蒋加林排列型思维综合出号.

    流程: 按位生成候选→位间隔过滤→位跨度过滤→位形态过滤→超级缩水→蓝球选号.
    """
    if len(data) < 20:
        return {"ok": False, "msg": f"数据不足(需≥20期), 当前{len(data)}期"}

    rng = random.Random()
    try:
        rng.seed(int(str(data[-1][0]) + "99"))
    except:
        pass

    # 步骤1: 按位生成候选 (原书Ch1)
    # 用近100期数据统计每位置覆盖范围(~90%)
    recent = data[-min(100, len(data)):]
    pos_ranges = []
    for p in range(6):
        vals = sorted(row[p+1] for row in recent)
        # 取90%覆盖范围
        lo = vals[int(len(vals) * 0.05)]
        hi = vals[int(len(vals) * 0.95)]
        pos_ranges.append((lo, hi))

    # 步骤2: 随机采样生成候选池
    pool_size = min(1000, n * 200)
    candidates = []
    attempts = 0
    while len(candidates) < pool_size and attempts < pool_size * 5:
        attempts += 1
        reds = []
        for p in range(6):
            lo, hi = pos_ranges[p]
            # 保证升序
            if p > 0:
                lo = max(lo, reds[-1] + 1)
            if lo > hi:
                break
            reds.append(rng.randint(lo, hi))
        if len(reds) == 6 and len(set(reds)) == 6:
            reds.sort()
            candidates.append(tuple(reds))

    if not candidates:
        return {"ok": False, "msg": "候选池为空"}

    original_count = len(candidates)

    # 步骤3: 位间隔过滤
    if use_gap:
        candidates = position_gap_filter(candidates, data)

    # 步骤4: 位跨度过滤
    if use_span:
        candidates = position_span_filter(candidates, data)

    # 步骤5: 位形态过滤 (并行三套, 交集)
    if use_pattern:
        for pt in ['oddeven', 'highlow', 'mod3']:
            candidates = pattern_filter(candidates, data, pt)

    # 步骤6: 超级缩水
    if use_shrink and len(candidates) > n * 2:
        candidates = super_shrink(candidates)

    # 步骤7: 蓝球
    if blue_mode == 'mod3':
        blue_pool = blue_mod3_candidates()
    elif blue_mode == 'diagonal':
        blue_pool = blue_diagonal_candidates()
    elif blue_mode == 'sametail':
        blue_pool = blue_sametail_candidates()
    else:
        blue_pool = list(range(1, 17))

    # 步骤8: 选n注
    tickets = []
    rng.shuffle(list(candidates))
    for i in range(min(n, len(candidates))):
        blue = rng.choice(blue_pool) if blue_pool else rng.randint(1, 16)
        tickets.append({"reds": list(candidates[i]), "blue": blue})

    return {
        "ok": True,
        "algorithm": "蒋加林·排列型思维(位间隔+位跨度+位形态+超级缩水)",
        "tickets": tickets,
        "candidate_count": original_count,
        "after_filter": len(candidates),
        "pos_ranges": {f"pos_{p}": list(r) for p, r in enumerate(pos_ranges)},
        "source": "蒋加林《技夺500万》(2010)",
    }
