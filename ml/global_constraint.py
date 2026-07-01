"""全局约束过滤 — 注级结构校验 (Stage 2)

理论基础:
  - Stage 1 (信号融合) 给每个号码独立打分，完全不关心一注六码的全局结构。
  - 历史数据显示某些结构特征高度集中，偏离这些结构=极低概率：
    和值 90-130, 跨度 18-28, 奇偶比 2:4 至 4:2, 尾数 4-6, 质数 1-3
  - Stage 2 做后置过滤：采样六码 → 校验 → 不通过则重采。

用法:
  from ml.global_constraint import validate_combo, constraint_summary
  ok, violations = validate_combo([3, 7, 12, 18, 25, 31])
"""
from collections import Counter
import math


# ═══ 历史基线 (基于 2000+ 期双色球数据) ═══

# 和值分布: ~N(102, 27²), 取 90-130 覆盖约 65%
SUM_MIN = 70
SUM_MAX = 140

# 跨度 (max - min): 典型 15-29
SPAN_MIN = 11
SPAN_MAX = 31

# 奇偶比: 3:3 (~35%), 2:4 (~24%), 4:2 (~23%)
ODD_MIN = 2
ODD_MAX = 4

# 质数个数 (2,3,5,7,11,13,17,19,23,29,31): 通常 1-3
PRIMES = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31}

# 尾数 (个位数) 种类: 通常 4-6
TAIL_MIN = 4
TAIL_MAX = 6

# 大号 (≥17) 个数: 通常 2-4
BIG_MIN = 1
BIG_MAX = 5

# AC值 (离散系数): 通常 6-10
AC_MIN = 5
AC_MAX = 10


def _ac_value(reds):
    """计算双色球 AC值 (离散系数)."""
    s = sorted(reds)
    diffs = set()
    for i in range(6):
        for j in range(i + 1, 6):
            diffs.add(s[j] - s[i])
    return len(diffs) - 5


def _strictness(kwargs):
    """返回约束严格程度: 'loose' | 'normal' | 'strict'."""
    level = kwargs.get('constraint_level', 'normal')
    return level if level in ('loose', 'normal', 'strict') else 'normal'


def validate_combo(reds, **kwargs):
    """校验一注六码是否符合全局结构约束.

    Args:
        reds: 6个红球号码 (任意顺序)
        constraint_level: 'loose' | 'normal' | 'strict' (默认 normal)

    Returns:
        (ok: bool, violations: list of str)
    """
    s = sorted(reds)
    level = _strictness(kwargs)
    violations = []

    total = sum(s)
    if level == 'strict':
        if total < SUM_MIN or total > SUM_MAX:
            violations.append(f"sum={total}")
    elif level == 'normal':
        if total < 60 or total > 160:
            violations.append(f"sum={total}")
    # loose: no sum check

    span = s[-1] - s[0]
    if span < SPAN_MIN or span > SPAN_MAX:
        violations.append(f"span={span}")

    odd_count = sum(1 for n in s if n % 2 == 1)
    if odd_count < ODD_MIN or odd_count > ODD_MAX:
        violations.append(f"odd/even={odd_count}/{6-odd_count}")

    prime_count = sum(1 for n in s if n in PRIMES)
    if level == 'strict' and (prime_count < 1 or prime_count > 3):
        violations.append(f"primes={prime_count}")

    big_count = sum(1 for n in s if n >= 17)
    if big_count < BIG_MIN or big_count > BIG_MAX:
        violations.append(f"big/small={big_count}/{6-big_count}")

    tails = len({n % 10 for n in s})
    if tails < TAIL_MIN or tails > TAIL_MAX:
        violations.append(f"tails={tails}")

    ac = _ac_value(s)
    if ac < AC_MIN or ac > AC_MAX:
        violations.append(f"ac={ac}")

    return len(violations) == 0, violations


def constraint_summary(data):
    """从历史数据统计约束的实际分布，返回诊断信息."""
    if not data:
        return {"error": "no_data"}

    sums, spans, odds, primes, tails, acs, bigs = [], [], [], [], [], [], []
    for row in data:
        reds = row[1:7]
        s = sorted(reds)
        sums.append(sum(s))
        spans.append(s[-1] - s[0])
        odds.append(sum(1 for n in s if n % 2 == 1))
        primes.append(sum(1 for n in s if n in PRIMES))
        tails.append(len({n % 10 for n in s}))
        acs.append(_ac_value(s))
        bigs.append(sum(1 for n in s if n >= 17))

    def _stats(vals):
        n = len(vals)
        mean = sum(vals) / n
        var = sum((x - mean) ** 2 for x in vals) / (n - 1) if n > 1 else 0
        sd = var ** 0.5
        return {"mean": round(mean, 2), "sd": round(sd, 2),
                "min": min(vals), "max": max(vals)}

    return {
        "n_draws": len(data),
        "sum": _stats(sums),
        "span": _stats(spans),
        "odd_count": _stats(odds),
        "prime_count": _stats(primes),
        "tail_count": _stats(tails),
        "ac_value": _stats(acs),
        "big_count": _stats(bigs),
    }
