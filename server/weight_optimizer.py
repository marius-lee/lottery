"""权重优化器 v4 — James-Stein收缩 + 滑动窗口 + 策略族上限"""
from collections import defaultdict
from server import db
from ml.ssq_constants import RED_EXPECTED_HITS, BLUE_HIT_PROB

# ── 本地参数 (原 ssq_constants 全局常量, 现仅此模块使用) ──

RED_BASELINE = RED_EXPECTED_HITS   # [数学] 超几何均值 36/33=1.0909
BLUE_BASELINE = BLUE_HIT_PROB      # [数学] 1/16 = 0.0625
DISCOUNT = 0.95                    # [文献] RiskMetrics 1996 EWMA衰减
MIN_WEIGHT = 0.3                   # [数据] 策略权重下限
MAX_WEIGHT = 1.6                   # [数据] 策略权重上限
FAMILY_CAP = 0.34                  # [数据] 单族总权重上限

# 策略族分组 (来源: 代码审查中识别的策略相关性分析)
FAMILIES = {
    "G1_频率族": ["频率", "遗漏", "趋势", "温度", "Pólya", "指数优化"],
    "G2_模式族": ["均匀", "间隔", "黄金分割", "同尾", "相似期", "位置"],
    "G3_结构族": ["共现", "马尔可夫蓝", "混沌"],
    "G4_ML族":   ["AI集成"],
    "G5_高级族": ["Copula", "贝叶斯", "熵值", "EVT", "RMT"],
}

# 冷启动种子: 已废弃的ML策略不再预填充 (原 COLD_START_WEIGHTS)
# 未知策略由 _default_weights 返回1.0, 或由 FAMILIES 覆盖的 _all_known 供给基线
COLD_START_SEEDS = {}


def compute_all_weights():
    """计算所有策略的红球+蓝球权重，应用族上限。返回 (red_weights, blue_weights)"""
    db.init_performance_log()
    records = db.load_performance_log(limit=500)

    if not records:
        return _default_weights(), _default_weights()

    # 获取最新期号作为 current
    max_period = max(r["period"] for r in records)

    # 按策略分组
    strat_data = defaultdict(lambda: {"red_hits": [], "blue_hits": [], "ages": []})
    for r in records:
        age = max_period - r["period"]
        strat_data[r["strategy"]]["red_hits"].append(r["red_hits"])
        strat_data[r["strategy"]]["blue_hits"].append(r["blue_hit"])
        strat_data[r["strategy"]]["ages"].append(age)

    # 冷启动种子
    for name, (n_seed, avg_seed) in COLD_START_SEEDS.items():
        if name not in strat_data:
            strat_data[name]["red_hits"] = [avg_seed] * n_seed
            strat_data[name]["blue_hits"] = [0.06] * n_seed
            strat_data[name]["ages"] = list(range(10, 10 + n_seed))

    # 确保所有已知策略都有条目
    all_known = set()
    for members in FAMILIES.values():
        all_known.update(members)
    for name in all_known:
        if name not in strat_data:
            strat_data[name]["red_hits"] = [RED_BASELINE / 6] * 5
            strat_data[name]["blue_hits"] = [BLUE_BASELINE] * 5
            strat_data[name]["ages"] = list(range(20, 25))

    # James-Stein 红球收缩
    red_weights = _james_stein_shrink(strat_data, "red_hits", RED_BASELINE)
    blue_weights = _james_stein_shrink(strat_data, "blue_hits", BLUE_BASELINE)

    # 族上限
    red_weights = _apply_family_cap(red_weights)
    blue_weights = _apply_family_cap(blue_weights)

    return red_weights, blue_weights


def _james_stein_shrink(strat_data, key, baseline):
    """James-Stein 收缩估计 → 权重"""
    # Step 1: 滑动窗口折扣统计
    stats = {}
    for name, data in strat_data.items():
        hits = data[key]
        ages = data["ages"]
        n_eff = sum(DISCOUNT ** a for a in ages)
        obs = sum((DISCOUNT ** a) * h for a, h in zip(ages, hits)) / max(n_eff, 0.01)
        stats[name] = {"n": n_eff, "obs": obs}

    n_list = [s["n"] for s in stats.values()]
    obs_list = [s["obs"] for s in stats.values()]
    total_n = sum(n_list)
    if total_n == 0:
        return {name: 1.0 for name in stats}

    # Step 2: 加权总均值
    grand = sum(n * o for n, o in zip(n_list, obs_list)) / total_n

    # Step 3: τ² 从数据估计 (Efron-Morris, 1975)
    # var_obs = τ² + mean(σ²/n_i), 所以 τ² = var_obs - mean(σ²/n_i)
    var_obs = sum(n * (o - grand) ** 2 for n, o in zip(n_list, obs_list)) / total_n
    # 二项分布方差: p(1-p)/n, p ≈ grand/6 ≈ 0.18
    p_hat = grand / 6
    avg_var = p_hat * (1 - p_hat) * 6 / max(1, total_n / len(n_list)) if grand > 0 else 0.15
    tau2 = max(0.001, var_obs - avg_var)  # 下限0.001防止除零

    # Step 4: 收缩
    weights = {}
    for name, s in stats.items():
        lam = tau2 / (tau2 + avg_var / max(s["n"], 0.5))
        shrunk = grand + (1 - lam) * (s["obs"] - grand)
        shrunk = max(0.5, min(shrunk, 2.5))
        w = shrunk / baseline
        weights[name] = round(max(MIN_WEIGHT, min(w, MAX_WEIGHT)), 4)

    return weights


def _apply_family_cap(weights):
    """应用策略族上限，单族总权重 ≤ 30%"""
    total = sum(weights.values())
    if total <= 0:
        return weights
    cap = total * FAMILY_CAP

    capped = dict(weights)
    for family, members in FAMILIES.items():
        fam_total = sum(capped.get(m, 0) for m in members)
        if fam_total > cap:
            scale = cap / fam_total
            for m in members:
                if m in capped:
                    capped[m] = round(capped[m] * scale, 4)

    return capped


def _default_weights():
    names = []
    for members in FAMILIES.values():
        names.extend(members)
    return {n: 1.0 for n in names}
