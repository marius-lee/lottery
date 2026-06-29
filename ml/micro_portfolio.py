"""有效号码池随机采样 + 运气规则（位置短窗动量）。

硬过滤 (组合数学, 始终生效):
  规则2 等差序列 d≥2
  规则3 历史已开红球

软过滤 (可选, 历史极少出现, 每期动态):
  规则S1 ≥5连号
  规则S4 最大间距≥24
  规则S5 位置从未出现

运气规则 (双入口):
  pure  = 位置加权独立抽号 → 硬过滤 → 去重 (幸运开奖按钮)

权重约定 (编码纪律): 各作者方法的权重值遵循项目统一规则:
  - 0.01 = 接近排除 (原书: "排除"/"范围外")
  - 0.1  = 大幅降权 (原书: "大幅降低")
  - 0.3  = 显著降权 (原书: "降权")
  - 0.4  = 中等降权 (原书: "略微降低")
  - 0.5  = 方向性调整 (原书: "冷/热偏好")
  所有具体权重值均在各函数内标注原书页码来源.
"""
import random
import itertools
import threading
from ml.ssq_constants import TICKET_PRICE, RANDOM_SINGLE_EV
from ml.shared.spread import compute_spread       # [李相春2003, 彩天使2004]
from ml.shared.ac_value import compute_ac_value     # [李相春2003, 刘大军2010]


from dataclasses import dataclass, field


@dataclass
class FilterConfig:
    """红球过滤配置 — 消除 handler→bridge→generate_tickets 三层25参数平铺.
    
    所有字段默认 False, 由 handler 层从查询参数构建.
    """
    color_filter: bool = False
    block9_filter: bool = False
    spread_filter: bool = False
    ac_filter: bool = False
    peng_channel_filter: bool = False
    gap_filter: bool = False
    omission_filter: bool = False
    coincidence_filter: bool = False
    wuming_clockwise: bool = False
    wuming_bsd: bool = False
    
    def as_kwargs(self) -> dict:
        """展开为 generate_tickets 兼容的关键字参数字典."""
        return {
            'color_filter': self.color_filter,
            'block9_filter': self.block9_filter,
            'spread_filter': self.spread_filter,
            'ac_filter': self.ac_filter,
            'peng_channel_filter': self.peng_channel_filter,
            'gap_filter': self.gap_filter,
            'omission_filter': self.omission_filter,
            'coincidence_filter': self.coincidence_filter,
            'wuming_clockwise': self.wuming_clockwise,
            'wuming_bsd': self.wuming_bsd,
        }


# ── 吴明/夏志强策略已提取至独立模块 (ml/wuming.py, ml/xia_zhiqiang.py), 此处保留别名 ──
from ml.wuming import (BLUE_CLOCKWISE, BLUE_BSD_TAIL, POSITION_VALUABLE,
    wuming_cyclic_oscillation as _wuming_cyclic_oscillation,
    wuming_blue_extreme_alert as _wuming_blue_extreme_alert,
    wuming_clockwise_weights as _wuming_clockwise_weights,
    wuming_bsd_tail_weights as _wuming_bsd_tail_weights,
    period5_hotness as _period5_hotness,
    period9_cold as _period9_cold,
    zone6_exclusion as _zone6_exclusion,
    position_filter as _position_filter,
    wu_sum_compound as _wu_sum_compound,
    extreme_value_dan as _extreme_value_dan,
    repeat_method as _repeat_method)
from ml.xia_zhiqiang import (xia_sub4_add4_blue as _xia_sub4_add4_blue,
    xia_compute_reds as _xia_compute_reds)

# ═══════════════════════════════════════════════════════════════════════════
# 线程安全状态容器 — 所有模块级缓存收敛到单一持有者
# ═══════════════════════════════════════════════════════════════════════════

class _PoolState:
    """线程安全的状态容器 — 所有模块级缓存的单一持有者.
    
    设计原则:
      - 所有可变状态集中管理, 读写通过 _state.xxx
      - _state.lock 保护建池等写操作
      - 当前服务使用单线程 HTTPServer, 锁为前向兼容
    """
    __slots__ = ('lock', 'valid_reds', 'soft_excluded', 'param_excluded',
                 'rule_status', 'past_count', 'last_verified',
                 'sum_min', 'sum_max',
                 'peng_channels', 'peng_channels_data_count',
                 'omission_ratios', 'omission_data_count',
                 'calibrated', 'luck_blue_mix')
    
    def __init__(self):
        self.lock = threading.Lock()
        self.valid_reds = None
        self.soft_excluded = None
        self.param_excluded = None
        self.rule_status = {}
        self.past_count = 0
        self.last_verified = 0
        self.sum_min = None
        self.sum_max = None
        self.peng_channels = None
        self.peng_channels_data_count = 0
        self.omission_ratios = None
        self.omission_data_count = 0
        self.calibrated = False
        self.luck_blue_mix = 0.06

_state = _PoolState()


# [彭浩 2010] 通道过滤缓存 — 每位置[下轨, 上轨]范围

# [刘大军 2010] 重合码 — 大中小∩012路交叉验证 [文献] 擒号绝技 p21-22
# 大数{7,8,9}∩2路{2,5,8}={8}, 中数{3,4,5,6}∩0路{0,3,6,9}={3,6}, 小数{0,1,2}∩1路{1,4,7}={1}
from ml.liu_dajun import COINCIDENCE_TAILS

# [彩天使 2009] 遗漏比缓存 — 每号码当前遗漏比
# 理论周期: 红球33/6=5.5 [文献] 新编绝算双色球 p89
_RED_PERIOD = 33.0 / 6.0  # 5.5

# [原书] 吴长坤《双色球擒号绝技》(2010) Ch4 §6: 三色分解体系
# 红球按波色分3类, 7码(6红+1蓝)需三色俱备(原书声称95%, 近500期实测81.4%)
COLOR_RED = {1,2,7,8,12,13,18,19,23,24,29,30}       # 红色系 12个
COLOR_BLUE = {3,4,9,10,14,15,20,25,26,31}           # 蓝色系 10个
COLOR_GREEN = {5,6,11,16,17,21,22,27,28,32,33}      # 绿色系 11个

# [原书] 吴长坤《双色球擒号绝技》(2010) Ch6 §1: 方块9杀号
# 33红球排成6行×6列, 取13个重叠的3×3方块. 约80%期有空方块, 空方块持续≤3期.
# 行1:1-6, 行2:7-12, 行3:13-18, 行4:19-24, 行5:25-30, 行6:31-33
BLOCK_9 = [
    {1,2,3,7,8,9,13,14,15},    {2,3,4,8,9,10,14,15,16},
    {3,4,5,9,10,11,15,16,17},  {4,5,6,10,11,12,16,17,18},
    {7,8,9,13,14,15,19,20,21}, {8,9,10,14,15,16,20,21,22},
    {9,10,11,15,16,17,21,22,23}, {10,11,12,16,17,18,22,23,24},
    {13,14,15,19,20,21,25,26,27}, {14,15,16,20,21,22,26,27,28},
    {15,16,17,21,22,23,27,28,29}, {16,17,18,22,23,24,28,29,30},
    {19,20,21,25,26,27,31,32,33},
]

def _block9_kill(data):
    """方块9重复杀号法 [吴长坤 2010 Ch6 §1].

    上期空方块下期继续杀（空方块持续≤3期）.
    返回被杀的号码集合.
    """
    if len(data) < 2:
        return set()

    last_reds = set(data[-1][1:7])
    prev_reds = set(data[-2][1:7])

    killed = set()
    for block in BLOCK_9:
        # 上期该方块为空 → 本期继续杀
        if not (last_reds & block):
            killed.update(block)

    return killed


# ── 运气规则参数 ──
# [工程] 运气规则: 蒋加林(2001)"百万军中选大将"概念, 非原书精确参数
#   窗口=10: 短窗捕捉近期号码动量（与双色球每周3期匹配: 10≈3周）
#   混合=0.5: Laplace频率+运气偏置等权融合
#   蓝球=0.06: 初始猜测(≈1/16=0.0625), 首次运行时自动校准到实际频率

LUCK_WINDOW = 10        # 回溯窗口期数
LUCK_COEFF = 0.5        # 混合偏置强度 (blend模式)


def _check_hard(reds):
    """检查硬规则违规(2). 返回违规规则名."""
    s = sorted(reds)
    d = s[1] - s[0]
    if all(s[i] - s[i-1] == d for i in range(2, 6)):
        return ["h2_arithmetic"]
    return []


def _check_soft(reds, param_filter=False, color_filter=False):
    """检查软规则违规(S1, S4, S6奇偶比, S7和值范围, S8三色分解)."""
    s = sorted(reds)
    v = []
    run = cur = 1
    for i in range(1, 6):
        if s[i] - s[i-1] == 1: cur += 1; run = max(run, cur)
        else: cur = 1
    if run >= 5: v.append("s1_consecutive")
    # [工程] 最大间距≥24: 6红球跨度上限保守估计(理论max=27), 超过则视为异常分布
    if max(s[i+1] - s[i] for i in range(5)) >= 24: v.append("s4_max_gap")

    # P2: 基本参数控制 (蒋加林 2001 第七绝招)
    if param_filter:
        odd = sum(1 for n in s if n % 2 == 1)
        if odd <= 1 or odd >= 5:  # 拒绝 0:6, 1:5, 5:1, 6:0
            v.append("s6_odd_even")
        if _state.sum_min is not None and _state.sum_max is not None:
            total = sum(s)
            if total < _state.sum_min or total > _state.sum_max:
                v.append("s7_sum_range")

    # 吴长坤 2010 Ch4 §6: 三色分解 — 6红球需含全部3种波色
    if color_filter:
        has_red = bool(set(s) & COLOR_RED)
        has_blue = bool(set(s) & COLOR_BLUE)
        has_green = bool(set(s) & COLOR_GREEN)
        if not (has_red and has_blue and has_green):
            v.append("s8_color_three")

    return v


def _verify():
    """验证新增期数, 报告软规则违规 (含 S5 位置)."""
    global _state
    from server.db import load_draws
    data = load_draws()
    new = [r for r in data if r[0] > _state.last_verified]
    if not new: return
    old_rows = [r for r in data if r[0] <= _state.last_verified]
    pos_seen = {p: set() for p in range(1, 7)}
    for row in old_rows:
        r = sorted(row[1:7])
        for p in range(1, 7):
            pos_seen[p].add(r[p - 1])
    for row in new:
        for name in _check_soft(row[1:7]):
            _state.rule_status[name]["violations"].append(row[0])
        r = sorted(row[1:7])
        for p in range(1, 7):
            if r[p - 1] not in pos_seen[p]:
                _state.rule_status.get("s5_position", {}) \
                    .setdefault("violations", []).append(row[0])
                break
        for p in range(1, 7):
            pos_seen[p].add(r[p - 1])
    _state.last_verified = data[-1][0]


def _build_pool():
    """枚举 C(33,6), 硬过滤 + 软过滤."""
    global _state
    from server.db import load_draws
    data = load_draws()
    _state.past_count = len(data)
    past_reds = {tuple(sorted(r[1:7])) for r in data}
    if not _state.rule_status:
        _state.rule_status = {
            "h2_arithmetic":  {"type": "hard", "excluded": 0, "violations": []},
            "h3_historical":  {"type": "hard", "excluded": 0, "violations": []},
            "s1_consecutive": {"type": "soft", "excluded": 0, "violations": []},
            "s4_max_gap":     {"type": "soft", "excluded": 0, "violations": []},
            "s5_position":    {"type": "soft", "excluded": 0, "violations": []},
            "s6_odd_even":    {"type": "param", "excluded": 0, "violations": []},
            "s7_sum_range":   {"type": "param", "excluded": 0, "violations": []},
        }
    # P2: 计算历史红球和值 P5/P95 范围 [数据] 百分位数来自蒋加林2001
    if _state.sum_min is None:
        hist_sums = sorted(sum(row[1:7]) for row in data)
        n_hist = len(hist_sums)
        # [统计] n≥20: 百分位数估计的最小可靠样本量(统计经验准则)
        # [数学] 21=C(6,1)=理论最小和值, 183=28+29+30+31+32+33=理论最大和值
        _state.sum_min = hist_sums[int(n_hist * 0.05)] if n_hist >= 20 else 21
        _state.sum_max = hist_sums[int(n_hist * 0.95)] if n_hist >= 20 else 183

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
    _state.valid_reds = valid
    _state.soft_excluded = soft
    _state.param_excluded = param
    _state.rule_status["h2_arithmetic"]["excluded"] = h2
    _state.rule_status["h3_historical"]["excluded"] = h3
    _state.rule_status["s1_consecutive"]["excluded"] = s1
    _state.rule_status["s4_max_gap"]["excluded"] = s4
    _state.rule_status["s5_position"]["excluded"] = s5
    _state.rule_status["s6_odd_even"]["excluded"] = s6
    _state.rule_status["s7_sum_range"]["excluded"] = s7


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


# ═══════════════════════════════════════════════════════════════════════════
# 蓝球候选集 (独立投票: weight>=0.5→推荐, 交集)
# ═══════════════════════════════════════════════════════════════════════════

def _w2c(weights, threshold=0.5):
    return {i + 1 for i, w in enumerate(weights) if w >= threshold}

def _five_period_candidates():
    return _w2c(_five_period_boost(), 0.5)

def _pattern_blue_candidates():
    return _w2c(_pattern_blue_boost(), 0.3)

def _liu_dajun_candidates():
    return _w2c(_liu_dajun_blue(), 0.5)

def _cailele_candidates():
    return _w2c(_cailele_blue(), 0.5)

def _gongyi_candidates():
    return _w2c(_gongyi_blue(), 0.5)

def _wuming_candidates():
    return _w2c(_wuming_blue(), 0.5)

def _wuming_clockwise_candidates():
    return _w2c(_wuming_clockwise_weights(), 0.5)

def _wuming_bsd_candidates():
    return _w2c(_wuming_bsd_tail_weights(), 0.5)


def _five_period_boost():
    """五期断蓝法 (刘大军, 2011): 近5期蓝球均值±4作为选号范围.

    原书: "可以在奖号04~12中选择" — 范围外排除。
    来源: 《双色球蓝球中奖绝技》第六章, 公式一."""
    from server.db import load_draws
    data = load_draws()
    if len(data) < 5:
        return [1.0] * 16
    recent = [r[7] for r in data[-5:]]
    avg = round(sum(recent) / 5)
    boost = [0.01] * 16  # 范围外几乎排除 (原书: 范围外不选)
    for n in range(max(1, avg - 4), min(16, avg + 4) + 1):
        boost[n - 1] = 1.0
    return boost



# ═══════════════════════════════════════════════════════════════════════════
# 按作者分组的独立蓝球策略 (各作者方法不混用)
# ═══════════════════════════════════════════════════════════════════════════

def _liu_dajun_blue():
    """刘大军《双色球蓝球中奖绝技》(2011) 蓝球方法.
    包含: 五期断蓝+三斜连反转+三效应连锁+竹节反转+冷热阈值+遗漏排除+矩阵杀蓝."""
    from server.db import load_draws
    data = load_draws()
    weights = [1.0] * 16
    if len(data) < 5:
        return weights
    blues = [r[7] for r in data]
    last = blues[-1]
    prev = blues[-2] if len(blues) >= 2 else last

    # 五期断蓝法 (第六章): 近5期均值±4, 范围外排除
    recent5 = blues[-5:]
    avg = round(sum(recent5) / 5)
    for n in range(1, 17):
        if n < avg - 4 or n > avg + 4:
            weights[n - 1] = 0.01

    # 三斜连反转 (p.157-163): 连3步同向→降权下一顺位
    if len(blues) >= 4:
        d1, d2, d3 = blues[-1]-blues[-2], blues[-2]-blues[-3], blues[-3]-blues[-4]
        if d1 == d2 == d3 and d1 != 0:
            cont = last + d1
            if 1 <= cont <= 16:
                weights[cont - 1] = 0.3

    # 三效应连锁 (p.135-136): 集聚/发散/惯性
    gap = abs(last - prev)
    if gap <= 2:
        for n in range(max(1, last - 2), min(16, last + 2) + 1):
            if weights[n - 1] > 0.01:
                weights[n - 1] = 1.0
    elif gap >= 7:
        for n in range(1, 17):
            if abs(n - last) >= 7 and weights[n - 1] > 0.01:
                weights[n - 1] = 1.0

    # 竹节反转 (p.146): 4期等差→降权延续方向
    if len(blues) >= 4:
        seq4 = blues[-4:]
        diffs = [seq4[i+1]-seq4[i] for i in range(3)]
        if len(set(diffs)) == 1 and diffs[0] != 0:
            for n in range(1, 17):
                if (diffs[0] > 0 and n > last) or (diffs[0] < 0 and n < last):
                    if weights[n - 1] > 0.01:
                        weights[n - 1] = 0.4

    # 冷热阈值 (原书 p.129): 实际/理论>1.5→热, <0.5→冷
    # [工程] window=50: 50期≈4个月,覆盖冷热转换周期
    window = min(50, len(data))
    recent = blues[-window:]
    theory = 1.0/16
    for n in range(1, 17):
        actual = recent.count(n) / len(recent)
        if theory > 0 and actual < theory * 0.5:
            weights[n - 1] *= 0.5
        elif actual > theory * 1.5:
            weights[n - 1] = 1.0

    # 长期遗漏排除 (p.129,157): 遗漏20-50期的top-5排除
    omissions = {}
    for b in range(1, 17):
        for offset, row in enumerate(reversed(data)):
            if row[7] == b:
                omissions[b] = offset
                break
        else:
            omissions[b] = float('inf')
    long_cold = sorted([(b,om) for b,om in omissions.items() if 20<=om<=50], key=lambda x:-x[1])
    for b, om in long_cold[:5]:
        weights[b - 1] *= 0.01

    # 矩阵杀蓝法 (p.179-182): 连续3期同组→绝杀; 连续2期同组→保留
    groups = {0:[1,5,9,13], 1:[2,6,10,14], 2:[3,7,11,15], 3:[4,8,12,16]}
    def _g(b):
        for gk, gv in groups.items():
            if b in gv: return gk
        return -1
    if len(blues) >= 3:
        g3 = [_g(b) for b in blues[-3:]]
        if g3[0] == g3[1] == g3[2]:
            for b in groups.get(g3[0], []):
                weights[b - 1] *= 0.01
    if len(blues) >= 2:
        g2, g1 = _g(blues[-2]), _g(blues[-1])
        if g2 == g1:
            for b in groups.get(g1, []):
                if weights[b - 1] > 0.01:
                    weights[b - 1] = 1.0

    return weights


def _cailele_blue():
    """彩乐乐《中彩好帮手》(2017) 蓝球方法.
    包含: 形态统计(奇偶/大小max驱动)+尾数驱码."""
    from server.db import load_draws
    data = load_draws()
    weights = [1.0] * 16
    if len(data) < 10:  # [工程] 彩乐乐蓝球法最少需要10期数据
        return weights
    blues = [r[7] for r in data]
    last = blues[-1]

    # 奇偶形态: 奇数max连续6期, 偶数5期 (p43). streak≥一半时触发
    oe = [1 if b%2==1 else 0 for b in blues]
    oe_streak = 1
    for i in range(len(oe)-1, 0, -1):
        if oe[i]==oe[i-1]: oe_streak+=1
        else: break
    cur_parity = oe[-1]
    parity_max = 6 if cur_parity==1 else 5
    if oe_streak >= parity_max//2:
        for n in range(1, 17):
            if (1 if n%2==1 else 0) == cur_parity:
                weights[n-1] *= 0.3
            else:
                weights[n-1] = 1.0

    # 大小形态: 大号max5, 小号max4 (p42)
    bs = [1 if b>=9 else 0 for b in blues]
    bs_streak = 1
    for i in range(len(bs)-1, 0, -1):
        if bs[i]==bs[i-1]: bs_streak+=1
        else: break
    cur_bs = bs[-1]
    bs_max = 5 if cur_bs==1 else 4
    if bs_streak >= bs_max//2:
        for n in range(1, 17):
            if (1 if n>=9 else 0) == cur_bs:
                weights[n-1] *= 0.3
            else:
                weights[n-1] = 1.0

    # 尾数驱码 (p45): 上期尾数→查表排除
    tail_map = {1:[6,10],2:[3,7,8,9],3:[3],4:[5,7,9],5:[2,4,10,16],
                6:[5,8,10,12,16],7:[9,12,15],8:[4,5,6,7,8,10,12,14,16],
                9:[1,3,5,8,10,11,12,14,16],0:[1,2,3,4,8,9,10,12,13,16]}
    for b in tail_map.get(last%10, []):
        if 1<=b<=16:
            weights[b-1] *= 0.01

    return weights


def _gongyi_blue():
    """公益时报《玩转双色球》(2010) 蓝球方法.
    包含: 期次转换法+代码对称法."""
    from server.db import load_draws
    data = load_draws()
    weights = [1.0] * 16
    if len(data) < 5:
        return weights
    blues = [r[7] for r in data]
    last = blues[-1]

    # 期次转换法 (p149): 双重012路码型→排除
    code_map = {(0,0):[3,6,9],(0,2):[12,15],(1,0):[10,13,16],
                (1,1):[1,4,7],(2,1):[11,14],(2,2):[2,5,8]}
    last_code = (last%3, (last%10)%3)
    for b in code_map.get(last_code, []):
        weights[b-1] *= 0.01

    # 代码对称法 (p154-162): 除5余数对称→回补
    codes = [b%5 for b in blues]
    code_balls = {0:[5,15,10],1:[1,11,6,16],2:[2,12,7],3:[3,13,8],4:[4,14,9]}
    if len(codes)>=4 and codes[-1]==codes[-4] and codes[-1]!=codes[-2]:
        for b in code_balls.get(codes[-1],[]):
            weights[b-1] = 1.0
    if len(codes)>=5 and codes[-1]==codes[-5] and codes[-2]==codes[-4]:
        for b in code_balls.get(codes[-1],[]):
            weights[b-1] = 1.0

    return weights


def _wuming_blue():
    """吴明《双色球蓝球大法》(经济管理出版社 约2006) 蓝球方法. ← 永久锁定来源, 勿改.
    包含: 背离率(Ch2)+大小极值(Ch2)+4区间极值(Ch2§6)+除4余数极值(Ch2§7).
    已核实: 198页蓝球专著. 非《核心秘密》(红球)/《揭秘》(汇编)/《细节战法》."""
    from server.db import load_draws
    data = load_draws()
    weights = [1.0] * 16
    if len(data) < 5:
        return weights
    blues = [r[7] for r in data]

    # 背离率 (p117-119): 遗漏/16×100%, >400%→关注
    omissions = {}
    for b in range(1, 17):
        for offset, row in enumerate(reversed(data)):
            if row[7] == b:
                omissions[b] = offset
                break
        else:
            omissions[b] = float('inf')
    for b in range(1, 17):
        om = omissions.get(b, float('inf'))
        if om > 0 and om != float('inf'):
            dev = om/16*100
            if dev >= 400:
                weights[b-1] = 1.0

    # 极值优先 (p63,p93-107): 大小号实际极值=7
    bs = [1 if b>=9 else 0 for b in blues]
    bs_streak = 1
    for i in range(len(bs)-1,0,-1):
        if bs[i]==bs[i-1]: bs_streak+=1
        else: break
    if bs_streak >= 5:
        for n in range(1, 17):
            if (1 if n>=9 else 0) == bs[-1]:
                weights[n-1] *= 0.01
            else:
                weights[n-1] = 1.0

    # 4区间极值 (p86-89): 每区间连出极值=3, 连空极值=8-9
    qu = [((b-1)//4) for b in blues]  # 0:01-04, 1:05-08, 2:09-12, 3:13-16
    for qi in range(4):
        streak = 1
        for i in range(len(qu)-1, 0, -1):
            if qu[i]==qi and qu[i-1]==qi: streak+=1
            else: break
        if streak >= 3:
            for n in range(qi*4+1, qi*4+5):
                weights[n-1] *= 0.01

    # 除4余数极值 (p89-95): 每区间连出极值=3(399期从未超3!), 连空极值=8-9
    rem4 = [b%4 for b in blues]
    for ri in range(4):
        streak = 1
        for i in range(len(rem4)-1, 0, -1):
            if rem4[i]==ri and rem4[i-1]==ri: streak+=1
            else: break
        if streak >= 3:
            for n in range(1, 17):
                if n%4 == ri:
                    weights[n-1] *= 0.01

    return weights


# ═══════════════════════════════════════════════════════════════════════════
# 旧版 _pattern_blue_boost (向后兼容, 调用4个独立函数)
# ═══════════════════════════════════════════════════════════════════════════

def _pattern_blue_boost():
    """旧版兼容: 4个作者方法等权平均."""
    w = [1.0]*16
    for fn in [_liu_dajun_blue, _cailele_blue, _gongyi_blue, _wuming_blue]:
        fw = fn()
        for i in range(16):
            w[i] *= fw[i]
    total = sum(w)
    return [x/total for x in w] if total > 0 else [1/16]*16




# ═══════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════
def _calibrate_luck_blue_mix():
    """滑动窗口回测确定最优蓝球运气融合比例。"""
    global _state
    from server.db import load_draws
    data = load_draws()
    window = LUCK_WINDOW
    if len(data) < window + 5:
        return
    best_mix = _state.luck_blue_mix
    best_hits = -1
    # [工程] 0-30%以2%步长扫描: 31是合理上界(>30%运气就没意义了), 2%足够分辨最优
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
    _state.luck_blue_mix = best_mix
    _state.calibrated = True


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
    mix = _state.luck_blue_mix if mix is None else mix
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


def _pick_blue(weights):
    """从蓝球权重中按概率抽取一个号码. 每注独立, 不要求跨注不重复."""
    return _weighted_choice(weights, list(range(1, 17)))


def _pick_unique_blue(weights, used=None):
    """从蓝球权重中抽取, 确保不与 used 中的重复."""
    if used is None:
        used = set()
    candidates = [b for b in range(1, 17) if b not in used]
    return _weighted_choice(weights, candidates)


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


def _generate_luck_tickets(n=3, max_overlap=None, five_period=False, pattern_rules=False):
    """纯运气模式: 位置加权抽取 → 硬过滤 → 去重 → 蓝球.

    不依赖 _state.valid_reds 池, 不依赖软过滤.
    每次独立按位置频率加权抽取, 硬过滤校验, 跨注去重.
    """
    if not _state.calibrated:
        _calibrate_luck_blue_mix()

    red_weights, blue_luck = _compute_luck_position_weights()
    freq_weights = _blue_freq_weights()
    if five_period:
        fpb = _five_period_boost()
        freq_weights = [freq_weights[i] * fpb[i] for i in range(16)]
    if pattern_rules:
        ppb = _pattern_blue_boost()
        freq_weights = [freq_weights[i] * ppb[i] for i in range(16)]
    blue_weights = _luck_blended_blue_weights(freq_weights, blue_luck)

    tickets = []
    used_reds = set()

    for _ in range(n):
        found = False
        for _ in range(500):  # [工程] 重试上限: 防止无限循环
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
            blue = _pick_blue(blue_weights)
            tickets.append({"reds": reds, "blue": blue})
            found = True
            break
        if not found:
            # 降级: 纯随机 + 硬过滤
            for _ in range(500):  # [工程] 重试上限: 防止无限循环
                c = tuple(sorted(random.sample(range(1, 34), 6)))
                if _check_hard(c):
                    continue
                if c in used_reds:
                    continue
                used_reds.add(c)
                blue = _pick_blue(blue_weights)
                tickets.append({"reds": list(c), "blue": blue})
                found = True
                break
            if not found:
                blue = _pick_blue(blue_weights)
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

def _generate_author_tickets(n=3, author_mode='zhang', soft=False, luck_mode='off',
                              max_overlap=None, five_period=False, pattern_rules=False,
                              liu_blue=False, cailele_blue=False, gongyi_blue=False,
                              wuming_blue=False, filter_config=None,
                              **filter_kwargs):
    """委托特定作者生成红球, 蓝球+出票逻辑复用本模块."""
    from server.db import load_draws
    data = load_draws()

    # 蓝球准备 (同主路径)
    blue_candidates = set(range(1, 17))
    blue_methods_active = []
    if liu_blue:
        blue_methods_active.append(("刘大军", _liu_dajun_candidates))
    if cailele_blue:
        blue_methods_active.append(("彩乐乐", _cailele_candidates))
    if gongyi_blue:
        blue_methods_active.append(("公益时报", _gongyi_candidates))
    if wuming_blue:
        blue_methods_active.append(("吴明", _wuming_candidates))
    if blue_methods_active:
        inter = set(range(1, 17))
        union = set()
        for _, fn in blue_methods_active:
            cands = fn()
            if cands:
                inter &= cands
                union |= cands
        blue_candidates = inter if inter else union

    blue_weights = _blue_freq_weights()
    if blue_candidates and len(blue_candidates) < 16:
        w = 1.0 / len(blue_candidates)
        blue_weights = [0.0] * 16
        for b in blue_candidates:
            blue_weights[b - 1] = w
    if five_period:
        fpb = _five_period_boost()
        blue_weights = [blue_weights[i] * fpb[i] for i in range(16)]

    # 调用作者模块生成红球
    author_tickets = []
    try:
        if author_mode == 'zhang':
            from ml.zhang_weiming import generate_weihao
            result = generate_weihao(data, n_tickets=n)
            author_tickets = result.get("tickets", []) if isinstance(result, dict) else []
        elif author_mode == 'li_zhilin':
            from ml.li_zhilin import generate_tickets as lz_generate
            result = lz_generate(data, n_tickets=n)
            author_tickets = result.get("tickets", []) if isinstance(result, dict) else []
        elif author_mode == 'peng':
            from ml.peng_hao import generate_tickets as ph_generate
            result = ph_generate(data, n=n)
            author_tickets = result.get("tickets", []) if isinstance(result, dict) else []
        elif author_mode == 'jiang_jialin':
            from ml.jiang_jialin import generate_tickets as jj_generate
            result = jj_generate(data, n=n)
            author_tickets = result.get("tickets", []) if isinstance(result, dict) else []
    except Exception:
        pass

    # 将作者红球组装成标准ticket格式
    tickets = []
    used_reds = set()
    used_blues = set()
    for entry in author_tickets[:n]:
        if isinstance(entry, dict):
            reds = tuple(sorted(entry.get("reds", entry.get("numbers", []))))
        elif isinstance(entry, (list, tuple)):
            reds = tuple(sorted(entry))
        else:
            continue
        if len(reds) != 6 or reds in used_reds:
            continue
        blue = _pick_unique_blue(blue_weights, used_blues)
        used_reds.add(reds)
        used_blues.add(blue)
        tickets.append({"reds": list(reds), "blue": blue})

    # 不足 → 补随机
    while len(tickets) < n:
        reds = tuple(sorted(random.sample(range(1, 34), 6)))
        if reds not in used_reds:
            blue = _pick_unique_blue(blue_weights, used_blues)
            used_reds.add(reds)
            used_blues.add(blue)
            tickets.append({"reds": list(reds), "blue": blue})

    algo = f"Author-{author_mode}" + ("+Soft" if soft else "")
    _log_prediction(tickets, source=f"micro+{algo}")
    return {
        "ok": True,
        "algorithm": algo,
        "tickets": tickets, "budget": n,
        "cost_rmb": n * TICKET_PRICE,
        "pool_size": None, "pool_valid_reds": None,
        "soft_filter": False, "soft_excluded": 0,
        "luck_mode": luck_mode,
        "luck_window": LUCK_WINDOW if luck_mode != 'off' else None,
        "rule_status": _state.rule_status,
        "ev_estimate": {"ev_per_draw": round(RANDOM_SINGLE_EV * n, 2),
                        "cost_per_draw": n * TICKET_PRICE},
    }


def _generate_fallback_tickets(n, luck_mode='off', max_overlap=None, five_period=False, pattern_rules=False,
                                filter_config: 'FilterConfig | None' = None,
                                block9_killed=None, peng_channels=None,
                                omission_ratios=None,
                                color_filter=False, block9_filter=False,
                                spread_filter=False, ac_filter=False,
                                peng_channel_filter=False,
                                gap_filter=False, omission_filter=False,
                                coincidence_filter=False):
    """随机生成+过滤: 不经池, 直接random.sample+排序+过过滤. 秒级响应."""
    if filter_config is not None:
        fk = filter_config.as_kwargs()
        color_filter = fk['color_filter']
        block9_filter = fk['block9_filter']
        spread_filter = fk['spread_filter']
        ac_filter = fk['ac_filter']
        peng_channel_filter = fk['peng_channel_filter']
        gap_filter = fk['gap_filter']
        omission_filter = fk['omission_filter']
        coincidence_filter = fk['coincidence_filter']
    blue_weights = _blue_freq_weights()
    if five_period:
        fpb = _five_period_boost()
        blue_weights = [blue_weights[i] * fpb[i] for i in range(16)]
    if pattern_rules:
        ppb = _pattern_blue_boost()
        blue_weights = [blue_weights[i] * ppb[i] for i in range(16)]

    if luck_mode == 'pure':
        if not _state.calibrated:
            _calibrate_luck_blue_mix()
        _, blue_luck = _compute_luck_position_weights()
        blue_weights = _luck_blended_blue_weights(blue_weights, blue_luck)

    # 预加载通道/遗漏比 (与主路径共享)
    if peng_channel_filter and peng_channels is None:
        from server.db import load_draws
        peng_channels = _get_peng_channels(load_draws())
    if omission_filter and omission_ratios is None:
        from server.db import load_draws
        omission_ratios = _get_omission_ratios(load_draws())

    tickets = []
    used_reds = set()
    for _ in range(n):
        for _ in range(500):  # [工程] 重试上限: 防止无限循环
            c = tuple(sorted(random.sample(range(1, 34), 6)))
            ticket = _try_one_ticket(c, used_reds, tickets, blue_weights,
                max_overlap=max_overlap, color_filter=color_filter,
                block9_filter=block9_filter, block9_killed=block9_killed,
                spread_filter=spread_filter, ac_filter=ac_filter,
                peng_channel_filter=peng_channel_filter, peng_channels=peng_channels,
                gap_filter=gap_filter, omission_filter=omission_filter,
                omission_ratios=omission_ratios, coincidence_filter=coincidence_filter)
            if ticket:
                tickets.append(ticket)
                break
        else:
            tickets.append({"reds": [1, 2, 3, 4, 5, 6],
                           "blue": _pick_blue(blue_weights)})
    _log_prediction(tickets, source="micro+Fallback")
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
# Tier 2: 贪心多样性选注 (数学: Jaccard距离最大化, 非书本算法)
# ────────────────────────────────────────────────────────

def _jaccard_distance(a, b):
    """Jaccard距离: 1 - |a∩b| / |a∪b|.
    对6元素集合: |a∪b| = 12 - |a∩b|, 范围6-12.
    返回 1.0(完全不相交) 到 0.0(完全相同)."""
    inter = len(set(a) & set(b))
    return 1.0 - inter / (12.0 - inter)


def _build_candidate_pool(pool_size, valid_reds, n_combos, exclude, used_reds, rng=random):
    """从_state.valid_reds随机采样pool_size个候选组合.
    返回 [(idx, reds_tuple), ...], 排除已过滤和已使用的组合."""
    candidates = []
    seen = set()
    attempts = 0
    # [工程] 最大尝试次数: pool_size×10保底, 5000是硬上限(防止大池子时无限循环)
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
                             pool_size=1000,  # [工程] 随机采样池大小: C(33,6)=1.1M中取1000做多样性优化
                             blue_weights=None,
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
        blue = _pick_blue(blue_weights)
        used_blues.add(blue)
        tickets.append({"reds": list(reds), "blue": blue})

    return tickets, used_idx, used_reds, used_blues


# ────────────────────────────────────────────────────────
# P0: 百万军中选大将 (蒋加林, 2001) — 回测排名选注
# ────────────────────────────────────────────────────────

def _backtest_rank_tickets(n, valid_reds, n_combos, min_hits=3):
    """回测排名: 枚举全量有效池, 选历史命中频率最高的N注.

    算法: 蒋加林《抓住500万》第二绝招, 2001.
    枚举全量组合(非采样), 对所有历史期数逐一兑奖.
    """
    from server.db import load_draws
    data = load_draws()
    period_reds = [{r[1], r[2], r[3], r[4], r[5], r[6]} for r in data]

    # 全量枚举 (原书做法: 数百万组合逐一兑奖)
    all_hits = []
    for idx in range(n_combos):
        base = idx * 6
        reds_set = set(valid_reds[base:base + 6])
        hit_periods = sum(1 for pr in period_reds if len(reds_set & pr) >= min_hits)
        all_hits.append(hit_periods)

    # 取top-N
    ranked = sorted(enumerate(all_hits), key=lambda x: -x[1])
    selected = ranked[:n]
    result = []
    for idx, hits in selected:
        base = idx * 6
        result.append((idx, tuple(valid_reds[base:base + 6]), hits))
    return result


def _get_peng_channels(data):
    """计算6个红球位置的彭浩通道范围 [彭浩 2010 Ch5 §3].

    使用MA9+MA18双通道交集, 返回 [(lower, upper), ...] 每位置.
    结果缓存在模块级, 数据不变时不重新计算.
    """
    global _state
    if _state.peng_channels is not None and _state.peng_channels_data_count == len(data):
        return _state.peng_channels

    from ml.peng_hao import compute_channel_dual
    channels = []
    for pos in range(6):
        ch = compute_channel_dual(data, pos)
        lower = max(1, int(ch.get("lower", 1)))
        upper = min(33, int(ch.get("upper", 33)))
        channels.append((lower, upper))
    _state.peng_channels = channels
    _state.peng_channels_data_count = len(data)
    return channels


def _get_omission_ratios(data):
    """计算所有红球的遗漏比 [彩天使 2009 p90].

    OR = 当前遗漏期数 / 理论出现周期(RED_PERIOD=5.5)
    OR > 5 → 极寒带, 应避开 [文献] 原书p108
    """
    global _state
    if _state.omission_ratios is not None and _state.omission_data_count == len(data):
        return _state.omission_ratios

    # 计算每个号码最近一次出现距今多少期
    last_seen = {}
    for i in range(len(data) - 1, -1, -1):
        for n in data[i][1:7]:
            if n not in last_seen:
                last_seen[n] = len(data) - 1 - i

    ratios = {}
    for n in range(1, 34):
        gap = last_seen.get(n, len(data))
        ratios[n] = gap / _RED_PERIOD

    _state.omission_ratios = ratios
    _state.omission_data_count = len(data)
    return ratios


def _try_one_ticket(reds, used_reds, tickets, blue_weights,
                     max_overlap=None, **filter_kwargs):
    """过滤+重叠检查, 通过则返回ticket并更新used_reds, 否则返回None.
    
    消除 _generate_fallback_tickets 与主路径重复的过滤逻辑.
    """
    if reds in used_reds:
        return None
    if not _passes_red_filters(reds, **filter_kwargs):
        return None
    if max_overlap is not None and tickets:
        if any(len(set(reds) & set(t["reds"])) > max_overlap for t in tickets):
            return None
    used_reds.add(reds)
    return {"reds": list(reds), "blue": _pick_blue(blue_weights)}


def _passes_red_filters(reds, color_filter=False, block9_filter=False,
                         block9_killed=None, spread_filter=False, ac_filter=False,
                         peng_channel_filter=False, peng_channels=None,
                         gap_filter=False, omission_filter=False,
                         omission_ratios=None, coincidence_filter=False):
    """检查可选红色球过滤规则. 返回 True=通过(保留), False=被过滤(跳过).

    包含: 吴长坤三色分解(Ch4§6), 方块9杀号(Ch6§1), 李相春散度(p55-57), AC值(p60-62),
          彭浩通道过滤(Ch5§3), 间距分析(2004 p114-119), 遗漏比过滤(2009 p90),
          刘大军重合码(2010 p21-22).
    """
    if color_filter:
        rs = set(reds)
        if not (rs & COLOR_RED and rs & COLOR_BLUE and rs & COLOR_GREEN):
            return False
    if block9_filter and block9_killed and set(reds) & block9_killed:
        return False
    if spread_filter:
        sp = compute_spread(list(reds), 33)
        if sp < 3 or sp > 10:
            return False
    if ac_filter:
        if compute_ac_value(list(reds)) < 6:
            return False
    # [文献] 李相春2004 p114-119: 间距分析 — 最大间距+平均间距约束
    # [数据] 近500期校准: avg_gap P5=3.2 P95=6.2 → [4,7]; max_gap P5=5 P95=17
    if gap_filter:
        s = sorted(reds)
        max_gap = max(s[i+1] - s[i] for i in range(5))
        avg_gap = (s[-1] - s[0]) / 5.0
        if max_gap < 5 or max_gap > 17:
            return False
        if avg_gap < 4 or avg_gap > 7:
            return False

    # [文献] 刘大军2010 p21-22: 重合码过滤 — 红球尾数需覆盖{1,3,6,8}
    if coincidence_filter:
        tails = {n % 10 for n in reds}
        if not (tails & COINCIDENCE_TAILS):
            return False

    # [文献] 彩天使2009 p90/p108: 遗漏比过滤 — 排除含极寒号码的组合
    if omission_filter and omission_ratios:
        for n in reds:
            if omission_ratios.get(n, 0) > 5:  # [文献] 原书p108: OR>5=极寒带
                return False

    # [彭浩 2010 Ch5 §3] 6位置通道过滤: 每红球必须落在对应位置的MA通道内
    if peng_channel_filter and peng_channels:
        s = sorted(reds)
        for pos in range(6):
            lower, upper = peng_channels[pos]
            if s[pos] < lower or s[pos] > upper:
                return False
    return True


# ────────────────────────────────────────────────────────
# 规则状态
# ────────────────────────────────────────────────────────

def rule_status():
    if _state.valid_reds is None:
        _build_pool()
    return _state.rule_status


# ────────────────────────────────────────────────────────
# 预测日志自动记录
# ────────────────────────────────────────────────────────

def _log_prediction(tickets, source="micro_portfolio"):
    """自动记录生成的号码到 prediction_log 表 (非阻塞, 失败静默)."""
    if not tickets:
        return
    try:
        from server import db
        data = db.load_draws()
        if not data:
            return
        period = data[-1][0] + 1  # 下一期
        entries = []
        for t in tickets:
            reds = sorted(t.get("reds", []))
            if len(reds) != 6:
                continue
            entries.append({
                "period": period, "source": source,
                "reds_json": ",".join(str(x) for x in reds),
                "blue": t.get("blue", 0),
                "pred_r1": reds[0], "pred_r2": reds[1], "pred_r3": reds[2],
                "pred_r4": reds[3], "pred_r5": reds[4], "pred_r6": reds[5],
            })
        if entries:
            db.save_prediction_log(entries)
    except Exception:
        pass  # 日志失败不影响核心流程


# ────────────────────────────────────────────────────────
# 主入口: 生成号码
# ────────────────────────────────────────────────────────

def generate_tickets(n=3, soft=False, luck_mode='off', max_overlap=None,
                     diversity_mode=None, five_period=False, backtest_rank=False,
                     param_filter=False, pattern_rules=False,
                     liu_blue=False, cailele_blue=False, gongyi_blue=False, wuming_blue=False,
                     author_mode=None,
                     filter_config: 'FilterConfig | None' = None,
                     # ── 以下为向后兼容的独立参数, filter_config 优先 ──
                     color_filter=False, block9_filter=False,
                     spread_filter=False, ac_filter=False,
                     peng_channel_filter=False,
                     gap_filter=False,
                     omission_filter=False,
                     coincidence_filter=False,
                     wuming_clockwise=False, wuming_bsd=False):
    """生成号码主入口.

    Args:
        n: 注数 (1-3)
        soft: 是否启用软过滤 (位置软过滤)
        luck_mode:
          'off'   → 纯池采样
          'pure'  → 位置加权独立抽号 (「幸运开奖」按钮)
        max_overlap: 注间最大共享红球数, None=不限制. 0=完全不相交, 2=默认推荐
        diversity_mode: None=随机采样, 'greedy'=贪心max-min Jaccard
        five_period: 五期断蓝法加权 (刘大军, 2011)
        author_mode: 委托特定作者 ('zhang'|'li_zhilin'|'peng'|'jiang_jialin')

    Returns:
        dict with tickets, algorithm, filter info, ev_estimate.
    """
    # ── filter_config 优先于独立参数 ──
    if filter_config is not None:
        fk = filter_config.as_kwargs()
        color_filter = fk['color_filter']
        block9_filter = fk['block9_filter']
        spread_filter = fk['spread_filter']
        ac_filter = fk['ac_filter']
        peng_channel_filter = fk['peng_channel_filter']
        gap_filter = fk['gap_filter']
        omission_filter = fk['omission_filter']
        coincidence_filter = fk['coincidence_filter']
        wuming_clockwise = fk['wuming_clockwise']
        wuming_bsd = fk['wuming_bsd']

    # ── 作者模式: 委托特定作者生成红球, 蓝球+过滤仍走本模块 ──
    if author_mode:
        return _generate_author_tickets(
            n=n, author_mode=author_mode, soft=soft, luck_mode=luck_mode,
            max_overlap=max_overlap, five_period=five_period,
            pattern_rules=pattern_rules,
            liu_blue=liu_blue, cailele_blue=cailele_blue,
            gongyi_blue=gongyi_blue, wuming_blue=wuming_blue,
            filter_config=filter_config,
            color_filter=color_filter, block9_filter=block9_filter,
            spread_filter=spread_filter, ac_filter=ac_filter,
            peng_channel_filter=peng_channel_filter,
            gap_filter=gap_filter, omission_filter=omission_filter,
            coincidence_filter=coincidence_filter,
            wuming_clockwise=wuming_clockwise, wuming_bsd=wuming_bsd)

    # ── pure 模式走独立路径 ──
    if luck_mode == 'pure':
        return _generate_luck_tickets(n=n, max_overlap=max_overlap, five_period=five_period, pattern_rules=pattern_rules)

    # ── off: 池采样 ──
    global _state
    from server.db import load_draws

    # 吴长坤 2010: 方块9杀号 — 上期空方块本期继续杀
    block9_killed = _block9_kill(load_draws()) if block9_filter else set()

    # [工程] 只在贪心/回测模式下建池(需全量枚举C(33,6)),
    # 普通采样直接用回退路径(随机生成6数+过滤), 秒级响应.
    needs_pool = (diversity_mode == 'greedy' or backtest_rank or soft or param_filter)
    if needs_pool:
        try:
            if _state.valid_reds is None or len(load_draws()) != _state.past_count:
                _build_pool()
        except Exception:
            _state.valid_reds = None
            _state.soft_excluded = None

    if _state.valid_reds is None:
        return _generate_fallback_tickets(n, luck_mode=luck_mode, max_overlap=max_overlap,
            five_period=five_period, pattern_rules=pattern_rules,
            color_filter=color_filter, block9_filter=block9_filter,
            block9_killed=block9_killed,
            spread_filter=spread_filter, ac_filter=ac_filter,
            peng_channel_filter=peng_channel_filter,
            gap_filter=gap_filter,
            omission_filter=omission_filter,
            coincidence_filter=coincidence_filter)

    exclude = _state.soft_excluded if soft else set()
    if param_filter and _state.param_excluded is not None:
        exclude = exclude | _state.param_excluded
    n_combos = len(_state.valid_reds) // 6
    if n_combos * 6 != len(_state.valid_reds) or n_combos == 0:
        return _generate_fallback_tickets(n, luck_mode=luck_mode, max_overlap=max_overlap,
            five_period=five_period, pattern_rules=pattern_rules,
            color_filter=color_filter, block9_filter=block9_filter,
            block9_killed=block9_killed,
            spread_filter=spread_filter, ac_filter=ac_filter,
            peng_channel_filter=peng_channel_filter,
            gap_filter=gap_filter,
            omission_filter=omission_filter,
            coincidence_filter=coincidence_filter)

    # 蓝球: 各作者方法独立候选集投票 → 并集
    blue_candidates = set(range(1, 17))
    blue_methods_active = []
    if liu_blue:
        blue_methods_active.append(("刘大军蓝球", _liu_dajun_candidates))
    if cailele_blue:
        blue_methods_active.append(("彩乐乐蓝球", _cailele_candidates))
    if gongyi_blue:
        blue_methods_active.append(("公益时报蓝球", _gongyi_candidates))
    if wuming_blue:
        blue_methods_active.append(("吴明蓝球", _wuming_candidates))
    if wuming_clockwise:
        blue_methods_active.append(("顺时针法", _wuming_clockwise_candidates))
    if wuming_bsd:
        blue_methods_active.append(("大小单双尾", _wuming_bsd_candidates))

    if blue_methods_active:
        # 独立投票: 先取交集(全票通过), 交集为空→退到并集(至少一票)
        inter = set(range(1, 17))
        union = set()
        for name, fn in blue_methods_active:
            cands = fn()
            if cands:
                inter &= cands
                union |= cands
        blue_candidates = inter if inter else union
    elif five_period:
        cands = _five_period_candidates()
        if cands:
            blue_candidates = cands
    elif pattern_rules:
        cands = _pattern_blue_candidates()
        if cands:
            blue_candidates = cands

    # 蓝球权重: 候选集内均权, 集外零权
    # 方法负责筛选, 不干涉内部偏好; 历史频率不参与二次加权
    blue_weights = [0.0] * 16
    if blue_candidates:
        w = 1.0 / len(blue_candidates)
        for b in blue_candidates:
            blue_weights[b - 1] = w
    else:
        blue_weights = _blue_freq_weights()  # 无候选→回退频率

    used_idx = set()
    used_reds = set()
    tickets = []
    n_original = n  # 保存原始注数用于返回dict

    # Tier 2: 贪心多样性选注 — 先尝试从候选池贪心选, 不足则走随机采样
    if diversity_mode == 'greedy':
        greedy = _greedy_diverse_tickets(
            n, _state.valid_reds, n_combos, exclude,
            pool_size=1000, blue_weights=blue_weights,
        )
        if greedy is not None:
            tickets, used_idx, used_reds, _ = greedy
            if len(tickets) >= n_original:
                pool_size = (n_combos - len(exclude)) * 16
                algo = "Pool-Sampling+Greedy"
                if soft: algo += "+Soft"
                _log_prediction(tickets, source=f"micro+{algo}")
                return {
                    "ok": True, "algorithm": algo,
                    "tickets": tickets, "budget": n_original,
                    "cost_rmb": n_original * TICKET_PRICE,
                    "pool_size": pool_size,
                    "pool_valid_reds": n_combos - len(exclude),
                    "soft_filter": soft, "soft_excluded": len(exclude),
                    "luck_mode": luck_mode,
                    "luck_window": LUCK_WINDOW if luck_mode != 'off' else None,
                    "rule_status": _state.rule_status,
                    "ev_estimate": {"ev_per_draw": round(RANDOM_SINGLE_EV * n_original, 2),
                                    "cost_per_draw": n_original * TICKET_PRICE},
                }
            # 贪心未产足 → 剩余 n 走随机采样
            n = n_original - len(tickets)
        else:
            n = n_original

    # Tier P0: 百万军中选大将 — 回测排名选注
    elif backtest_rank:
        ranked = _backtest_rank_tickets(n_original, _state.valid_reds, n_combos)
        if ranked and len(ranked) >= n_original:
            for idx, reds, hits in ranked[:n_original]:
                used_idx.add(idx)
                used_reds.add(reds)
                blue = _pick_blue(blue_weights)
                tickets.append({"reds": list(reds), "blue": blue})

            pool_size = (n_combos - len(exclude)) * 16
            algo = "Pool-Sampling+Backtest"
            if soft: algo += "+Soft"
            if luck_mode == 'blend': algo += "+Luck"
            return {
                "ok": True, "algorithm": algo,
                "tickets": tickets, "budget": n_original,
                "cost_rmb": n_original * TICKET_PRICE,
                "pool_size": pool_size,
                "pool_valid_reds": n_combos - len(exclude),
                "soft_filter": soft, "soft_excluded": len(exclude),
                "luck_mode": luck_mode,
                "luck_window": LUCK_WINDOW if luck_mode != 'off' else None,
                "rule_status": _state.rule_status,
                "ev_estimate": {"ev_per_draw": round(RANDOM_SINGLE_EV * n_original, 2),
                                "cost_per_draw": n_original * TICKET_PRICE},
            }
            _log_prediction(tickets, source=f"micro+{algo}")
        else:
            n = n_original
    else:
        n = n_original

    # [彭浩 2010 Ch5 §3] 通道过滤: 预计算6位置通道范围
    # [彩天使 2009 p90] 遗漏比: 预计算所有号码遗漏比
    peng_channels = None
    omission_ratios = None
    if peng_channel_filter or omission_filter:
        from server.db import load_draws
        data = load_draws()
        if peng_channel_filter:
            peng_channels = _get_peng_channels(data)
        if omission_filter:
            omission_ratios = _get_omission_ratios(data)


    def _pick_combo_idx():
        return random.randrange(n_combos)

    for _ in range(n):
        for _ in range(500):  # [工程] 重试上限: 防止无限循环
            idx = _pick_combo_idx()
            if idx in used_idx:
                continue
            base = idx * 6
            assert base + 6 <= len(_state.valid_reds), \
                f"idx={idx}, base={base}, len={len(_state.valid_reds)}, 越界"
            reds = tuple(_state.valid_reds[base:base + 6])
            if reds in exclude:
                continue
            if reds in used_reds:
                continue

            # 可选红色球过滤 + 注间分散 → _try_one_ticket
            ticket = _try_one_ticket(reds, used_reds, tickets, blue_weights,
                max_overlap=max_overlap, color_filter=color_filter,
                block9_filter=block9_filter, block9_killed=block9_killed,
                spread_filter=spread_filter, ac_filter=ac_filter,
                peng_channel_filter=peng_channel_filter,
                peng_channels=peng_channels,
                gap_filter=gap_filter,
                omission_filter=omission_filter,
                omission_ratios=omission_ratios,
                coincidence_filter=coincidence_filter)
            if ticket:
                used_idx.add(idx)
                tickets.append(ticket)
                break
        else:
            for _ in range(500):  # [工程] 重试上限: 防止无限循环
                c = tuple(sorted(random.sample(range(1, 34), 6)))
                if c in used_reds:
                    continue
                ticket = _try_one_ticket(c, used_reds, tickets, blue_weights,
                    max_overlap=max_overlap, color_filter=color_filter,
                    block9_filter=block9_filter, block9_killed=block9_killed,
                    spread_filter=spread_filter, ac_filter=ac_filter,
                    peng_channel_filter=peng_channel_filter,
                    peng_channels=peng_channels,
                    gap_filter=gap_filter,
                    omission_filter=omission_filter,
                    omission_ratios=omission_ratios,
                    coincidence_filter=coincidence_filter)
                if ticket:
                    tickets.append(ticket)
                    break
            else:
                blue = _pick_blue(blue_weights)
                tickets.append({"reds": [1, 2, 3, 4, 5, 6], "blue": blue})


    pool_size = (n_combos - len(exclude)) * 16
    algo = "Pool-Sampling" + ("+Soft" if soft else "")
    _log_prediction(tickets, source=f"micro+{algo}")
    return {
        "ok": True,
        "algorithm": algo,
        "tickets": tickets, "budget": n_original,
        "cost_rmb": n_original * TICKET_PRICE,
        "pool_size": pool_size,
        "pool_valid_reds": n_combos - len(exclude),
        "soft_filter": soft, "soft_excluded": len(exclude),
        "luck_mode": luck_mode,
        "luck_window": LUCK_WINDOW if luck_mode != 'off' else None,
        "rule_status": _state.rule_status,
        "ev_estimate": {"ev_per_draw": round(RANDOM_SINGLE_EV * n_original, 2),
                        "cost_per_draw": n_original * TICKET_PRICE},
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
    used = set()
    tickets = []
    for r in raw:
        blue = _pick_unique_blue(blue_weights, used)
        used.add(blue)
        tickets.append({"reds": r, "blue": blue})

    return {
        "ok": True,
        "algorithm": f"聚合覆盖(v={cover['v']},t={t})",
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
