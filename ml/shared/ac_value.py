"""AC值 (算术复杂性) 分析.

作者: 李相春《彩票小额投注必读》(2003) p60-62, 刘大军《双色球擒号绝技》(2010) p74-92
"""

from typing import List


def compute_ac_value(numbers: List[int]) -> int:
    """计算算术复杂性 (AC值).

    定义 (2003 p60):
      AC = 所有两数正差值的不同值个数 - (R - 1)
      其中 R = 号码个数 (双色球R=6)

    含义:
      - AC越低 → 号码规律性越强
      - AC越高 → 号码越随机
      - 算术级数 (如1,6,11,16,21,26,31) 的AC=0

    参考值 (双色球33选6):
      - 范围: 0-10
      - 最常见: 6-9 (82%)
      - 建议: AC ≥ 6

    [数学] 李相春2003 p60, 刘大军2010 p74
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


def ac_filter(candidates: List[List[int]], min_ac: int = 6) -> List[List[int]]:
    """AC值过滤: 过滤掉AC值过低的组合.

    [文献] 李相春2003 p61, 刘大军2010: AC≥6
    """
    return [c for c in candidates if compute_ac_value(c) >= min_ac]
