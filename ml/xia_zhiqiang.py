"""夏志强 算法实现 — 测蓝法 + 选红法 (2013)

  2013 《彩票中奖就这几招》: Trick 46 减4加4测蓝法, Trick 65 计算与观察法
"""

from server.db import load_draws


def xia_sub4_add4_blue():
    """减4加4测蓝法 [夏志强 Trick 46, p64].

    |蓝_{t-1} - 蓝_t| ± 4 = 预测范围. 声称90%准确率.
    """
    data = load_draws()
    if len(data) < 3:
        return {"ok": False}
    b1 = data[-2][7]
    b2 = data[-1][7]
    base = abs(b1 - b2)
    lo = max(1, base - 4)
    hi = min(16, base + 4)
    candidates = list(range(lo, hi + 1))
    return {"ok": True, "candidates": candidates, "base": base,
            "range": [lo, hi], "source": "夏志强 Trick 46: 减4加4测蓝法"}


def xia_compute_reds():
    """计算与观察法选红号 [夏志强 Trick 65, p87].

    公式: (6红和 - 每红) / 每红 = 商(忽略余数), 商的尾数→下期候选.
    """
    data = load_draws()
    if len(data) < 1:
        return {"ok": False}
    reds = sorted(data[-1][1:7])
    total = sum(reds)
    candidates = set()
    for r in reds:
        if r == 0:
            continue
        q = (total - r) // r
        tail = q % 10
        for n in range(1, 34):
            if n % 10 == tail:
                candidates.add(n)
    return {"ok": True, "candidates": sorted(candidates), "count": len(candidates),
            "source": "夏志强 Trick 65: 计算与观察法"}
