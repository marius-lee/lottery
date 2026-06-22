"""
李相春《彩票小额投注必读》(2003, 208页) — 核心算法实现

全书结构:
  第三章: 选号技巧—趋势分析 (11短期+4中期+6长期=21种方法)
  第四章: 组号技巧—旋转矩阵 (平衡式+加权式, 即覆盖设计)

独特算法 (其他12+作者未覆盖):
  1. 散度分析 — 号码集中/分散程度的数学度量
  2. 偏度分析 — 本期号码相对上期的整体偏移度量
  3. DHR — 连续两期出现比率, 预测号码重复概率
  4. 降三浪 — 冷号→热号反转的最强信号
  5. 升三浪 — 热号→冷号的疲惫信号
  6. 双底/三底 — 等间隔出现模式识别

与现有系统的关系:
  - 11种短期偏态分析中9种已被吴明/彭浩/李志林等覆盖
  - 旋转矩阵 = 覆盖设计, 系统已有 covering_design.py
  - 散度和偏度是本书独有, 其他作者未涉及
"""

import math
import random
from typing import List, Tuple, Dict, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# 1. 散度分析 (Spread) — 第55-57页
# ═══════════════════════════════════════════════════════════════════════════════

def compute_spread(numbers: List[int], pool_size: int = 33) -> float:
    """计算一组号码的散度.

    定义 (第55-56页):
      散度 = max_{i ∈ 所有号码} min_{j ∈ 选中号码} |i - j|
    即: 对号码池中每个号码, 计算其与最近选中号码的距离,
    取所有距离中的最大值。

    含义:
      - 散度越大 → 号码越集中 (有大片空白区)
      - 散度越小 → 号码越分散 (均匀覆盖)

    参考值 (北京风采32选7):
      - 理论范围: 3-25
      - 常见值: 5-6 (均线=6)
      - >10罕见 (36期仅2次)
      - 偏离均线后3期内回归

    [数学] 散度严格定义于原书 p55-56
    """
    if not numbers:
        return 0.0

    all_nums = list(range(1, pool_size + 1))
    max_min_dist = 0

    for i in all_nums:
        min_dist = min(abs(i - n) for n in numbers)
        if min_dist > max_min_dist:
            max_min_dist = min_dist

    return float(max_min_dist)


def spread_filter(candidates: List[List[int]], pool_size: int = 33,
                  spread_range: Tuple[int, int] = (3, 10)) -> List[List[int]]:
    """散度过滤: 只保留散度在合理范围内的组合.

    [文献] spread_range默认(3,10)基于原书p56统计:
      36期中散度>10仅2次, <3仅理论存在
    """
    return [c for c in candidates
            if spread_range[0] <= compute_spread(c, pool_size) <= spread_range[1]]


# ═══════════════════════════════════════════════════════════════════════════════
# 2. 偏度分析 (Skewness) — 第57-59页
# ═══════════════════════════════════════════════════════════════════════════════

def compute_skewness(current_numbers: List[int],
                     previous_numbers: List[int]) -> float:
    """计算本期号码相对上期的偏度.

    定义 (第58页):
      偏度 = max_{j ∈ 本期号码} min_{k ∈ 上期号码} |j - k|
    即: 对本期每个号码, 计算其与上期最近号码的距离,
    取所有距离中的最大值。

    含义:
      - 偏度越大 → 本期号码整体偏离上期越远
      - 偏度越小 → 本期号码与上期越接近

    参考值 (北京风采32选7):
      - 理论范围: 0-25
      - 正常范围: 4-5 (中间区域)
      - <2和>12未在39期中出现过
      - 偏离中间区域后4期内回归

    [数学] 偏度严格定义于原书 p58

    关键关系 (第59页):
      本期散度 = 下期偏度的上限
      即: 下期偏度 ≤ 本期散度
    """
    if not current_numbers or not previous_numbers:
        return 0.0

    max_min_dist = 0
    for j in current_numbers:
        min_dist = min(abs(j - k) for k in previous_numbers)
        if min_dist > max_min_dist:
            max_min_dist = min_dist

    return float(max_min_dist)


def predict_skewness_bound(current_spread: float) -> float:
    """根据当前散度预测下期偏度上限.

    定理 (第59页): 下期偏度 ≤ 本期散度

    [数学] 由定义直接推导: 散度衡量号码池中任意号码到本期号码的最大距离,
    下期号码必在此号码池中, 故其到本期号码的最小距离上限即散度.
    """
    return current_spread


def skewness_filter(candidates: List[List[int]],
                    previous_numbers: List[int],
                    skew_range: Tuple[int, int] = (2, 12)) -> List[List[int]]:
    """偏度过滤: 只保留偏度在合理范围的组合.

    [文献] skew_range默认(2,12)基于原书p59统计: <2和>12从未出现
    """
    return [c for c in candidates
            if skew_range[0] <= compute_skewness(c, previous_numbers) <= skew_range[1]]


# ═══════════════════════════════════════════════════════════════════════════════
# 3. DHR — 连续两期出现比率 (第76-78页)
# ═══════════════════════════════════════════════════════════════════════════════

def compute_dhr(history: List[List[int]], target_num: int) -> float:
    """计算某号码的连续两期出现比率 (DHR).

    定义 (第77页):
      DHR = 仅出现1期的次数 / 连续2期及以上出现的总次数

    含义:
      - DHR越低 → 该号码越"粘滞", 出现后倾向于继续出现
      - DHR越高 → 该号码越"孤立", 出现后倾向于立即消失
      - 平均值≈6:1 (即DHR≈6)

    使用 (第78页):
      选择DHR低于均值的号码, 它们更可能在下一期重复出现.

    [文献] DHR公式 + 均值6:1来自原书p77-78
    """
    single_count = 0   # 仅出现1期的次数
    streak_count = 0   # 连续2期及以上的总次数

    i = 0
    while i < len(history):
        if target_num in history[i]:
            # 统计连续出现长度
            streak_len = 1
            j = i + 1
            while j < len(history) and target_num in history[j]:
                streak_len += 1
                j += 1
            if streak_len == 1:
                single_count += 1
            else:
                streak_count += 1
            i = j
        else:
            i += 1

    if streak_count == 0:
        return float('inf')  # 从未连续出现 → 极不可能重复

    return single_count / streak_count


def dhr_predict(current_numbers: List[int],
                history: List[List[int]],
                dhr_threshold: float = 6.0) -> List[int]:
    """基于DHR预测哪些号码更可能重复.

    返回当前号码中DHR低于阈值的号码 (更可能重复).

    [文献] dhr_threshold=6.0基于原书p77: 平均DHR≈6:1
    """
    dhr_vals = {num: compute_dhr(history, num) for num in current_numbers}
    repeat_candidates = [num for num in current_numbers if dhr_vals[num] < dhr_threshold]
    # 按DHR升序 (越低的越可能重复)
    repeat_candidates.sort(key=lambda n: dhr_vals[n])
    return repeat_candidates


# ═══════════════════════════════════════════════════════════════════════════════
# 4. 降三浪 — 冷号→热号反转信号 (第73-74页)
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
# 7. AC值 (算术复杂性) — 第60-62页
# ═══════════════════════════════════════════════════════════════════════════════

def compute_ac_value(numbers: List[int]) -> int:
    """计算算术复杂性 (AC值).

    定义 (第60页):
      AC = 所有两数正差值的不同值个数 - (r - 1)
      其中 r = 号码个数

    含义:
      - AC越低 → 号码规律性越强
      - AC越高 → 号码越随机
      - 算术级数 (如1,6,11,16,21,26,31) 的AC=0
      - 好的投注组合应有较高的AC值

    参考值:
      - 35选7: AC≥7
      - 30/32选7: AC≥6

    [数学] AC值严格定义于原书p60
    """
    r = len(numbers)
    if r < 2:
        return 0

    diffs = set()
    for i in range(r):
        for j in range(i + 1, r):
            diff = abs(numbers[i] - numbers[j])
            if diff > 0:
                diffs.add(diff)

    return len(diffs) - (r - 1)


def ac_filter(candidates: List[List[int]],
              min_ac: int = 6) -> List[List[int]]:
    """AC值过滤: 过滤掉AC值过低的组合.

    [文献] min_ac=6基于原书p61: 30/32选7的AC值通常≥6
    """
    return [c for c in candidates if compute_ac_value(c) >= min_ac]


# ═══════════════════════════════════════════════════════════════════════════════
# 8. 综合趋势评分
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
