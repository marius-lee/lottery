"""偏度分析 — 本期号码相对上期的整体偏移度量.

作者: 李相春《彩票小额投注必读》(2003) p57-59, 彩天使《手把手教你玩彩票》(2004) p51-53
"""

from typing import List, Tuple


def compute_skewness(current_numbers: List[int],
                     previous_numbers: List[int]) -> float:
    """计算本期号码相对上期的偏度.

    定义 (2003 p58):
      偏度 = max_{j ∈ 本期号码} min_{k ∈ 上期号码} |j - k|

    含义:
      - 偏度越大 → 本期号码整体偏离上期越远
      - 偏度越小 → 本期号码与上期越接近

    参考值 (双色球33选6):
      - 理论范围: 0-27
      - 常见范围: 3-7 (77%)

    关键关系 (2003 p59): 本期散度 = 下期偏度的上限

    [数学] 偏度严格定义于 李相春2003 p58, 彩天使2004 p51
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

    定理: 下期偏度 ≤ 本期散度

    [数学] 李相春2003 p59: 由定义直接推导
    """
    return current_spread


def skewness_filter(candidates: List[List[int]],
                    previous_numbers: List[int],
                    skew_range: Tuple[int, int] = (2, 12)) -> List[List[int]]:
    """偏度过滤: 只保留偏度在合理范围的组合.

    [文献] 李相春2003 p59, 彩天使2004 p113: <2和>12从未出现
    """
    return [c for c in candidates
            if skew_range[0] <= compute_skewness(c, previous_numbers) <= skew_range[1]]
