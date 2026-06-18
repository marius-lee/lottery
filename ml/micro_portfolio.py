"""有效号码池随机采样 + 运气规则（位置短窗动量）。

硬过滤 (组合数学, 始终生效):
  规则2 等差序列 d≥2
  规则3 历史已开红球

软过滤 (可选, 历史极少出现, 每期动态):
  规则S1 ≥5连号
  规则S4 最大间距≥24
  规则S5 位置从未出现

运气规则 (双入口):
  blend = 池采样 + 位置热度偏置 (生成号码 + 勾选运气规则)
  pure  = 位置加权独立抽号 → 硬过滤 → 去重 (运气开奖按钮)
"""
import random
import itertools
from ml.ssq_constants import TICKET_PRICE, RANDOM_SINGLE_EV

_valid_reds = None
_soft_excluded = None
_param_excluded = None  # P2: 奇偶比/和值过滤独立于soft
_rule_status = {}
_past_count = 0
_last_verified = 0
_sum_min = None  # P2: 历史红球和值下限 (P5)
_sum_max = None  # P2: 历史红球和值上限 (P95)

# ── 运气规则参数 ──

LUCK_WINDOW = 10        # 回溯窗口期数
LUCK_COEFF = 0.5        # 混合偏置强度 (blend模式)
LUCK_BLUE_MIX = 0.06    # 蓝球运气融合比例 (首次使用时自动校准)
_calibrated = False     # 校准标记


def _check_hard(reds):
    """检查硬规则违规(2). 返回违规规则名."""
    s = sorted(reds)
    d = s[1] - s[0]
    if all(s[i] - s[i-1] == d for i in range(2, 6)):
        return ["h2_arithmetic"]
    return []


def _check_soft(reds, param_filter=False):
    """检查软规则违规(S1, S4, S6奇偶比, S7和值范围)."""
    s = sorted(reds)
    v = []
    run = cur = 1
    for i in range(1, 6):
        if s[i] - s[i-1] == 1: cur += 1; run = max(run, cur)
        else: cur = 1
    if run >= 5: v.append("s1_consecutive")
    if max(s[i+1] - s[i] for i in range(5)) >= 24: v.append("s4_max_gap")

    # P2: 基本参数控制 (蒋加林 2001 第七绝招)
    if param_filter:
        odd = sum(1 for n in s if n % 2 == 1)
        if odd <= 1 or odd >= 5:  # 拒绝 0:6, 1:5, 5:1, 6:0
            v.append("s6_odd_even")
        if _sum_min is not None and _sum_max is not None:
            total = sum(s)
            if total < _sum_min or total > _sum_max:
                v.append("s7_sum_range")
    return v


def _verify():
    """验证新增期数, 报告软规则违规 (含 S5 位置)."""
    global _last_verified, _rule_status
    from server.db import load_draws
    data = load_draws()
    new = [r for r in data if r[0] > _last_verified]
    if not new: return
    old_rows = [r for r in data if r[0] <= _last_verified]
    pos_seen = {p: set() for p in range(1, 7)}
    for row in old_rows:
        r = sorted(row[1:7])
        for p in range(1, 7):
            pos_seen[p].add(r[p - 1])
    for row in new:
        for name in _check_soft(row[1:7]):
            _rule_status[name]["violations"].append(row[0])
        r = sorted(row[1:7])
        for p in range(1, 7):
            if r[p - 1] not in pos_seen[p]:
                _rule_status.get("s5_position", {}) \
                    .setdefault("violations", []).append(row[0])
                break
        for p in range(1, 7):
            pos_seen[p].add(r[p - 1])
    _last_verified = data[-1][0]


def _build_pool():
    """枚举 C(33,6), 硬过滤 + 软过滤."""
    global _valid_reds, _soft_excluded, _param_excluded, _rule_status, _past_count, _sum_min, _sum_max
    from server.db import load_draws
    data = load_draws()
    _past_count = len(data)
    past_reds = {tuple(sorted(r[1:7])) for r in data}
    if not _rule_status:
        _rule_status = {
            "h2_arithmetic":  {"type": "hard", "excluded": 0, "violations": []},
            "h3_historical":  {"type": "hard", "excluded": 0, "violations": []},
            "s1_consecutive": {"type": "soft", "excluded": 0, "violations": []},
            "s4_max_gap":     {"type": "soft", "excluded": 0, "violations": []},
            "s5_position":    {"type": "soft", "excluded": 0, "violations": []},
            "s6_odd_even":    {"type": "param", "excluded": 0, "violations": []},
            "s7_sum_range":   {"type": "param", "excluded": 0, "violations": []},
        }
    # P2: 计算历史红球和值 P5/P95 范围
    if _sum_min is None:
        hist_sums = sorted(sum(row[1:7]) for row in data)
        n_hist = len(hist_sums)
        _sum_min = hist_sums[int(n_hist * 0.05)] if n_hist >= 20 else 21
        _sum_max = hist_sums[int(n_hist * 0.95)] if n_hist >= 20 else 183

    _verify()
    pos_seen = {p: set() for p in range(1, 7)}
    for row in data:
        r = sorted(row[1:7])
        for p in range(1, 7): pos_seen[p].add(r[p-1])
    valid = []
    soft = set()
    param = set()
    h2, h3 = 0, 0
    s1, s4, s5, s6, s7 = 0, 0, 0, 0, 0
    for c in itertools.combinations(range(1, 34), 6):
        if _check_hard(c):  h2 += 1; continue
        if c in past_reds:  h3 += 1; continue
        valid.extend(c)
        sv = _check_soft(c, param_filter=True)
        if "s1_consecutive" in sv: s1 += 1; soft.add(c)
        if "s4_max_gap" in sv:     s4 += 1; soft.add(c)
        if "s6_odd_even" in sv:    s6 += 1; param.add(c)
        if "s7_sum_range" in sv:   s7 += 1; param.add(c)
        s = sorted(c)
        for p in range(1, 7):
            if s[p-1] not in pos_seen[p]:
                s5 += 1; soft.add(c)
                break
    _valid_reds = valid
    _soft_excluded = soft
    _param_excluded = param
    _rule_status["h2_arithmetic"]["excluded"] = h2
    _rule_status["h3_historical"]["excluded"] = h3
    _rule_status["s1_consecutive"]["excluded"] = s1
    _rule_status["s4_max_gap"]["excluded"] = s4
    _rule_status["s5_position"]["excluded"] = s5
    _rule_status["s6_odd_even"]["excluded"] = s6
    _rule_status["s7_sum_range"]["excluded"] = s7


# ────────────────────────────────────────────────────────
# 蓝球频率 + 运气融合
# ────────────────────────────────────────────────────────

def _blue_freq_weights():
    """蓝球频率权重，带 Laplace 平滑。"""
    from server.db import load_draws
    data = load_draws()
    weights = [1.0] * 16
    for row in data:
        weights[row[7] - 1] += 1.0
    total = sum(weights)
    return [w / total for w in weights]


def _five_period_boost():
    """五期断蓝法 (刘大军, 2011): 近5期蓝球均值±4范围的蓝球×1.5权重.

    原理: 5期窗口捕获短期蓝球动量, ±4覆盖约一半蓝球空间。
    来源: 《双色球蓝球中奖绝技》第六章, 公式一."""
    from server.db import load_draws
    data = load_draws()
    if len(data) < 5:
        return [1.0] * 16
    recent = [r[7] for r in data[-5:]]
    avg = round(sum(recent) / 5)
    boost = [1.0] * 16
    for n in range(max(1, avg - 4), min(16, avg + 4) + 1):
        boost[n - 1] = 1.5
    return boost


def _calibrate_luck_blue_mix():
    """滑动窗口回测确定最优蓝球运气融合比例。"""
    global LUCK_BLUE_MIX, _calibrated
    from server.db import load_draws
    data = load_draws()
    window = LUCK_WINDOW
    if len(data) < window + 5:
        return
    best_mix = LUCK_BLUE_MIX
    best_hits = -1
    for mix_pct in range(0, 31, 2):
        mix = mix_pct / 100.0
        hits = 0
        total = 0
        for i in range(window, len(data) - 1):
            actual = data[i][7]
            laplace = [1.0] * 16
            for row in data[:i]:
                laplace[row[7] - 1] += 1.0
            total_l = sum(laplace)
            laplace_w = [w / total_l for w in laplace]
            counts = [0] * 16
            for row in data[i - window:i]:
                counts[row[7] - 1] += 1
            max_b = max(counts) or 1
            luck_w = [c / max_b for c in counts]
            blended = [laplace_w[j] * (1.0 - mix) + luck_w[j] * mix for j in range(16)]
            pred = max(range(16), key=lambda x: blended[x]) + 1
            if pred == actual:
                hits += 1
            total += 1
        if hits > best_hits:
            best_hits = hits
            best_mix = mix
    LUCK_BLUE_MIX = best_mix
    _calibrated = True


def _compute_luck_position_weights(window=None):
    """计算近 N 期各位置号码出现频率。

    返回:
      red_weights: list[6][33] — 6个位置 × 33个号码的归一化权重 (0~1)
      blue_weights: list[16] — 蓝球归一化权重 (0~1)
    """
    from server.db import load_draws
    data = load_draws()
    window = window or LUCK_WINDOW
    recent = data[-window:] if len(data) >= window else data

    red_counts = [[0] * 33 for _ in range(6)]
    for row in recent:
        s = sorted(row[1:7])
        for pos in range(6):
            red_counts[pos][s[pos] - 1] += 1

    blue_counts = [0] * 16
    for row in recent:
        blue_counts[row[7] - 1] += 1

    red_weights = []
    for pos in range(6):
        mx = max(red_counts[pos]) or 1
        red_weights.append([c / mx for c in red_counts[pos]])

    max_b = max(blue_counts) or 1
    blue_weights = [c / max_b for c in blue_counts]

    return red_weights, blue_weights


def _luck_blended_blue_weights(freq_weights, luck_blue, mix=None):
    """融合 Laplace 频率权重 + 运气权重。"""
    mix = LUCK_BLUE_MIX if mix is None else mix
    n = min(len(freq_weights), len(luck_blue))
    return [freq_weights[i] * (1.0 - mix) + luck_blue[i] * mix for i in range(n)]


def _weighted_choice(weights, candidates, rng=random):
    """从 candidates 中按权重随机抽一个。"""
    if not candidates:
        return None
    w = [weights[c - 1] if c - 1 < len(weights) else 0 for c in candidates]
    total = sum(w)
    if total <= 0:
        return rng.choice(candidates)
    r = rng.random() * total
    cum = 0.0
    for i, val in enumerate(w):
        cum += val
        if r < cum:
            return candidates[i]
    return candidates[-1]


def _pick_unique_blue(weights, used_blues):
    """从可用篮号中按权重抽取，保证不与 used_blues 重复。"""
    available = [i + 1 for i in range(16) if (i + 1) not in used_blues]
    if not available:
        return _weighted_choice(weights, list(range(1, 17)))
    avail_w = [weights[i] for i in range(16) if (i + 1) in available]
    total = sum(avail_w)
    if total <= 0:
        return random.choice(available)
    r = random.random() * total
    cum = 0.0
    for i, w in enumerate(avail_w):
        cum += w
        if r < cum:
            return available[i]
    return available[-1]


# ────────────────────────────────────────────────────────
# 纯运气模式: 位置加权抽号
# ────────────────────────────────────────────────────────

def _draw_luck_reds(red_weights):
    """按6个位置各自的频率权重, 逐个抽取红球, 保证升序。

    位置1 ~ 位置6 各有独立的频率分布。
    每个位置的上限受前一个位置约束, 保证 sorted 升序。
    返回 6 个升序整数, 或 None (无法完成).
    """
    reds = []
    for pos in range(6):
        candidates = [n for n in range(1, 34)
                      if (not reds or n > reds[-1])
                      and red_weights[pos][n - 1] > 0]
        pick = _weighted_choice(red_weights[pos], candidates)
        if pick is None:
            return None
        reds.append(pick)
    return reds


def _generate_luck_tickets(n=3, max_overlap=None, five_period=False):
    """纯运气模式: 位置加权抽取 → 硬过滤 → 去重 → 蓝球.

    不依赖 _valid_reds 池, 不依赖软过滤.
    每次独立按位置频率加权抽取, 硬过滤校验, 跨注去重.
    """
    if not _calibrated:
        _calibrate_luck_blue_mix()

    red_weights, blue_luck = _compute_luck_position_weights()
    freq_weights = _blue_freq_weights()
    if five_period:
        fpb = _five_period_boost()
        freq_weights = [freq_weights[i] * fpb[i] for i in range(16)]
    blue_weights = _luck_blended_blue_weights(freq_weights, blue_luck)

    tickets = []
    used_reds = set()
    used_blues = set()

    for _ in range(n):
        found = False
        for _ in range(500):
            reds = _draw_luck_reds(red_weights)
            if reds is None:
                continue
            # 硬过滤
            if _check_hard(reds):
                continue
            tr = tuple(reds)
            if tr in used_reds:
                continue
            # Tier 1: 注间分散
            if max_overlap is not None and tickets:
                if any(len(set(tr) & set(t["reds"])) > max_overlap
                       for t in tickets):
                    continue
            used_reds.add(tr)
            blue = _pick_unique_blue(blue_weights, used_blues)
            used_blues.add(blue)
            tickets.append({"reds": reds, "blue": blue})
            found = True
            break
        if not found:
            # 降级: 纯随机 + 硬过滤
            for _ in range(500):
                c = tuple(sorted(random.sample(range(1, 34), 6)))
                if _check_hard(c):
                    continue
                if c in used_reds:
                    continue
                used_reds.add(c)
                blue = _pick_unique_blue(blue_weights, used_blues)
                used_blues.add(blue)
                tickets.append({"reds": list(c), "blue": blue})
                found = True
                break
            if not found:
                blue = _pick_unique_blue(blue_weights, used_blues)
                used_blues.add(blue)
                tickets.append({"reds": [1, 2, 3, 4, 5, 6], "blue": blue})

    return {
        "ok": True,
        "algorithm": "Luck-Position",
        "tickets": tickets, "budget": n,
        "cost_rmb": n * TICKET_PRICE,
        "pool_size": None,
        "pool_valid_reds": None,
        "soft_filter": False, "soft_excluded": 0,
        "luck_mode": "pure",
        "luck_window": LUCK_WINDOW,
        "rule_status": {},
        "ev_estimate": {"ev_per_draw": round(RANDOM_SINGLE_EV * n, 2),
                        "cost_per_draw": n * TICKET_PRICE},
    }


# ────────────────────────────────────────────────────────
# 故障降级
# ────────────────────────────────────────────────────────

def _generate_fallback_tickets(n, luck_mode='off', max_overlap=None, five_period=False):
    """故障降级: 纯随机, 无硬/软过滤. 红球/蓝球注间去重. """
    from ml.ssq_constants import TICKET_PRICE, RANDOM_SINGLE_EV
    blue_weights = _blue_freq_weights()
    if five_period:
        fpb = _five_period_boost()
        blue_weights = [blue_weights[i] * fpb[i] for i in range(16)]

    red_weights = None
    if luck_mode in ('blend', 'pure'):
        if not _calibrated:
            _calibrate_luck_blue_mix()
        _, blue_luck = _compute_luck_position_weights()
        blue_weights = _luck_blended_blue_weights(blue_weights, blue_luck)

    tickets = []
    used_reds = set()
    used_blues = set()
    for _ in range(n):
        c = None
        for _ in range(500):
            c = tuple(sorted(random.sample(range(1, 34), 6)))
            if c in used_reds:
                continue
            # Tier 1: 注间分散
            if max_overlap is not None and tickets:
                if any(len(set(c) & set(t["reds"])) > max_overlap
                       for t in tickets):
                    continue
            used_reds.add(c)
            break
        else:
            c = (1, 2, 3, 4, 5, 6)
        blue = _pick_unique_blue(blue_weights, used_blues)
        used_blues.add(blue)
        tickets.append({"reds": list(c), "blue": blue})
    return {
        "ok": True,
        "algorithm": "Fallback-Random",
        "tickets": tickets, "budget": n,
        "cost_rmb": n * TICKET_PRICE,
        "pool_size": None, "pool_valid_reds": None,
        "soft_filter": False, "soft_excluded": 0,
        "luck_mode": luck_mode,
        "rule_status": {},
        "ev_estimate": {"ev_per_draw": round(RANDOM_SINGLE_EV * n, 2),
                        "cost_per_draw": n * TICKET_PRICE},
    }


# ────────────────────────────────────────────────────────
# Tier 2: 贪心多样性选注
# ────────────────────────────────────────────────────────

def _jaccard_distance(a, b):
    """Jaccard距离: 1 - |a∩b| / |a∪b|.
    对6元素集合: |a∪b| = 12 - |a∩b|, 范围6-12.
    返回 1.0(完全不相交) 到 0.0(完全相同)."""
    inter = len(set(a) & set(b))
    return 1.0 - inter / (12.0 - inter)


def _build_candidate_pool(pool_size, valid_reds, n_combos, exclude, used_reds, rng=random):
    """从_valid_reds随机采样pool_size个候选组合.
    返回 [(idx, reds_tuple), ...], 排除已过滤和已使用的组合."""
    candidates = []
    seen = set()
    attempts = 0
    max_attempts = max(pool_size * 10, 5000)
    while len(candidates) < pool_size and attempts < max_attempts:
        idx = rng.randrange(n_combos)
        if idx in seen:
            attempts += 1; continue
        seen.add(idx)
        base = idx * 6
        reds = tuple(valid_reds[base:base + 6])
        if reds in exclude or reds in used_reds:
            attempts += 1; continue
        candidates.append((idx, reds))
        attempts += 1
    return candidates


def _greedy_diverse_tickets(n, valid_reds, n_combos, exclude=None,
                             pool_size=1000, blue_weights=None,
                             used_blues=None, rng=random):
    """贪心最大化最小Jaccard距离选注.
    返回 (tickets, used_idx, used_reds, used_blues), 不足时返回None."""
    if exclude is None:
        exclude = set()
    if blue_weights is None:
        blue_weights = _blue_freq_weights()
    if used_blues is None:
        used_blues = set()

    candidates = _build_candidate_pool(pool_size, valid_reds, n_combos,
                                       exclude, set(), rng)
    if len(candidates) < n:
        return None

    # 随机选第一个
    first = rng.choice(candidates)
    selected = [first]
    remaining = [c for c in candidates if c[0] != first[0]]

    # 贪心: 每步选min Jaccard距离最大的候选
    for _ in range(1, min(n, len(remaining) + 1)):
        best_candidate = None
        best_min_dist = -1.0
        for c in remaining:
            min_dist = min(_jaccard_distance(c[1], s[1]) for s in selected)
            if min_dist > best_min_dist:
                best_min_dist = min_dist
                best_candidate = c
        if best_candidate is None:
            break
        selected.append(best_candidate)
        remaining.remove(best_candidate)

    used_idx = set()
    used_reds = set()
    tickets = []
    for idx, reds in selected:
        used_idx.add(idx)
        used_reds.add(reds)
        blue = _pick_unique_blue(blue_weights, used_blues)
        used_blues.add(blue)
        tickets.append({"reds": list(reds), "blue": blue})

    return tickets, used_idx, used_reds, used_blues


# ────────────────────────────────────────────────────────
# P0: 百万军中选大将 (蒋加林, 2001) — 回测排名选注
# ────────────────────────────────────────────────────────

def _backtest_rank_tickets(n, valid_reds, n_combos, window=50, min_hits=3, sample_size=10000, rng=random):
    """滑动窗口回测: 从有效池采样, 选历史命中频率最高的N注.

    算法: 蒋加林《抓住500万》第二绝招, 2001.
    采样 sample_size 个组合, 对近 window 期逐一兑奖,
    统计命中≥min_hits个红球的期数, 取top-N.
    """
    from server.db import load_draws
    data = load_draws()
    if len(data) < window:
        window = len(data)
    recent = data[-window:]
    period_reds = [{r[1], r[2], r[3], r[4], r[5], r[6]} for r in recent]

    actual_sample = min(sample_size, n_combos)
    scored = []
    seen = set()
    attempts = 0
    while len(scored) < actual_sample and attempts < actual_sample * 10:
        idx = rng.randrange(n_combos)
        if idx in seen:
            attempts += 1; continue
        seen.add(idx)
        base = idx * 6
        reds = set(valid_reds[base:base + 6])
        hit_periods = sum(1 for pr in period_reds if len(reds & pr) >= min_hits)
        scored.append((idx, hit_periods, tuple(valid_reds[base:base + 6])))
        attempts += 1

    scored.sort(key=lambda x: -x[1])
    selected = scored[:n]
    return [(idx, reds, hits) for idx, hits, reds in selected]


# ────────────────────────────────────────────────────────
# 规则状态
# ────────────────────────────────────────────────────────

def rule_status():
    if _valid_reds is None:
        _build_pool()
    return _rule_status


# ────────────────────────────────────────────────────────
# 主入口: 生成号码
# ────────────────────────────────────────────────────────

def generate_tickets(n=3, soft=False, luck_mode='off', max_overlap=None,
                     diversity_mode=None, five_period=False, backtest_rank=False,
                     param_filter=False, bundle_a=None, bundle_b=None):
    """生成号码主入口.

    Args:
        n: 注数 (1-3)
        soft: 是否启用软过滤 (位置软过滤)
        luck_mode:
          'off'   → 纯池采样 (原「生成号码」, 不勾选运气规则)
          'blend' → 池采样 + 位置热度偏置 (勾选运气规则 + 生成号码)
          'pure'  → 位置加权独立抽号 (「运气开奖」按钮)
        max_overlap: 注间最大共享红球数, None=不限制. 0=完全不相交, 2=默认推荐
        diversity_mode: None=随机采样, 'greedy'=贪心max-min Jaccard
        five_period: 五期断蓝法加权 (刘大军, 2011)

    Returns:
        dict with tickets, algorithm, filter info, ev_estimate.
    """
    # ── pure 模式走独立路径 ──
    if luck_mode == 'pure':
        return _generate_luck_tickets(n=n, max_overlap=max_overlap, five_period=five_period)

    # ── off / blend 共用池采样 ──
    global _valid_reds, _soft_excluded, _past_count
    from server.db import load_draws
    try:
        if len(load_draws()) != _past_count:
            _build_pool()
    except Exception:
        _valid_reds = None
        _soft_excluded = None

    if _valid_reds is None:
        return _generate_fallback_tickets(n, luck_mode=luck_mode, max_overlap=max_overlap, five_period=five_period)

    exclude = _soft_excluded if soft else set()
    if param_filter and _param_excluded is not None:
        exclude = exclude | _param_excluded
    n_combos = len(_valid_reds) // 6
    if n_combos * 6 != len(_valid_reds) or n_combos == 0:
        return _generate_fallback_tickets(n, luck_mode=luck_mode, max_overlap=max_overlap, five_period=five_period)

    # 蓝球: Laplace平滑频率 (可选五期断蓝加权)
    blue_weights = _blue_freq_weights()
    if five_period:
        fpb = _five_period_boost()
        blue_weights = [blue_weights[i] * fpb[i] for i in range(16)]
        total = sum(blue_weights)
        blue_weights = [w / total for w in blue_weights]  # 重新归一化

    # blend 模式: 位置热度权重 + 蓝球融合
    red_pos_weights = None
    if luck_mode == 'blend':
        if not _calibrated:
            _calibrate_luck_blue_mix()
        red_pos_weights, blue_luck = _compute_luck_position_weights()
        blue_weights = _luck_blended_blue_weights(blue_weights, blue_luck)

    used_idx = set()
    used_reds = set()
    used_blues = set()
    tickets = []
    n_original = n  # 保存原始注数用于返回dict

    # Tier 2: 贪心多样性选注 — 先尝试从候选池贪心选, 不足则走随机采样
    if diversity_mode == 'greedy':
        greedy = _greedy_diverse_tickets(
            n, _valid_reds, n_combos, exclude,
            pool_size=1000, blue_weights=blue_weights,
            used_blues=used_blues
        )
        if greedy is not None:
            tickets, used_idx, used_reds, used_blues = greedy
            if len(tickets) >= n_original:
                n = n_original
                pool_size = (n_combos - len(exclude)) * 16
                algo = "Pool-Sampling+Greedy"
                if soft: algo += "+Soft"
                if luck_mode == 'blend': algo += "+Luck"
                return {
                    "ok": True, "algorithm": algo,
                    "tickets": tickets, "budget": n,
                    "cost_rmb": n * TICKET_PRICE,
                    "pool_size": pool_size,
                    "pool_valid_reds": n_combos - len(exclude),
                    "soft_filter": soft, "soft_excluded": len(exclude),
                    "luck_mode": luck_mode,
                    "luck_window": LUCK_WINDOW if luck_mode != 'off' else None,
                    "rule_status": _rule_status,
                    "ev_estimate": {"ev_per_draw": round(RANDOM_SINGLE_EV * n, 2),
                                    "cost_per_draw": n * TICKET_PRICE},
                }
            # 贪心未产足 → 剩余 n 走随机采样
            n = n_original - len(tickets)
        else:
            n = n_original

    # Tier P0: 百万军中选大将 — 回测排名选注
    elif backtest_rank:
        ranked = _backtest_rank_tickets(n_original, _valid_reds, n_combos)
        if ranked and len(ranked) >= n_original:
            for idx, reds, hits in ranked[:n_original]:
                used_idx.add(idx)
                used_reds.add(reds)
                blue = _pick_unique_blue(blue_weights, used_blues)
                used_blues.add(blue)
                tickets.append({"reds": list(reds), "blue": blue})
            n = n_original
            pool_size = (n_combos - len(exclude)) * 16
            algo = "Pool-Sampling+Backtest"
            if soft: algo += "+Soft"
            if luck_mode == 'blend': algo += "+Luck"
            return {
                "ok": True, "algorithm": algo,
                "tickets": tickets, "budget": n,
                "cost_rmb": n * TICKET_PRICE,
                "pool_size": pool_size,
                "pool_valid_reds": n_combos - len(exclude),
                "soft_filter": soft, "soft_excluded": len(exclude),
                "luck_mode": luck_mode,
                "luck_window": LUCK_WINDOW if luck_mode != 'off' else None,
                "rule_status": _rule_status,
                "ev_estimate": {"ev_per_draw": round(RANDOM_SINGLE_EV * n, 2),
                                "cost_per_draw": n * TICKET_PRICE},
            }
        else:
            n = n_original
    else:
        n = n_original

    for _ in range(n):
        for _ in range(500):
            idx = random.randrange(n_combos)
            if idx in used_idx:
                continue
            base = idx * 6
            assert base + 6 <= len(_valid_reds), \
                f"idx={idx}, base={base}, len={len(_valid_reds)}, 越界"
            reds = tuple(_valid_reds[base:base + 6])
            if reds in exclude:
                continue
            if reds in used_reds:
                continue

            # Tier 1: 注间分散 — 候选注与已选注共享红球数 ≤ max_overlap
            if max_overlap is not None and tickets:
                if any(len(set(reds) & set(t["reds"])) > max_overlap
                       for t in tickets):
                    continue

            # blend 模式: 位置热度偏置
            if luck_mode == 'blend':
                # 计算每个号码在其排序位置上的热度评分
                score_sum = 0.0
                for pos, num in enumerate(sorted(reds)):
                    score_sum += red_pos_weights[pos][num - 1]
                score = score_sum / 6.0
                # 接受概率: 全热号(1.0)始终接受, 全冷号(0.0)接受率 67%
                if random.random() > (1.0 + LUCK_COEFF * score) / (1.0 + LUCK_COEFF):
                    continue

            used_idx.add(idx)
            used_reds.add(reds)
            blue = _pick_unique_blue(blue_weights, used_blues)
            used_blues.add(blue)
            tickets.append({"reds": list(reds), "blue": blue})
            break
        else:
            for _ in range(500):
                c = tuple(sorted(random.sample(range(1, 34), 6)))
                if c in used_reds:
                    continue
                used_reds.add(c)
                blue = _pick_unique_blue(blue_weights, used_blues)
                used_blues.add(blue)
                tickets.append({"reds": list(c), "blue": blue})
                break
            else:
                blue = _pick_unique_blue(blue_weights, used_blues)
                used_blues.add(blue)
                tickets.append({"reds": [1, 2, 3, 4, 5, 6], "blue": blue})

    n = n_original  # 恢复原始注数 (贪心模式可能修改了n)

    # P1: 捆绑投注 — 确保至少一注包含bundle_a和bundle_b
    bundle_applied = False
    if bundle_a is not None and bundle_b is not None and tickets:
        bundle_set = {bundle_a, bundle_b}
        if not any(bundle_set.issubset(set(t["reds"])) for t in tickets):
            # 删除最后一注, 替换为含捆绑对的组合
            last = tickets.pop()
            used_reds.discard(tuple(last["reds"]))
            for _ in range(500):
                idx = random.randrange(n_combos)
                base = idx * 6
                reds = tuple(_valid_reds[base:base + 6])
                if bundle_set.issubset(set(reds)) and reds not in used_reds:
                    used_reds.add(reds)
                    tickets.append({"reds": list(reds), "blue": last["blue"]})
                    bundle_applied = True
                    break
            if not bundle_applied:
                # 降级: 从全空间随机找含bundle的组合
                for _ in range(2000):
                    c = tuple(sorted(random.sample(range(1, 34), 6)))
                    if bundle_set.issubset(set(c)) and c not in used_reds:
                        used_reds.add(c)
                        tickets.append({"reds": list(c), "blue": last["blue"]})
                        bundle_applied = True
                        break
            if not bundle_applied:
                tickets.append(last)  # 实在找不到, 放回原注

    pool_size = (n_combos - len(exclude)) * 16
    algo = "Pool-Sampling"
    if bundle_applied: algo += "+Bundle"
    if soft: algo += "+Soft"
    if luck_mode == 'blend':
        algo += "+Luck"
    return {
        "ok": True,
        "algorithm": algo,
        "tickets": tickets, "budget": n,
        "cost_rmb": n * TICKET_PRICE,
        "pool_size": pool_size,
        "pool_valid_reds": n_combos - len(exclude),
        "soft_filter": soft, "soft_excluded": len(exclude),
        "luck_mode": luck_mode,
        "luck_window": LUCK_WINDOW if luck_mode != 'off' else None,
        "rule_status": _rule_status,
        "ev_estimate": {"ev_per_draw": round(RANDOM_SINGLE_EV * n, 2),
                        "cost_per_draw": n * TICKET_PRICE},
    }


# ═══════════════════════════════════════════════════════════════════════════
# Tier 3: 覆盖设计生成 — Steiner t-wise + 蓝球分配
# ═══════════════════════════════════════════════════════════════════════════

def generate_tickets_covering(n=6, hot_numbers=None, t=4, max_overlap=None, five_period=False):
    """覆盖设计票生成: 用SA引擎优化红球覆盖 + Laplace蓝球分配.

    Args:
        n: 目标注数
        hot_numbers: 热号列表 [n1, n2, ...], len≥6
        t: t-wise 覆盖强度 (默认4)
        max_overlap: 注间最大共享红球数, None=不限制
        five_period: 五期断蓝法加权 (刘大军, 2011)

    Returns:
        dict with tickets(含reds+blue), covering元数据(v, t, coverage_pct, guarantee)
    """
    from ml.covering_design import build_covering_tickets
    from ml.ssq_constants import TICKET_PRICE, RANDOM_SINGLE_EV

    if hot_numbers is None or len(hot_numbers) < 6:
        return {"ok": False, "msg": "热号数量不足（需要 ≥6）"}

    cover = build_covering_tickets(hot_numbers, t=t, target_tickets=n)
    if not cover["ok"]:
        return {"ok": False, "msg": "覆盖设计失败: " + cover.get("msg", "生成错误")}

    raw = cover["tickets"]  # List[List[int]], 无蓝球

    # max_overlap 过滤
    if max_overlap is not None and len(raw) > 1:
        filtered = [raw[0]]
        for r in raw[1:]:
            if not any(len(set(r) & set(f)) > max_overlap for f in filtered):
                filtered.append(r)
        raw = filtered

    raw = raw[:n]

    # 蓝球分配 (Laplace平滑频率)
    blue_weights = _blue_freq_weights()
    if five_period:
        fpb = _five_period_boost()
        blue_weights = [blue_weights[i] * fpb[i] for i in range(16)]
    used_blues = set()
    tickets = []
    for r in raw:
        blue = _pick_unique_blue(blue_weights, used_blues)
        used_blues.add(blue)
        tickets.append({"reds": r, "blue": blue})

    return {
        "ok": True,
        "algorithm": f"Covering-Design(v={cover['v']},t={t})",
        "tickets": tickets,
        "budget": len(tickets),
        "cost_rmb": len(tickets) * TICKET_PRICE,
        "pool_size": None,
        "pool_valid_reds": None,
        "soft_filter": False,
        "soft_excluded": 0,
        "luck_mode": "off",
        "rule_status": {},
        "covering": {
            "hot_numbers": hot_numbers,
            "v": cover["v"],
            "t": t,
            "estimated_coverage_pct": cover.get("estimated_coverage_pct", 0),
            "guarantee": cover.get("guarantee", ""),
        },
        "ev_estimate": {
            "ev_per_draw": round(RANDOM_SINGLE_EV * len(tickets), 2),
            "cost_per_draw": len(tickets) * TICKET_PRICE,
        },
    }
