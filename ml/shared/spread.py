"""散度分析 — 号码集中/分散程度的数学度量.

作者: 李相春《彩票小额投注必读》(2003) p55-57, 彩天使《手把手教你玩彩票》(2004) p48-50
"""

from typing import List, Tuple


def compute_spread(numbers: List[int], pool_size: int = 33) -> float:
    """计算一组号码的散度.

    定义 (2003 p55-56):
      散度 = max_{i ∈ 所有号码} min_{j ∈ 选中号码} |i - j|

    含义:
      - 散度越大 → 号码越集中 (有大片空白区)
      - 散度越小 → 号码越分散 (均匀覆盖)

    参考值 (双色球33选6):
      - 理论范围: 3-27
      - 常见值: 5-9 (80%)
      - >10罕见

    [数学] 散度严格定义于 李相春2003 p55-56, 彩天使2004 p48
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

    [文献] spread_range默认(3,10)基于 李相春2003 p56 统计:
      36期中散度>10仅2次, <3仅理论存在
    """
    return [c for c in candidates
            if spread_range[0] <= compute_spread(c, pool_size) <= spread_range[1]]
