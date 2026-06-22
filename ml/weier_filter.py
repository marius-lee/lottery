"""微尔算法 (彩乐乐, 2017) — 严格按原书实现.

完整流程 (原书第5-7章):
  1. 遗漏值追踪 → 热温冷动态选择 (7条规则, 非1条)
  2. 规律检测窄化 (N带一/对补数/前后呼应/旺者恒旺/打破局)
  3. 跨位置约束传播 (12位→23位→34位, 相互约束)
  4. 8步条件逐层过滤_valid_reds全量池
  5. 全量导出

原书案例产出: 12注/68注/319注, 取决于条件松紧程度.
"""
from ml.ssq_constants import TICKET_PRICE

_ROUTE = {n: n % 3 for n in range(1, 34)}
_ALL_RATIOS = ['0:0', '0:1', '0:2', '1:0', '1:1', '1:2', '2:0', '2:1', '2:2']

PAIRS_A = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)]
PAIRS_B = [(0, 2), (0, 3), (0, 4), (0, 5)]
PAIRS_C = [(1, 3), (1, 4), (1, 5), (2, 4), (2, 5)]
ALL_PAIRS = PAIRS_A + PAIRS_B + PAIRS_C


# ═══════════════════════════════════════════════════════════════════════════
# 遗漏值 (原书第6章 p.075)
# ═══════════════════════════════════════════════════════════════════════════

def _compute_omissions(data, pairs):
    """计算每个位比值条件的遗漏值."""
    omissions = {}
    for pair in pairs:
        omissions[pair] = {r: float('inf') for r in _ALL_RATIOS}
    for period_offset, row in enumerate(reversed(data)):
        reds = sorted(row[1:7])
        for pair in pairs:
            ratio = f"{_ROUTE[reds[pair[0]]]}:{_ROUTE[reds[pair[1]]]}"
            if omissions[pair][ratio] == float('inf'):
                omissions[pair][ratio] = period_offset
    return omissions


def _classify(omission):
    """热温冷分类: 遗漏0-10=热, 11-18=温, ≥19=冷 (原书 p.075)"""
    if omission <= 10:
        return 'hot'
    elif omission <= 18:
        return 'warm'
    return 'cold'


# ═══════════════════════════════════════════════════════════════════════════
# 热温冷动态选择 — 7条规则 (原书第7章案例)
# ═══════════════════════════════════════════════════════════════════════════

def _select_by_hwc(omissions_for_pair):
    """原书热温冷选择策略.

    返回值: (selected_ratios, report_dict)
    """
    hot, warm, cold = {}, {}, {}
    hot_sum, warm_sum, cold_sum = 0, 0, 0

    for ratio, omission in omissions_for_pair.items():
        cls = _classify(omission)
        if cls == 'hot':
            hot[ratio] = omission
            hot_sum += omission
        elif cls == 'warm':
            warm[ratio] = omission
            warm_sum += omission
        else:
            cold[ratio] = omission
            cold_sum += omission

    n_hot, n_warm, n_cold = len(hot), len(warm), len(cold)
    warm_cold_sum = warm_sum + cold_sum
    selected = set()
    reason = ''

    # 规则1-7: each sets selected and reason, single return at end
    if n_cold >= 1 and cold_sum >= 45:
        selected = set(cold.keys())
        if len(selected) < 2:
            selected.update(set(hot.keys()))
        reason = f'大冷必选(cold_sum={cold_sum})'
    elif warm_cold_sum >= 80 and hot_sum <= 15 and n_cold >= 1:
        selected = set(cold.keys())
        if len(selected) < 2:
            selected.update(set(hot.keys()))
        reason = f'打破格局(warm_cold={warm_cold_sum},hot={hot_sum})'
    elif n_hot >= 2 and n_warm >= 1 and hot_sum >= 20 and warm_sum >= 20 and abs(hot_sum - warm_sum) <= 5:
        selected = set(warm.keys())
        if len(selected) < 2:
            selected.update(set(hot.keys()))
        reason = f'热温转换(hot={hot_sum},warm={warm_sum})'
    elif n_warm == 0 and n_cold <= 1:
        reason = '跳过(温为0,不确定)'
    elif n_warm <= 1 and n_cold == 0:
        reason = '跳过(无冷,温不够)'
    elif n_cold >= 1 and cold_sum < 30 and n_warm >= 1:
        selected = set(hot.keys()) | set(warm.keys())
        reason = f'冷不够冷(cold={cold_sum}),保留热温'
    elif warm_cold_sum < 40:
        selected = set(hot.keys())
        reason = f'标准选择(只选热,warm_cold={warm_cold_sum})'
    else:
        selected = set(hot.keys())
        if not selected and warm:
            selected = set(warm.keys())
        reason = '默认选热'

    return selected, {'hot': list(hot.keys()), 'warm': list(warm.keys()),
                      'cold': list(cold.keys()), 'reason': reason,
                      'hot_sum': hot_sum, 'warm_sum': warm_sum, 'cold_sum': cold_sum}


# ═══════════════════════════════════════════════════════════════════════════
# 规律检测器 (原书第5章)
# ═══════════════════════════════════════════════════════════════════════════

def _detect_patterns(seq):
    """对值序列应用全部规律检测器 (原书第5章10大规律), 返回预测的值集合."""
    if len(seq) < 2:
        return set()
    predicted = set()
    last = seq[-1]
    last2 = seq[-2] if len(seq) >= 2 else last

    # N带一: 连续N个相同后一个不同 → 预测延续 (原书 p.075)
    for n in (2, 3):
        if len(seq) >= n + 1:
            seg = seq[-n - 1:]
            maj = max(set(seg[:-1]), key=seg[:-1].count)
            if seg[:-1].count(maj) == n and seg[-1] != maj:
                predicted.add(maj)

    # 前后呼应: 0-x-x-0 → 预测中间值 (原书 p.076)
    for end in range(max(3, len(seq) - 4), len(seq)):
        if seq[end] == seq[end - 3]:
            predicted.update(set(seq[end - 2:end]))

    # 旺者恒旺: 10期内高频值 (原书 p.076: 10期窗口检测高频)
    # [工程] 40%阈值: 10期中出现≥4次视为"旺"
    window = seq[-10:]
    counts = {v: window.count(v) for v in set(window)}
    if counts:
        mx = max(counts.values())
        if mx >= len(window) * 0.4:
            for v, c in counts.items():
                if c == mx:
                    predicted.add(v)

    # 打破局: 重复结构被破坏后新方向 (原书 p.076)
    if len(seq) >= 3 and seq[-2] == seq[-3] and last != seq[-2]:
        predicted.add(last)

    # 对补数: 连续交替 a-b-a-b → 预测回到pre_prev (原书 p.076)
    if len(seq) >= 4 and seq[-1] != seq[-2] and seq[-2] != seq[-3] and seq[-1] == seq[-3]:
        predicted.add(seq[-2])

    # 顺连开: 0→1→2递增 → 预测接2→0反转 (原书 p.074)
    if len(seq) >= 3 and seq[-3:] == [0, 1, 2]:
        predicted.add(0)  # 反转方向
    elif len(seq) >= 2 and seq[-2:] == [0, 1]:
        predicted.add(2)  # 继续上升
    elif len(seq) >= 2 and seq[-2:] == [1, 2]:
        predicted.add(0)  # 继续上升后反转到0

    # 数全开: 012全出现后 → 预测最近值继续 (原书 p.075)
    # [工程] 5期窗口观察012覆盖
    recent5 = set(seq[-5:]) if len(seq) >= 5 else set(seq)
    if {0, 1, 2}.issubset(recent5):
        predicted.add(last)

    # 对立对子: 211...112对称 → 预测打破方向 (原书 p.076)
    if len(seq) >= 6:
        first3 = tuple(seq[-6:-3])
        last3 = tuple(seq[-3:])
        if first3 == last3[::-1] and first3 != last3:
            predicted.add(last3[0])

    return predicted


# ═══════════════════════════════════════════════════════════════════════════
# 跨位置约束传播 (原书 p.110)
# ═══════════════════════════════════════════════════════════════════════════

def _propagate_constraints(pair_rules):
    """跨位置约束: 相邻位比值共享位置, 互相约束.

    例如 12位选了1:0, 23位2位=0, 那么12位中1:1(2位=1)应排除.
    原书 p.110: "12位选择了1:0和1:1, 23位中2位选择了0路, 可以将12位1:1排除"
    """
    # 简化: 遍历相邻pair的共享位置, 如果后一个pair的路数集合限制了共享位,
    # 则前一个pair中违反该限制的比值被排除
    for i in range(len(PAIRS_A) - 1):
        p1 = PAIRS_A[i]      # e.g. (0,1)
        p2 = PAIRS_A[i + 1]  # e.g. (1,2)
        if p1 not in pair_rules or p2 not in pair_rules:
            continue
        # 共享位置是 p1[1] == p2[0]
        shared_pos = p1[1]
        # p2中该共享位的允许路数
        allowed_routes = {b for (a, b) in pair_rules[p2]}
        if not allowed_routes:
            continue
        # p1中, 排除那些共享位路数不在allowed_routes中的比值
        p1_filtered = {(a, b) for (a, b) in pair_rules[p1] if b in allowed_routes}
        if p1_filtered:
            pair_rules[p1] = p1_filtered

        # 同样: p2中, 排除共享位路数不在p1允许范围的比值
        allowed_shared = {b for (a, b) in pair_rules[p1]}
        if allowed_shared:
            p2_filtered = {(a, b) for (a, b) in pair_rules[p2] if a in allowed_shared}
            if p2_filtered:
                pair_rules[p2] = p2_filtered


# ═══════════════════════════════════════════════════════════════════════════
# 第1-3步: 遗漏值+热温冷+规律+约束 (原书第7章)
# ═══════════════════════════════════════════════════════════════════════════

def _step123_filter(valid_reds, n_combos, data):
    """第1-3步: 遗失值→热温冷7规则→规律窄化→跨位置约束→筛选."""
    omissions = _compute_omissions(data, ALL_PAIRS)
    recent = data[-30:]  # [工程] 30期窗口做遗漏值统计
    pair_rules = {}
    report = {}

    # Phase 1: 仅A轮5组相邻位比值 → 遗漏值+热温冷选择
    # 原书 p.102: B轮C轮在A轮已确定位路数后, 只做热温冷交叉验证, 不产生新的独立约束
    # 原书 p.103: 第三步"本步骤删除空间不多, 所以不做选择"
    for pair in PAIRS_A:
        selected_ratios, cls_report = _select_by_hwc(omissions[pair])

        # 跳过不选 → 该位置不设约束(所有9个比值均可)
        if not selected_ratios:
            report[f"{pair[0]+1}-{pair[1]+1}位"] = cls_report
            continue

        # Phase 2: 规律窄化 (仅窄化热/温条件, 不覆盖冷条件)
        seq = [int(r[0]) for r in
               [f"{_ROUTE[sorted(r[1:7])[pair[0]]]}:{_ROUTE[sorted(r[1:7])[pair[1]]]}"
                for r in recent]]
        predicted_routes = _detect_patterns(seq)

        # 只用旺者恒旺窄化 (原书最可靠的规律, 数值可验证)
        if predicted_routes:
            streak = 1
            for i in range(len(seq)-1, 0, -1):
                if seq[i] == seq[i-1]:
                    streak += 1
                else:
                    break
            if streak >= 3 and seq[-1] in predicted_routes:  # [工程] 连续≥3次视为稳定模式
                predicted_routes = {seq[-1]}
            # 不满足→保持predicted_routes原值(含多种可能)

        if predicted_routes:
            # 保护冷条件: 规律窄化不覆盖冷条件的选择
            cold_ratios = {r for r in selected_ratios
                           if omissions[pair][r] > 18}
            warm_hot_ratios = selected_ratios - cold_ratios

            narrowed = {(int(r[0]), int(r[2])) for r in warm_hot_ratios
                        if int(r[0]) in predicted_routes}
            if narrowed:
                selected_ratios = cold_ratios | {r for r in warm_hot_ratios
                                                  if (int(r[0]), int(r[2])) in narrowed}

        pair_rules[pair] = {(int(r[0]), int(r[2])) for r in selected_ratios}
        cls_report['selected'] = sorted(selected_ratios)
        cls_report['predicted_routes'] = sorted(predicted_routes)
        report[f"{pair[0]+1}-{pair[1]+1}位"] = cls_report

    # Phase 3: 跨位置约束传播 (原书 p.110)
    _propagate_constraints(pair_rules)

    # Phase 4: 过滤
    filtered = []
    for idx in range(n_combos):
        base = idx * 6
        reds = tuple(valid_reds[base:base + 6])
        keep = True
        for pair in pair_rules:
            if pair not in pair_rules or not pair_rules[pair]:
                continue  # 跳过不选的位置
            a, b = _ROUTE[reds[pair[0]]], _ROUTE[reds[pair[1]]]
            if (a, b) not in pair_rules[pair]:
                keep = False
                break
        if keep:
            filtered.extend(reds)

    n = len(filtered) // 6
    return filtered, n, report


# ═══════════════════════════════════════════════════════════════════════════
# 第4-8步: 规律窄化 → 筛选 (原书第7章, p.103-108,129-132)
# ═══════════════════════════════════════════════════════════════════════════

def _step4_col_value(reds, col):
    """第4步高尾: col→该组高尾个数(0/1/2). col:0=12位,1=34位,2=56位,3=25位,4=16位."""
    pairs = [(0, 1), (2, 3), (4, 5), (1, 4), (0, 5)]
    return sum(1 for pos in pairs[col] if reds[pos] % 10 >= 5)


def _step5_col_value(reds, col):
    """第5步位间距奇偶: col→该位间距奇偶(1=奇,2=偶). col:0=12位,1=34位,2=56位."""
    pos = [0, 2, 4][col]
    return 2 - abs(reds[pos + 1] - reds[pos]) % 2


def _step6_col_value(reds, col):
    """第6步大小和值奇偶: col:0=大数和值奇偶, 1=小数和值奇偶."""
    if col == 0:
        return sum(n for n in reds if n >= 17) % 2 + 1
    else:
        return sum(n for n in reds if n <= 16) % 2 + 1


def _step456_filter(pool, n, value_fn, n_cols, col_labels, data, window=10):
    """第4-6步分列分析: 每列独立规律检测 → 合并 → 过滤.

    原书 p.103-108,129-132: 每列独立分析, 规律不明显的跳过.
    window=10: [工程] 用最近10期检测列规律
    """
    recent = data[-window:]
    if len(recent) < 5:
        return pool, n, {}

    col_allowed = []
    report = {}

    for col in range(n_cols):
        # 提取历史值序列
        seq = []
        for row in recent:
            reds = sorted(row[1:7])
            seq.append(value_fn(reds, col))

        # 规律检测: 旺者恒旺 (原书 p.076: 5期窗口, 连续≥3次→预测延续)
        candidates = set()
        if len(seq) >= 3:
            window = seq[-5:] if len(seq) >= 5 else seq  # [原书] p.076: 5期检测窗
            counts = {}
            for v in window:
                counts[v] = counts.get(v, 0) + 1
            # [原书] p.076: 同一值连续出现≥3次→预测延续
            streak = 1
            for i in range(len(seq)-1, 0, -1):
                if seq[i] == seq[i-1]:
                    streak += 1
                else:
                    break
            if streak >= 3:  # [工程] 连续≥3次视为稳定模式
                candidates = {seq[-1]}

        if not candidates:
            report[col_labels[col]] = '跳过(无规律)'
            col_allowed.append(None)  # None = pass all
        else:
            report[col_labels[col]] = f'选{sorted(candidates)}'
            col_allowed.append(candidates)

    # 过滤
    result = []
    for idx in range(n):
        base = idx * 6
        reds = tuple(pool[base:base + 6])
        keep = True
        for col in range(n_cols):
            if col_allowed[col] is None:
                continue
            if value_fn(reds, col) not in col_allowed[col]:
                keep = False
                break
        if keep:
            result.extend(reds)

    new_n = len(result) // 6
    return result, new_n, report


def _step7_value(reds, key):
    """第7步首尾和/差/尾数和012路: key=0→首尾和, 1→首尾差, 2→尾数和."""
    if key == 0:
        return (reds[0] + reds[5]) % 3
    elif key == 1:
        return (reds[5] - reds[0]) % 3
    else:
        return sum(n % 10 for n in reds) % 3


def _step8_value(reds, key):
    """第8步位尾数和012路: key=0→12位, 1→34位, 2→56位."""
    return ((reds[key * 2] % 10) + (reds[key * 2 + 1] % 10)) % 3


def _step78_filter(pool, n, value_fn, data):
    """第7-8步专用: 分列规律检测+大遗漏预排除+合并.

    原书 p.106-108: 每列独立分析, 遗漏>100的先排除, 再规律检测.
    """
    recent = data[-20:]  # 原书第7步用20期窗口 (p.106)
    if len(recent) < 5:
        return pool, n, {}

    col_results = []  # [(col_idx, allowed_values), ...]
    report = {}
    col_names = {0: '首尾和', 1: '首尾差', 2: '尾数和'} if value_fn.__name__ == '_step7_value' else \
                {0: '12位尾和', 1: '34位尾和', 2: '56位尾和'}

    for col in range(3):
        # 提取历史值序列
        seq = []
        for row in recent:
            reds = sorted(row[1:7])
            seq.append(value_fn(reds, col))

        # 遗漏值预排除 (原书 p.106): 遗漏>100的大冷值先排除
        omissions = {}
        for v in (0, 1, 2):
            for offset, val in enumerate(reversed(seq)):
                if val == v:
                    omissions[v] = offset
                    break
            else:
                omissions[v] = float('inf')

        # 排除遗漏>100的值
        candidates = {v for v, om in omissions.items() if om <= 100}

        # 规律检测窄化: 旺者恒旺 (同一值连续出现≥3次→预测延续)
        if candidates and len(seq) >= 3:
            streak = 1
            for i in range(len(seq)-1, 0, -1):
                if seq[i] == seq[i-1]:
                    streak += 1
                else:
                    break
            if streak >= 3:  # [工程] 连续≥3次视为稳定模式
                narrowed = candidates & {seq[-1]}
                if narrowed:
                    candidates = narrowed

        if not candidates:
            candidates = {0, 1, 2}  # 无法判断→全选

        col_results.append(candidates)
        report[col_names[col]] = f'选{sorted(candidates)}(遗漏{ {v:omissions.get(v,999) for v in (0,1,2)} })'

    # 合并: 三列取笛卡尔积
    allowed = set()
    for a in col_results[0]:
        for b in col_results[1]:
            for c in col_results[2]:
                allowed.add(f"{a}{b}{c}")

    # 过滤
    result = []
    for idx in range(n):
        base = idx * 6
        reds = tuple(pool[base:base + 6])
        v0 = value_fn(reds, 0)
        v1 = value_fn(reds, 1)
        v2 = value_fn(reds, 2)
        if f"{v0}{v1}{v2}" in allowed:
            result.extend(reds)

    new_n = len(result) // 6

    # 冲突保护: 如窄化后为0, 回退到全选 (原书逻辑: 后步不与前步冲突)
    if new_n == 0 and len(allowed) < 27:
        result2 = []
        for idx in range(n):
            base = idx * 6
            reds = tuple(pool[base:base + 6])
            result2.extend(reds)
        new_n = len(result2) // 6
        report['conflict_fallback'] = f'窄化冲突,回退全选({n}→{new_n})'
        return result2, new_n, report

    return result, new_n, report


def _manual_filter_step(pool, n, step_conditions, step_key, col_names, value_fn, report):
    """Filter pool by manual conditions for a single step (4-8)."""
    conditions = step_conditions.get(step_key, {})
    active = {col_names[k]: {int(vv) for vv in v} for k, v in conditions.items() if k in col_names}
    if not active:
        return pool, n
    result = []
    for idx in range(n):
        base = idx * 6
        reds = tuple(pool[base:base + 6])
        for col, allowed in active.items():
            if value_fn(reds, col) not in allowed:
                break
        else:
            result.extend(reds)
    pool = result
    n = len(pool) // 6
    report[step_key] = f'{n}'
    return pool, n


def _ensure_pool(data):
    """Ensure valid_reds is built, return (valid_reds, n_combos) or None."""
    import ml.micro_portfolio as mp
    try:
        if mp._valid_reds is None or len(data) != mp._past_count:
            mp._build_pool()
    except Exception:
        mp._build_pool()
    valid_reds = mp._valid_reds
    if valid_reds is None or len(valid_reds) < 6:
        return None
    return valid_reds, len(valid_reds) // 6


def _build_tickets(pool, n):
    """Build tickets with blue ball assignment."""
    from ml.micro_portfolio import _blue_freq_weights, _pick_blue
    blue_weights = _blue_freq_weights()
    tickets = []
    for idx in range(n):
        base = idx * 6
        reds = list(pool[base:base + 6])
        blue = _pick_blue(blue_weights)
        tickets.append({"reds": reds, "blue": blue})
    return tickets


# ═══════════════════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════════════════

def generate_tickets_weier():
    """微尔算法 (严格按原书).

    流程:
      1. 遗漏值 → 热温冷7规则动态选择
      2. 规律检测窄化
      3. 跨位置约束传播
      4. 第1-3步 012路位比值筛选 (原书第7章)
      5. 第4-8步 规律窄化筛选 (高尾/位间距/大小和/首尾和/位尾和)
      6. 蓝球Laplace加权分配
      7. 全量导出
    """
    from server.db import load_draws

    data = load_draws()
    if len(data) < 20:  # [工程] 微尔自动生成最少需要20期数据做遗漏统计
        return {"ok": False, "msg": "数据不足(需≥20期)"}

    # 确保_valid_reds已构建
    pool_result = _ensure_pool(data)
    if pool_result is None:
        return {"ok": False, "msg": "有效池未构建"}
    valid_reds, n_combos = pool_result

    pool_size_exact = f"C(33,6)-h2(93)-h3({len(data)})={n_combos}"
    report = {}

    # ── 第1-3步 ──
    pool, n, step123_report = _step123_filter(valid_reds, n_combos, data)
    report['step1-3'] = step123_report

    # ── 第4步: 高尾 (5组分列分析) ──
    pool, n, rep = _step456_filter(pool, n, _step4_col_value, 5,
                                    {0: '12位', 1: '34位', 2: '56位', 3: '25位', 4: '16位'}, data)
    report['step4'] = rep

    # ── 第5步: 位间距奇偶 (3组分列分析) ──
    pool, n, rep = _step456_filter(pool, n, _step5_col_value, 3,
                                    {0: '12位距', 1: '34位距', 2: '56位距'}, data)
    report['step5'] = rep

    # ── 第6步: 大小和值奇偶 (2组分列分析) ──
    pool, n, rep = _step456_filter(pool, n, _step6_col_value, 2,
                                    {0: '大和值', 1: '小和值'}, data)
    report['step6'] = rep

    # ── 第7步: 首尾和/差/尾数和012路 (分列分析) ──
    pool, n, rep = _step78_filter(pool, n, _step7_value, data)
    report['step7'] = rep

    # ── 第8步: 位尾数和012路 (分列分析) ──
    pool, n, rep = _step78_filter(pool, n, _step8_value, data)
    report['step8'] = rep

    # ── 蓝球 ──
    tickets = _build_tickets(pool, n)

    return {
        "ok": True,
        "algorithm": "Weier-8Step",
        "tickets": tickets,
        "budget": len(tickets),
        "cost_rmb": len(tickets) * TICKET_PRICE,
        "filter_log": {
            "exact_pool_size": pool_size_exact,
            "final_count": len(tickets),
        },
        "conditions": report,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 手动条件过滤 (用户自选条件, 不自动检测)
# ═══════════════════════════════════════════════════════════════════════════

def generate_tickets_weier_manual(step_conditions):
    """按用户手动选择的条件过滤, 不自动检测.

    Args:
        step_conditions: dict, 格式:
          {"step1": {"1-2": ["0:0","1:2"], "2-3": ["0:1"], ...},
           "step4": {"12位": ["1"], "25位": ["0"]},
           "step5": {"12位距": ["2"], ...},
           "step6": {"大和值": ["2"], ...},
           "step7": {"首尾和": ["1"], ...},
           "step8": {"12位尾和": ["0","1"], ...}}
        未指定的步骤/列 = 全量通过
    """
    from server.db import load_draws

    data = load_draws()
    if len(data) < 5:
        return {"ok": False, "msg": "数据不足"}

    pool_result = _ensure_pool(data)
    if pool_result is None:
        return {"ok": False, "msg": "有效池未构建"}
    valid_reds, n_combos = pool_result
    pool = valid_reds
    n = n_combos
    report = {}

    # ── 第1步: 位比值A/B/C轮 ──
    step1 = step_conditions.get("step1", {})
    if step1:
        pair_map = {}
        for label, pair in [("1-2", (0,1)), ("2-3", (1,2)), ("3-4", (2,3)),
                            ("4-5", (3,4)), ("5-6", (4,5)),
                            ("1-3", (0,2)), ("1-4", (0,3)), ("1-5", (0,4)), ("1-6", (0,5)),
                            ("2-4", (1,3)), ("2-5", (1,4)), ("2-6", (1,5)),
                            ("3-5", (2,4)), ("3-6", (2,5))]:
            if label in step1:
                allowed_set = set()
                for r in step1[label]:
                    parts = r.split(":")
                    if len(parts) == 2:
                        allowed_set.add((int(parts[0]), int(parts[1])))
                if allowed_set:
                    pair_map[pair] = allowed_set

        if pair_map:
            result = []
            for idx in range(n):
                base = idx * 6
                reds = tuple(pool[base:base + 6])
                keep = True
                for pair, allowed in pair_map.items():
                    a, b = _ROUTE[reds[pair[0]]], _ROUTE[reds[pair[1]]]
                    if (a, b) not in allowed:
                        keep = False
                        break
                if keep:
                    result.extend(reds)
            pool = result
            n = len(pool) // 6
            report['step1'] = f'{n_combos}→{n}'

    # ── 第4步: 高尾 ──
    pool, n = _manual_filter_step(pool, n, step_conditions, "step4",
        {"12位": 0, "34位": 1, "56位": 2, "25位": 3, "16位": 4}, _step4_col_value, report)

    # ── 第5步: 位间距 ──
    pool, n = _manual_filter_step(pool, n, step_conditions, "step5",
        {"12位距": 0, "34位距": 1, "56位距": 2}, _step5_col_value, report)

    # ── 第6步: 大小和值 ──
    pool, n = _manual_filter_step(pool, n, step_conditions, "step6",
        {"大和值": 0, "小和值": 1}, _step6_col_value, report)

    # ── 第7步: 首尾和/差/尾数和 ──
    pool, n = _manual_filter_step(pool, n, step_conditions, "step7",
        {"首尾和": 0, "首尾差": 1, "尾数和": 2}, _step7_value, report)

    # ── 第8步: 位尾数和 ──
    pool, n = _manual_filter_step(pool, n, step_conditions, "step8",
        {"12位尾和": 0, "34位尾和": 1, "56位尾和": 2}, _step8_value, report)

    # ── 蓝球 ──
    tickets = _build_tickets(pool, n)

    return {
        "ok": True,
        "algorithm": "Weier-Manual",
        "tickets": tickets,
        "budget": len(tickets),
        "cost_rmb": len(tickets) * TICKET_PRICE,
        "filter_log": report,
    }
