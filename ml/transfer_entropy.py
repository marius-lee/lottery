"""转移熵 — 检测上期号码→本期号码的条件概率偏移

对 33×33 对做二项检验, Bonferroni 校正后保留显著对。
"""
import math
from collections import Counter, defaultdict


def _binomial_pvalue(k, n, p):
    """二项分布右尾概率 P(X >= k | n, p)."""
    if n <= 0 or k <= 0:
        return 1.0
    mu = n * p
    sigma = math.sqrt(n * p * (1 - p))
    if sigma < 0.001:
        return 0.0 if k > mu else 1.0
    return 0.5 * math.erfc((k - mu) / (sigma * math.sqrt(2)))


def compute_transfer_entropy(data, window=300, min_period_gap=1, max_lag=3):
    """检测转移熵: 上期出现球 A → 下期球 B 出现概率是否显著偏高.

    Args:
        data: [[period, r1..r6, blue], ...]
        window: 回溯窗口
        min_period_gap: 最小期间隔 (1=相邻期)
        max_lag: 最大滞后 (检测 lag 1/2/3)

    Returns:
        significant_pairs: [(from_num, to_num, lag, obs_rate, baseline_rate, p_value), ...]
        diagnostics: dict
    """
    recent = data[-window:] if len(data) > window else data
    T = len(recent)

    # 构建期间→出现集合的映射
    period_sets = {}
    for row in recent:
        period_sets[row[0]] = set(row[1:7])

    # 排序期号
    periods = sorted(period_sets.keys())

    # 基线: 每个球的总体出现频率
    c = Counter()
    for row in recent:
        for r in row[1:7]:
            c[r] += 1
    baseline = {num: c[num] / T for num in range(1, 34)}

    # 转移计数: transfers[lag][from_num][to_num] = 次数
    transfers = {lag: defaultdict(lambda: defaultdict(int)) for lag in range(1, max_lag + 1)}
    # 条件总数: triggers[lag][from_num] = from_num 出现了多少次(在这些次中去看 lag 期后)
    triggers = {lag: Counter() for lag in range(1, max_lag + 1)}

    for i in range(len(periods) - max_lag):
        pi = periods[i]
        for lag in range(1, max_lag + 1):
            j = i + lag
            if j >= len(periods):
                break
            pj = periods[j]
            src_set = period_sets.get(pi, set())
            tgt_set = period_sets.get(pj, set())
            for a in src_set:
                triggers[lag][a] += 1
                for b in tgt_set:
                    transfers[lag][a][b] += 1

    # 检验每对
    N_TESTS = 33 * 32 * max_lag  # ~3168
    BONFERRONI = 0.05 / N_TESTS  # ~1.58e-05
    # 实际用稍宽松的 NOMINAL = 0.001 标记"弱信号", BONFERRONI 标记"强信号"

    significant = []
    for lag in range(1, max_lag + 1):
        for a in range(1, 34):
            n_a = triggers[lag].get(a, 0)
            if n_a < 10:  # 最少 10 次出现才有统计效力
                continue
            for b in range(1, 34):
                if a == b:
                    continue
                obs = transfers[lag][a].get(b, 0)
                if obs == 0:
                    continue
                p_b = baseline[b] * 6 / 33  # 每期 b 出现的基线概率
                # 注意: a 出现的期, 未来 lag 期后 b 出现的期望次数
                expected = n_a * p_b
                if obs <= expected:
                    continue
                p_val = _binomial_pvalue(obs, n_a, p_b)
                if p_val < 0.05:
                    significant.append((a, b, lag, round(obs / n_a, 4),
                                        round(p_b, 4), round(p_val, 6)))

    # 按 p 值排序
    significant.sort(key=lambda x: x[5])

    # Bonferroni 显著 vs 弱信号
    strong = [s for s in significant if s[5] < BONFERRONI]
    weak = [s for s in significant if BONFERRONI <= s[5] < 0.01]

    return significant, {
        "window": T,
        "total_tests": N_TESTS,
        "bonferroni_alpha": round(BONFERRONI, 8),
        "n_significant": len(significant),
        "n_strong": len(strong),
        "n_weak": len(weak),
        "strong_pairs": [(s[0], s[1], s[2], s[3], s[5]) for s in strong[:20]],
    }


# ═══ 蓝球转移熵 (蓝→蓝) ═══

def compute_blue_transfer_entropy(data, window=300, max_lag=5):
    """16×16 蓝球转移: 上期蓝球 A → 下期蓝球 B 的条件概率偏移.

    只有 256 对 (16×16), 不需要 Bonferroni, 直接用 nominal α=0.05
    再按 FDR (Benjamini-Hochberg) 控制假阳性.

    Returns:
        pairs: [(from_blue, to_blue, lag, obs_rate, baseline, p_value), ...]
        diagnostics: dict
    """
    recent = data[-window:] if len(data) > window else data
    # 提取蓝球序列
    blues = [row[7] for row in recent]
    T = len(blues)

    # 基线频率
    c = Counter(blues)
    baseline = {b: c[b] / T for b in range(1, 17)}

    # 转移计数: trans[lag][from_b][to_b]
    trans = {lag: {a: Counter() for a in range(1, 17)} for lag in range(1, max_lag + 1)}
    triggers = {lag: Counter() for lag in range(1, max_lag + 1)}

    for i in range(T - max_lag):
        a = blues[i]
        for lag in range(1, max_lag + 1):
            j = i + lag
            if j >= T:
                break
            b = blues[j]
            triggers[lag][a] += 1
            trans[lag][a][b] += 1

    # 二项检验所有对
    nominal = 1.0 / 16.0
    pairs = []
    for lag in range(1, max_lag + 1):
        for a in range(1, 17):
            n_a = triggers[lag].get(a, 0)
            if n_a < 10:
                continue
            for b in range(1, 17):
                obs = trans[lag][a].get(b, 0)
                expected = n_a * nominal
                if obs <= expected:
                    continue
                mu = n_a * nominal
                sigma = math.sqrt(n_a * nominal * (1 - nominal))
                if sigma < 0.001:
                    p_val = 0.0 if obs > mu else 1.0
                else:
                    z = (obs - mu) / sigma
                    p_val = 0.5 * math.erfc(z / math.sqrt(2))
                if p_val < 0.05:
                    pairs.append((a, b, lag, round(obs / n_a, 4),
                                  round(nominal, 4), round(p_val, 6)))

    # FDR 校正 (Benjamini-Hochberg)
    pairs.sort(key=lambda x: x[5])  # 按p值升序
    n = len(pairs)
    fdr_threshold = 0.1  # FDR 水平
    significant = []
    for rank, pair in enumerate(pairs, 1):
        bh_critical = (rank / n) * fdr_threshold
        if pair[5] <= bh_critical:
            significant.append(pair)
        else:
            break

    return significant, {
        "window": T,
        "total_tests": 16 * 16 * max_lag,
        "n_candidates": n,
        "n_fdr_significant": len(significant),
        "fdr_level": fdr_threshold,
        "top_pairs": [(a, b, lag, rate, round(p, 6))
                       for a, b, lag, rate, _, p in significant[:20]],
    }
