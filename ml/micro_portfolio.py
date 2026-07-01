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
    __slots__ = ('valid_reds', 'rule_status', 'past_count', 'sum_min', 'sum_max')
    def __init__(self):
        self.valid_reds = None
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
    h2, h3 = 0, 0

    for c in itertools.combinations(range(1, 34), 6):
        if _check_hard(c):
            h2 += 1; continue
        if c in past_reds:
            h3 += 1; continue
        valid.extend(c)

    _state.valid_reds = valid
    _state.rule_status = {
        "h2_arithmetic":  {"type": "hard", "excluded": h2},
        "h3_historical":  {"type": "hard", "excluded": h3},
    }

    # 写缓存
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, 'wb') as f:
            pickle.dump({
                'past_count': _state.past_count,
                'valid_reds': valid,
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

def generate_tickets(n=3, max_overlap=0, constraint_level='normal', **kwargs):
    """生成号码 — gap+position 信号融合 + 全局约束过滤.

    Args:
        n: 注数 (1-3)
        max_overlap: 注间最大红球重叠 (0=不重叠, None=不限)
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
        return _response(tickets, n, "Fallback-Random")

    n_combos = len(_state.valid_reds) // 6
    if n_combos * 6 != len(_state.valid_reds) or n_combos == 0:
        tickets = _random_tickets(n, max_overlap, constraint_level=constraint_level)
        return _response(tickets, n, "Fallback-Random")

    # 蓝球 — 间隔分析
    blue_method = "间隔分析蓝球"
    try:
        from ml.signal_aggregator import collect_blue_signals
        blue_fused, blue_diag = collect_blue_signals(load_draws())
        blue_weights = [0.0] * 16
        for b in range(1, 17):
            blue_weights[b - 1] = blue_fused[b]
        total = sum(blue_weights)
        if total > 0:
            blue_weights = [w / total for w in blue_weights]
        blue_method = blue_diag.get("algorithm", "间隔分析蓝球")
    except Exception:
        blue_weights = _blue_freq_weights()
        blue_method = "频率蓝球(降级)"

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
    def _pick():
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
            if reds in used_reds:
                continue
            t = _try_one_ticket(reds, used_reds, used_blues, tickets, blue_weights, max_overlap, constraint_level=constraint_level)
            if t:
                used_idx.add(idx); tickets.append(t); break
        else:
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

    pool_valid = sum(1 for _ in _state.valid_reds) // 6
    return _response(tickets, n, "Pool-Sampling+Gap+Position",
                     pool_valid=pool_valid, blue_method=blue_method, rule_status=_state.rule_status)


def _response(tickets, n, algo, pool_valid=None, blue_method="间隔分析蓝球", rule_status=None):
    return {
        "ok": True, "algorithm": algo, "tickets": tickets, "budget": n,
        "cost_rmb": n * TICKET_PRICE,
        "pool_size": (pool_valid or 0) * 16,
        "pool_valid_reds": pool_valid,
        "rule_status": rule_status or {},
        "blue_method": blue_method,
    }
