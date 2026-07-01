"""有效号码池随机采样 + 近期偏差加权出号。

唯一算法: 近100期二项检验检测偏热号码 → best-of-20加权池采样。

硬过滤 (始终生效): 等差序列、历史已开红球
软过滤 (可选):   连号、最大间距、位置、奇偶比、和值
"""
import itertools
import pickle
import random
from ml.ssq_constants import TICKET_PRICE


# ═══ 模块级池缓存 ═══

class _State:
    """池缓存. valid_reds 是 C(33,6) 扁平列表, 每6个一组."""
    __slots__ = ('valid_reds', 'soft_excluded', 'param_excluded',
                 'rule_status', 'past_count',
                 'sum_min', 'sum_max')
    def __init__(self):
        self.valid_reds = None
        self.soft_excluded = None
        self.param_excluded = None
        self.rule_status = {}
        self.past_count = 0
        self.sum_min = None
        self.sum_max = None


_state = _State()

# Pickle 缓存: 避免每次启动枚举 1.1M 组合
def _pool_cache_path():
    from pathlib import Path
    from server.db import CACHE_DIR
    return CACHE_DIR / "pool.pkl"


# ═══ 过滤规则 ═══

def _check_hard(reds):
    s = sorted(reds)
    d = s[1] - s[0]
    if all(s[i] - s[i-1] == d for i in range(2, 6)):
        return ["h2_arithmetic"]
    return []


def _check_soft(reds, sum_min=None, sum_max=None):
    """只在 _build_pool 中调用, sum_min/max 由调用方传入避免读 _state."""
    s = sorted(reds)
    v = []
    run = cur = 1
    for i in range(1, 6):
        if s[i] - s[i-1] == 1:
            cur += 1; run = max(run, cur)
        else:
            cur = 1
    if run >= 5:
        v.append("s1_consecutive")
    if max(s[i+1] - s[i] for i in range(5)) >= 24:
        v.append("s4_max_gap")
    odd = sum(1 for n in s if n % 2 == 1)
    if odd <= 1 or odd >= 5:
        v.append("s6_odd_even")
    if sum_min is not None and sum_max is not None:
        total = sum(s)
        if total < sum_min or total > sum_max:
            v.append("s7_sum_range")
    return v


# ═══ 池构建 ═══

def _build_pool():
    """枚举 C(33,6) 并过滤. 结果缓存到 pickle."""
    from server.db import load_draws

    data = load_draws()
    _state.past_count = len(data)

    # 尝试读缓存
    cache_path = _pool_cache_path()
    if cache_path.exists():
        try:
            with open(cache_path, 'rb') as f:
                cached = pickle.load(f)
            if cached.get('past_count') == _state.past_count:
                _state.valid_reds = cached['valid_reds']
                _state.soft_excluded = cached['soft_excluded']
                _state.param_excluded = cached['param_excluded']
                _state.rule_status = cached['rule_status']
                return
        except Exception:
            pass

    # 全量枚举
    past_reds = {tuple(sorted(r[1:7])) for r in data}
    hist_sums = sorted(sum(r[1:7]) for r in data)
    n_hist = len(hist_sums)
    sum_min = hist_sums[int(n_hist * 0.05)] if n_hist >= 20 else 21
    sum_max = hist_sums[int(n_hist * 0.95)] if n_hist >= 20 else 183
    _state.sum_min = sum_min
    _state.sum_max = sum_max

    pos_seen = {p: set() for p in range(1, 7)}
    for row in data:
        r = sorted(row[1:7])
        for p in range(1, 7):
            pos_seen[p].add(r[p-1])

    valid = []
    soft = set()
    param = set()
    h2, h3 = 0, 0
    s1, s4, s5, s6, s7 = 0, 0, 0, 0, 0

    for c in itertools.combinations(range(1, 34), 6):
        if _check_hard(c):
            h2 += 1; continue
        if c in past_reds:
            h3 += 1; continue
        valid.extend(c)
        sv = _check_soft(c, sum_min, sum_max)
        if "s1_consecutive" in sv: s1 += 1; soft.add(c)
        if "s4_max_gap" in sv:     s4 += 1; soft.add(c)
        if "s6_odd_even" in sv:    s6 += 1; param.add(c)
        if "s7_sum_range" in sv:   s7 += 1; param.add(c)
        s = sorted(c)
        for p in range(1, 7):
            if s[p-1] not in pos_seen[p]:
                s5 += 1; soft.add(c)
                break

    _state.valid_reds = valid
    _state.soft_excluded = soft
    _state.param_excluded = param
    _state.rule_status = {
        "h2_arithmetic":  {"type": "hard", "excluded": h2},
        "h3_historical":  {"type": "hard", "excluded": h3},
        "s1_consecutive": {"type": "soft", "excluded": s1},
        "s4_max_gap":     {"type": "soft", "excluded": s4},
        "s5_position":    {"type": "soft", "excluded": s5},
        "s6_odd_even":    {"type": "param", "excluded": s6},
        "s7_sum_range":   {"type": "param", "excluded": s7},
    }

    # 写缓存
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, 'wb') as f:
            pickle.dump({
                'past_count': _state.past_count,
                'valid_reds': valid,
                'soft_excluded': soft,
                'param_excluded': param,
                'rule_status': _state.rule_status,
            }, f)
    except Exception:
        pass


def rule_status():
    if _state.valid_reds is None:
        _build_pool()
    return _state.rule_status


# ═══ 蓝球 ═══

def _blue_freq_weights():
    from server.db import load_draws
    data = load_draws()
    weights = [1.0] * 16
    for row in data:
        weights[row[7] - 1] += 1.0
    total = sum(weights)
    return [w / total for w in weights]


def _freq_blue_candidates(n=6):
    from server.db import load_draws
    data = load_draws()
    counts = [1.0] * 16
    for row in data:
        counts[row[7] - 1] += 1.0
    ranked = sorted(range(16), key=lambda i: counts[i], reverse=True)
    return set(i + 1 for i in ranked[:n])


def _weighted_choice(weights, candidates, rng=random):
    cands = list(candidates)
    if not cands:
        return None
    ws = [weights[c - 1] for c in cands]
    total = sum(ws)
    if total <= 0:
        return rng.choice(cands)
    r = rng.random() * total
    cum = 0.0
    for c, w in zip(cands, ws):
        cum += w
        if r < cum:
            return c
    return cands[-1]


def _pick_blue(weights, exclude=None):
    cands = [i + 1 for i in range(16) if weights[i] > 0
             and (exclude is None or (i + 1) not in exclude)]
    if not cands:
        cands = [i + 1 for i in range(16) if weights[i] > 0]
    if not cands:
        cands = list(range(1, 17))
    return _weighted_choice(weights, cands)


# ═══ 出号核心 ═══

def _try_one_ticket(reds, used_reds, used_blues, tickets, blue_weights, max_overlap=None, constraint_level='normal'):
    if reds in used_reds:
        return None
    if max_overlap is not None and tickets:
        if any(len(set(reds) & set(t["reds"])) > max_overlap for t in tickets):
            return None
    # Stage 2: 全局结构约束过滤
    from ml.global_constraint import validate_combo
    ok, _ = validate_combo(reds, constraint_level=constraint_level)
    if not ok:
        return None
    blue_exclude = used_blues if max_overlap == 0 else None
    blue = _pick_blue(blue_weights, exclude=blue_exclude)
    used_reds.add(reds)
    if max_overlap == 0:
        used_blues.add(blue)
    return {"reds": list(reds), "blue": blue}


def _random_tickets(n, max_overlap=None, constraint_level='normal'):
    """纯随机 fallback."""
    blue_weights = _blue_freq_weights()
    tickets, used_reds, used_blues = [], set(), set()
    for _ in range(n):
        for _ in range(800):
            c = tuple(sorted(random.sample(range(1, 34), 6)))
            t = _try_one_ticket(c, used_reds, used_blues, tickets, blue_weights, max_overlap, constraint_level=constraint_level)
            if t:
                tickets.append(t); break
        else:
            blue = _pick_blue(blue_weights,
                              exclude=used_blues if max_overlap == 0 else None)
            if max_overlap == 0:
                used_blues.add(blue)
            tickets.append({"reds": [1, 2, 3, 4, 5, 6], "blue": blue})
    return tickets


# ═══ 主入口 ═══

def generate_tickets(n=3, soft=False, max_overlap=0, use_freq_blue=False, constraint_level='normal', **kwargs):
    """生成号码 — gap+position 信号融合 + 全局约束过滤.

    Args:
        n: 注数 (1-3)
        soft: 启用软过滤
        max_overlap: 注间最大红球重叠 (0=不重叠, None=不限)
        use_freq_blue: 蓝球缩小池 (top-6)
        constraint_level: 全局约束 'loose'|'normal'|'strict'
    """
    from server.db import load_draws

    # 建池
    try:
        if _state.valid_reds is None or len(load_draws()) != _state.past_count:
            _build_pool()
    except Exception:
        _state.valid_reds = None

    if _state.valid_reds is None:
        tickets = _random_tickets(n, max_overlap, constraint_level=constraint_level)
        return _response(tickets, n, "Fallback-Random", soft, False)

    exclude = _state.soft_excluded if soft else set()
    n_combos = len(_state.valid_reds) // 6
    if n_combos * 6 != len(_state.valid_reds) or n_combos == 0:
        tickets = _random_tickets(n, max_overlap, constraint_level=constraint_level)
        return _response(tickets, n, "Fallback-Random", soft, False)

    # 蓝球 — 频率加权
    blue_method = "频率加权"
    try:
        from ml.signal_aggregator import collect_blue_signals
        blue_fused, blue_diag = collect_blue_signals(load_draws())
    except Exception:
        blue_fused = None

    if blue_fused is None:
        blue_weights = _blue_freq_weights()
        blue_method = "均匀蓝球(降级)"
    elif use_freq_blue:
        # 缩小池模式: 取融合权重 top-6 蓝球, 用融合权重做加权
        ranked = sorted([(b, blue_fused[b]) for b in range(1, 17)], key=lambda x: -x[1])
        blue_candidates = set(b for b, _ in ranked[:6])
        blue_weights = [0.0] * 16
        for b in blue_candidates:
            blue_weights[b - 1] = blue_fused[b]
        total = sum(blue_weights)
        if total > 0:
            blue_weights = [w / total for w in blue_weights]
        blue_method = "频率Top-6"
    else:
        # 全池模式: 直接使用融合权重
        blue_weights = [0.0] * 16
        for b in range(1, 17):
            blue_weights[b - 1] = blue_fused[b]
        total = sum(blue_weights)
        if total > 0:
            blue_weights = [w / total for w in blue_weights]
        blue_method = "频率加权"

    # 红球信号融合 (gap_analysis + position_model)
    red_w = [1.0] * 34
    try:
        from ml.signal_aggregator import collect_all_signals
        fused_w, _ = collect_all_signals(load_draws())
        for num in range(1, 34):
            red_w[num] = fused_w[num]
    except Exception:
        pass  # 降级为均匀权重

    # best-of-20 加权采样
    def _pick(n_combos=n_combos):
        c = random.sample(range(n_combos), min(20, n_combos))
        return max(c, key=lambda i: sum(red_w[v] for v in _state.valid_reds[i*6:i*6+6]))

    used_idx, used_reds, used_blues = set(), set(), set()
    tickets = []
    for _ in range(n):
        for _ in range(500):
            idx = _pick()
            if idx in used_idx:
                continue
            reds = tuple(_state.valid_reds[idx*6:idx*6+6])
            if reds in exclude or reds in used_reds:
                continue
            t = _try_one_ticket(reds, used_reds, used_blues, tickets, blue_weights, max_overlap, constraint_level=constraint_level)
            if t:
                used_idx.add(idx); tickets.append(t); break
        else:
            # 池采样失败, 随机 fallback
            for _ in range(500):
                c = tuple(sorted(random.sample(range(1, 34), 6)))
                if c in used_reds:
                    continue
                t = _try_one_ticket(c, used_reds, used_blues, tickets, blue_weights, max_overlap, constraint_level=constraint_level)
                if t:
                    tickets.append(t); break
            else:
                blue = _pick_blue(blue_weights, exclude=used_blues if max_overlap == 0 else None)
                if max_overlap == 0:
                    used_blues.add(blue)
                tickets.append({"reds": [1, 2, 3, 4, 5, 6], "blue": blue})

    return _response(tickets, n, "Pool-Sampling+Gap+Position", soft,
                     soft_excluded=len(exclude), pool_valid=sum(1 for c in _state.valid_reds) // 6 - len(exclude),
                     blue_method=blue_method, rule_status=_state.rule_status)


def _response(tickets, n, algo, soft, soft_excluded=0, pool_valid=None, blue_method="均匀分布", rule_status=None):
    return {
        "ok": True, "algorithm": algo, "tickets": tickets, "budget": n,
        "cost_rmb": n * TICKET_PRICE,
        "pool_size": (pool_valid or 0) * 16,
        "pool_valid_reds": pool_valid,
        "soft_filter": soft, "soft_excluded": soft_excluded,
        "rule_status": rule_status or {},
        "blue_method": blue_method,
    }
