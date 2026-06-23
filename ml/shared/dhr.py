"""DHR — 连续两期出现比率.

作者: 李相春《彩票小额投注必读》(2003) p76-78, 彩天使《手把手教你玩彩票》(2004) p80-83
"""

from typing import List


def compute_dhr(history: List[List[int]], target_num: int) -> float:
    """计算某号码的连续两期出现比率 (DHR).

    定义 (2003 p77):
      DHR = 仅出现1期的次数 / 连续2期及以上出现的总次数

    含义:
      - DHR越低 → 该号码越"粘滞", 出现后倾向于继续出现
      - DHR越高 → 该号码越"孤立", 出现后倾向于立即消失
      - 平均值≈6:1 (即DHR≈6)

    [文献] DHR公式 + 均值6:1 来自 李相春2003 p77-78, 彩天使2004 p80
    """
    single_count = 0
    streak_count = 0

    i = 0
    while i < len(history):
        if target_num in history[i]:
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
        return float('inf')

    return single_count / streak_count


def dhr_predict(current_numbers: List[int],
                history: List[List[int]],
                dhr_threshold: float = 6.0) -> List[int]:
    """基于DHR预测哪些号码更可能重复.

    返回当前号码中DHR低于阈值的号码 (更可能重复).

    [文献] dhr_threshold=6.0 基于 李相春2003 p77: 平均DHR≈6:1
    """
    dhr_vals = {num: compute_dhr(history, num) for num in current_numbers}
    repeat_candidates = [num for num in current_numbers if dhr_vals[num] < dhr_threshold]
    repeat_candidates.sort(key=lambda n: dhr_vals[n])
    return repeat_candidates
