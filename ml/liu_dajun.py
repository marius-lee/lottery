"""刘大军 算法实现 — 三书聚合 (2010+2011+2014)

  2010《双色球擒号绝技》(第二版): 定尾选号法, 重合码 {1,3,6,8}
  2011《双色球蓝球中奖绝技》: 三效应, 冷热判定, 五期断蓝 (已在 micro_portfolio)
  2014《双色球终极战法》(第二版): 断区转换法 (已在 zone_break)
"""

import math
from typing import List, Dict, Tuple
from collections import Counter


# [文献] 刘大军 2010 p21-22: 重合码 — 大中小∩012路交叉验证
COINCIDENCE_TAILS = {1, 3, 6, 8}

# [文献] 刘大军 2010 p22: 6大类指标定义
TAIL_GROUP_LARGE = {7, 8, 9}       # 大数
TAIL_GROUP_MEDIUM = {3, 4, 5, 6}   # 中数
TAIL_GROUP_SMALL = {0, 1, 2}       # 小数
TAIL_GROUP_0LU = {0, 3, 6, 9}      # 012路-0路
TAIL_GROUP_1LU = {1, 4, 7}         # 012路-1路
TAIL_GROUP_2LU = {2, 5, 8}         # 012路-2路

POSITION_NAMES = ["第1位(最小)", "第2位", "第3位", "第4位", "第5位", "第6位(最大)"]


def position_tail_analysis(data: List, window: int = 50) -> Dict:
    """每位置尾数分布分析 [刘大军 2010 Ch2].

    对最近N期数据, 统计6个位置上0-9尾数的出现频率,
    返回每位置的尾数热度分布和预测建议.

    Args:
        data: [[period, r1..r6, blue], ...]
        window: 分析窗口期数 (默认50期)

    Returns:
        positions: [{pos_name, tails: [{digit, count, pct, hot}, ...], recommendation}, ...]
        coincidence_check: 当前期尾数覆盖情况
    """
    if len(data) < window:
        window = len(data)
    recent = data[-window:]

    positions = []
    for pos in range(6):
        tail_counts = Counter()
        for row in recent:
            n = row[pos + 1]  # red balls are at index 1-6
            tail_counts[n % 10] += 1

        tails = []
        total = window
        for digit in range(10):
            cnt = tail_counts.get(digit, 0)
            pct = cnt / total * 100
            # [文献] 刘大军 2010 p23: 7期内>2次=热, =2次=温, <2次=冷
            hot = "热" if cnt > total * 0.22 else ("温" if cnt > total * 0.08 else "冷")
            tails.append({"digit": digit, "count": cnt, "pct": round(pct, 1), "hot": hot})

        # 推荐: 取热+温的尾数
        recommended = [t["digit"] for t in tails if t["hot"] in ("热", "温")]

        # [文献] 刘大军 2010: 重合码交集
        coincidence = [d for d in recommended if d in COINCIDENCE_TAILS]

        positions.append({
            "name": POSITION_NAMES[pos],
            "tails": tails,
            "recommended": recommended,
            "coincidence": coincidence,
        })

    # 当前期尾数覆盖情况
    latest = data[-1] if data else None
    coincidence_status = None
    if latest:
        latest_tails = {n % 10 for n in latest[1:7]}
        has_coincidence = bool(latest_tails & COINCIDENCE_TAILS)
        coincidence_status = {
            "tails": sorted(latest_tails),
            "has_coincidence": has_coincidence,
            "matched": sorted(latest_tails & COINCIDENCE_TAILS) if has_coincidence else [],
        }

    return {
        "positions": positions,
        "coincidence_status": coincidence_status,
        "window": window,
        "total_periods": len(data),
    }


def check_coincidence(reds: List[int]) -> bool:
    """检查红球尾数是否覆盖重合码 {1,3,6,8} [刘大军 2010 p21-22]."""
    return bool({n % 10 for n in reds} & COINCIDENCE_TAILS)
