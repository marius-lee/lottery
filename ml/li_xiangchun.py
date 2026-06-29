"""
李相春《彩票小额投注必读》(2003, 208页) — 核心算法实现

全书结构:
  第三章: 选号技巧—趋势分析 (11短期+4中期+6长期=21种方法)
  第四章: 组号技巧—旋转矩阵 (平衡式+加权式, 即覆盖设计)

独有算法:
  1. 降三浪 — 冷号→热号反转的最强信号
  2. 升三浪 — 热号→冷号的疲惫信号
  3. 双底/三底 — 等间隔出现模式识别
  4. 热门转冷门 — 活跃期结束判断
  5. 冷热号偏态 — 间隔统计
  6. 间距分析 — 相邻红球间距统计

共享算法 (已提取至 ml.shared):
  - 散度 [李相春 2003, 彩天使 2004] → ml.shared.spread
  - 偏度 [李相春 2003, 彩天使 2004] → ml.shared.skewness
  - AC值 [李相春 2003, 刘大军 2010] → ml.shared.ac_value
  - DHR  [李相春 2003, 彩天使 2004] → ml.shared.dhr
"""

import math
import random
from typing import List, Tuple, Dict, Optional

from ml.shared.spread import compute_spread
from ml.shared.skewness import compute_skewness
from ml.shared.ac_value import compute_ac_value
from ml.shared.dhr import compute_dhr


# ═══════════════════════════════════════════════════════════════════════════════
# 1. 降三浪 — 冷号→热号反转信号 (第73-74页)
# ═══════════════════════════════════════════════════════════════════════════════

def detect_jiang_sanlang(intervals: List[int]) -> bool:
    """检测降三浪模式 — 冷号→热号的最强反转信号.

    定义 (第73-74页):
      降三浪: 间隔逐次递减
        第一次间隔: ≥10期
        第二次间隔: 4-6期
        第三次间隔: 0-3期
      含义: 号码活跃期来临, 近期将频繁出现.

    这是书中描述的"趋势反转的最强信号" (第74页).

    [文献] 三浪阈值来自原书p60-61

    注意: intervals是最近三次出现的间隔列表, 按时间顺序排列
          需要至少3个间隔才能检测
    """
    if len(intervals) < 3:
        return False

    # 取最近三次间隔
    recent = intervals[-3:]
    g1, g2, g3 = recent[0], recent[1], recent[2]

    return (g1 >= 10) and (4 <= g2 <= 6) and (0 <= g3 <= 3)


def detect_sheng_sanlang(intervals: List[int]) -> bool:
    """检测升三浪模式 — 热号→冷号的疲惫信号.

    定义 (第73页):
      升三浪: 间隔逐次递增
        第一次间隔: 0-3期
        第二次间隔: 4-6期
        第三次间隔: ≥10期
      含义: 号码越跑越累, 需要更长的休息时间.

    策略: 除非出现趋势反转信号, 否则不宜追买.

    [文献] 三浪阈值来自原书p60
    """
    if len(intervals) < 3:
        return False

    recent = intervals[-3:]
    g1, g2, g3 = recent[0], recent[1], recent[2]

    return (0 <= g1 <= 3) and (4 <= g2 <= 6) and (g3 >= 10)


def extract_intervals(history: List[List[int]], target_num: int) -> List[int]:
    """从历史数据中提取某号码的各次出现间隔."""
    appearances = []
    for i, draw in enumerate(history):
        if target_num in draw:
            appearances.append(i)

    if len(appearances) < 2:
        return []

    intervals = []
    for i in range(1, len(appearances)):
        intervals.append(appearances[i] - appearances[i - 1] - 1)

    return intervals


def sanlang_predict(history: List[List[int]],
                    pool_size: int = 33) -> Dict[str, List[int]]:
    """基于三浪分析预测号码状态.

    返回:
      - 'jiang': 降三浪信号 (即将活跃) 的号码
      - 'sheng': 升三浪信号 (即将沉寂) 的号码
      - 'hot_end': 热门转冷门 (活跃期已结束) 的号码
    """
    result = {'jiang': [], 'sheng': [], 'hot_end': []}

    for num in range(1, pool_size + 1):
        intervals = extract_intervals(history, num)
        if len(intervals) >= 3:
            if detect_jiang_sanlang(intervals):
                result['jiang'].append(num)
            if detect_sheng_sanlang(intervals):
                result['sheng'].append(num)
        if len(intervals) >= 6:
            if detect_hot_to_cold(intervals):
                result['hot_end'].append(num)

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 5. 双底/三底 — 等间隔模式 (第74-75页)
# ═══════════════════════════════════════════════════════════════════════════════

def detect_hot_to_cold(intervals: List[int]) -> bool:
    """检测热门转冷门规则 (第74页).

    定义 (第74页):
      如果某个号码以不超过1期的间隔连续出现了5次左右,
      然后消失了8期左右, 那么可以认为该号码的活跃期已经结束。

    具体: 最近一次出现后已消失≥8期, 且在此之前连续5次出现的间隔都≤1期.

    [文献] 连续5次≤1期+消失8期 阈值来自原书p74
    """
    if len(intervals) < 6:
        return False

    # 最近一次间隔 ≥ 8 (当前正在消失中)
    if intervals[-1] < 8:
        return False

    # 在此之前连续5次出现间隔都 ≤ 1 (热度持续)
    prev_5 = intervals[-6:-1]  # 倒数第6到倒数第2个间隔, 共5个
    return all(g <= 1 for g in prev_5)


def detect_shuangdi(intervals: List[int]) -> Optional[int]:
    """检测双底模式 — 预测下一次出现时间.

    定义 (第74-75页):
      双底: 某号码间隔5-8期出现后, 再隔相同期数(±1)再次出现.
      三底: 三个相同或接近的间隔.

    返回: 预测的下次出现间隔 (None表示未检测到).

    [文献] 间隔范围5-8来自原书p61, ±1容差来自p62
    """
    if len(intervals) < 2:
        return None

    # 检查最近两次间隔是否形成双底
    last = intervals[-1]
    prev = intervals[-2]

    if 5 <= last <= 8 and abs(last - prev) <= 1:
        return last  # 预测下次以相同间隔出现

    return None


def detect_sandi(intervals: List[int]) -> Optional[int]:
    """检测三底模式.

    定义 (第75页): 三个相同(或接近)的间隔期.

    [文献] ±1容差来自原书p62
    """
    if len(intervals) < 3:
        return None

    g1, g2, g3 = intervals[-3], intervals[-2], intervals[-1]
    avg_gap = (g1 + g2 + g3) / 3

    # 检查三者是否彼此接近 (都在均值±1范围内)
    if all(abs(g - avg_gap) <= 1 for g in [g1, g2, g3]):
        return round(avg_gap)

    return None


def bottom_predict(history: List[List[int]],
                   pool_size: int = 33) -> Dict[int, int]:
    """基于双底/三底预测号码下次出现时间.

    返回: {号码: 预测间隔} 字典.
    """
    predictions = {}

    for num in range(1, pool_size + 1):
        intervals = extract_intervals(history, num)
        if len(intervals) < 2:
            continue

        # 三底优先 (更可靠)
        gap = detect_sandi(intervals)
        if gap is not None:
            predictions[num] = gap
            continue

        # 其次双底
        gap = detect_shuangdi(intervals)
        if gap is not None:
            predictions[num] = gap

    return predictions


# ═══════════════════════════════════════════════════════════════════════════════
# 6. 冷热号偏态 — 含间隔统计 (第50-55页)
# ═══════════════════════════════════════════════════════════════════════════════

def compute_hot_cold_stats(history: List[List[int]],
                           pool_size: int = 33,
                           hot_threshold: int = 4) -> Dict:
    """冷热号偏态统计 (第50-53页).

    定义:
      间隔 = 自上次出现到本次出现的期数
      间隔 < 4 → 热门
      间隔 ≥ 4 → 冷门

    关键指标:
      - 间隔<4的号码个数: 理论均值=4
      - 总间隔: 以36选7为例均值≈30

    偏移过多 → 预期均值回归.

    [文献] hot_threshold=4, 总间隔均值=30 来自原书p52-53
    """
    # 计算每个号码最近一次间隔
    intervals = {}

    for num in range(1, pool_size + 1):
        # 从最近往前找
        found = False
        for i in range(len(history) - 1, -1, -1):
            if num in history[i]:
                intervals[num] = len(history) - 1 - i
                found = True
                break
        if not found:
            intervals[num] = len(history)  # 从未出现

    hot_count = sum(1 for v in intervals.values() if v < hot_threshold)
    total_interval = sum(intervals.values())

    return {
        'hot_count': hot_count,
        'total_interval': total_interval,
        'hot_threshold': hot_threshold,
        'expected_hot_count': 4,       # [文献] 原书p53
        'expected_total_interval': 30,  # [文献] 原书p53 (36选7)
        'intervals': intervals,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 7. 综合趋势评分
# ═══════════════════════════════════════════════════════════════════════════════

def trend_score(history: List[List[int]],
                candidate_reds: List[int],
                candidate_blue: int = None,
                pool_size: int = 33) -> Dict:
    """李相春趋势分析综合评分.

    组合以下信号:
      - 散度是否在正常范围 (3-10)
      - 偏度是否在正常范围 (2-12)
      - 红球中降三浪信号数
      - 红球是否避开升三浪号码

    返回评分及各维度得分.
    """
    scores = {}

    # 1. 散度评分 (0-1)
    spread = compute_spread(candidate_reds, pool_size)
    spread_ok = 3 <= spread <= 10  # [文献] 原书p56
    scores['spread'] = {'value': spread, 'ok': spread_ok, 'score': 1.0 if spread_ok else 0.0}

    # 2. 偏度评分 (0-1)
    if len(history) >= 1:
        prev_numbers = history[-1]
        skew = compute_skewness(candidate_reds, prev_numbers)
        skew_ok = 2 <= skew <= 12  # [文献] 原书p59
        scores['skewness'] = {'value': skew, 'ok': skew_ok, 'score': 1.0 if skew_ok else 0.0}
    else:
        scores['skewness'] = {'value': None, 'ok': True, 'score': 0.5}

    # 3. 三浪评分 (0-1)
    sanlang = sanlang_predict(history, pool_size)
    jiang_nums = set(sanlang['jiang'])
    sheng_nums = set(sanlang['sheng'])

    jiang_hits = len(set(candidate_reds) & jiang_nums)
    sheng_hits = len(set(candidate_reds) & sheng_nums)
    sanlang_score = 0.5 + 0.1 * jiang_hits - 0.2 * sheng_hits
    sanlang_score = max(0.0, min(1.0, sanlang_score))
    scores['sanlang'] = {
        'jiang_hits': jiang_hits,
        'sheng_hits': sheng_hits,
        'jiang_nums': sorted(jiang_nums),
        'sheng_nums': sorted(sheng_nums),
        'score': sanlang_score
    }

    # 4. AC值评分 (0-1)
    ac = compute_ac_value(candidate_reds)
    ac_ok = ac >= 6  # [文献] 原书p61
    scores['ac_value'] = {'value': ac, 'ok': ac_ok, 'score': 1.0 if ac_ok else 0.5}

    # 综合
    weights = {'spread': 0.3, 'skewness': 0.25, 'sanlang': 0.25, 'ac_value': 0.2}
    total = sum(weights[k] * scores[k]['score'] for k in weights)
    scores['total'] = total

    return scores


# ═══════════════════════════════════════════════════════════════════════════════
# 8. 统一信号仪表盘 (2003+2004+2009 三书聚合)
# ═══════════════════════════════════════════════════════════════════════════════

_RED_PERIOD = 33.0 / 6.0  # [文献] 彩天使2009 p89: 红球理论周期=5.5


def dashboard(history: List[List[int]], pool_size: int = 33) -> Dict:
    """李相春三书全部信号聚合 — 一次调用返回所有指标.

    返回:
      sanlang: 降三浪/升三浪/热门转冷门
      dhr_sticky: DHR最低的5个 (最可能重复)
      dhr_avoid: DHR最高的5个 (最不可能重复)
      shuangdi: 双底/三底预测
      spread_trend: 散度趋势 (当前值+均线+区间)
      skewness_trend: 偏度趋势 (当前值+均线+区间)
      omission_ratios: 所有号码遗漏比
    """
    # ── 三浪信号 ──
    sanlang = sanlang_predict(history, pool_size)

    # ── DHR (所有号码, 取Top5/Bottom5) ──
    all_dhr = {}
    for num in range(1, pool_size + 1):
        dhr = compute_dhr(history, num)
        if dhr != float('inf'):
            all_dhr[num] = round(dhr, 2)
    dhr_sorted = sorted(all_dhr.items(), key=lambda x: x[1])
    dhr_sticky = [{"num": n, "dhr": d} for n, d in dhr_sorted[:5] if d < 10]
    dhr_avoid = [{"num": n, "dhr": d} for n, d in dhr_sorted[-5:] if d > 0]

    # ── 双底/三底预测 ──
    bottom_preds = []
    for num in range(1, pool_size + 1):
        intervals = extract_intervals(history, num)
        if len(intervals) >= 3:
            gap = detect_sandi(intervals)
            if gap is None:
                gap = detect_shuangdi(intervals)
        elif len(intervals) >= 2:
            gap = detect_shuangdi(intervals)
        else:
            gap = None
        if gap is not None:
            bottom_preds.append({"num": num, "predicted_gap": gap,
                                 "type": "三底" if (len(intervals) >= 3 and detect_sandi(intervals) is not None) else "双底"})

    # ── 散度/偏度趋势 ──
    if len(history) >= 1:
        latest_reds = history[-1][1:7] if len(history[-1]) >= 7 else history[-1]
        current_spread = compute_spread(latest_reds, pool_size)
        spread_trend = {
            "current": current_spread,
            "mean": 6,  # [文献] 2003 p56
            "normal_range": [5, 9],  # [文献] 2004 p109: SSQ散度常见5-9
            "zone": "normal" if 5 <= current_spread <= 9 else ("high" if current_spread > 9 else "low"),
            "note": f"均线=6, 偏离后≤3期回归" if abs(current_spread - 6) > 2 else "在正常范围"
        }
    else:
        spread_trend = None

    if len(history) >= 2:
        prev_reds = history[-2][1:7] if len(history[-2]) >= 7 else history[-2]
        curr_reds = history[-1][1:7] if len(history[-1]) >= 7 else history[-1]
        current_skew = compute_skewness(curr_reds, prev_reds)
        skewness_trend = {
            "current": current_skew,
            "normal_range": [3, 7],  # [文献] 2004 p113: SSQ偏度常见3-7
            "zone": "normal" if 3 <= current_skew <= 7 else ("high" if current_skew > 7 else "low"),
            "bound": current_spread if spread_trend else None,  # [定理] 下期偏度≤本期散度
            "note": f"正常偏度3-7" if 3 <= current_skew <= 7 else f"偏离正常范围"
        }
    else:
        skewness_trend = {"current": None, "normal_range": [3, 7], "zone": "unknown"}

    # ── 遗漏比 ──
    ratios = {}
    for num in range(1, pool_size + 1):
        gap = 0
        for i in range(len(history) - 1, -1, -1):
            if num in history[i]:
                gap = len(history) - 1 - i
                break
        else:
            gap = len(history)
        ratios[num] = round(gap / _RED_PERIOD, 1)

    return {
        "sanlang": {"jiang": sanlang["jiang"], "sheng": sanlang["sheng"],
                     "hot_end": sanlang["hot_end"]},
        "dhr_sticky": dhr_sticky,
        "dhr_avoid": dhr_avoid,
        "shuangdi": bottom_preds[:5],
        "spread_trend": spread_trend,
        "skewness_trend": skewness_trend,
        "omission_ratios": ratios,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 出口: generate_tickets
# ═══════════════════════════════════════════════════════════════════════════════

def generate_tickets(history: List[List[int]],
                     pool_size: int = 33,
                     n_tickets: int = 5,
                     blue_pool: List[int] = None) -> Dict:
    """李相春风格生成号码.

    策略 (源自本书第3章):
      1. 用趋势分析过滤候选红球
      2. 应用散度+偏度+AC值约束
      3. 避开升三浪号码, 优先降三浪号码
      4. 蓝球用余数偏态 (除6余数)

    注意: 本书重点在选号(趋势分析)和组号(旋转矩阵),
    旋转矩阵=覆盖设计已由其他模块实现.
    """
    results = {
        'algorithm': '李相春 趋势分析 (2003)',
        'tickets': [],
        'stats': {}
    }

    # 1. 三浪预筛选
    sanlang = sanlang_predict(history, pool_size)

    avoid_nums = set(sanlang['sheng'])
    prefer_nums = set(sanlang['jiang'])

    # 2. 构建候选池
    all_nums = set(range(1, pool_size + 1)) - avoid_nums
    candidates = sorted(all_nums)

    results['stats']['avoid_sheng'] = sorted(avoid_nums)
    results['stats']['prefer_jiang'] = sorted(prefer_nums)
    results['stats']['candidate_pool_size'] = len(candidates)

    # 3. 生成红球 (简化版: 非旋转矩阵)
    rng = random.Random()
    # [工程] 用最后期号作为种子增加可复现性
    seed = len(history) * 1000 + sum(history[-1]) if history else 42
    rng.seed(seed)

    tickets = []
    max_attempts = n_tickets * 500
    attempts = 0

    while len(tickets) < n_tickets and attempts < max_attempts:
        attempts += 1

        # 优先从降三浪号码中选2-3个
        n_jiang = min(len(prefer_nums), rng.randint(2, 3))
        reds = set(rng.sample(sorted(prefer_nums), n_jiang)) if n_jiang >= 2 else set()

        # 其余从候选池补足
        remaining = sorted(all_nums - reds)
        needed = 6 - len(reds)
        if needed > 0 and len(remaining) >= needed:
            reds.update(rng.sample(remaining, needed))

        if len(reds) != 6:
            continue

        reds = sorted(reds)

        # 过滤: 散度+偏度+AC
        spread = compute_spread(reds, pool_size)
        if not (3 <= spread <= 10):
            continue

        ac = compute_ac_value(reds)
        if ac < 6:
            continue

        if history:
            skew = compute_skewness(reds, history[-1])
            if not (2 <= skew <= 12):
                continue

        # 蓝球
        if blue_pool:
            blue = rng.choice(blue_pool)
        else:
            blue = rng.randint(1, 16)

        tickets.append({'reds': reds, 'blue': blue})

    results['tickets'] = tickets
    results['stats']['attempts'] = attempts
    results['stats']['spread_filter'] = True
    results['stats']['ac_filter'] = True
    results['stats']['skewness_filter'] = True

    return results
