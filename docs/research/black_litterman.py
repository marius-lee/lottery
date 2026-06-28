"""Black-Litterman融合 — 方法"观点" → 贝叶斯更新 → 偏置分布

算法基础 (2026-06-26):
  #4 Black-Litterman: 均匀先验 + 方法观点(ρ加权) → 后验分布

问题: ensemble_aggregator等权平均12方法, 好方法(ρ≈0.68)和坏方法(ρ≈0)权重一样.

方案: Black-Litterman框架:
  - 先验: Dirichlet后验 (纯频率信息的"均衡分布")
  - 观点: 每个方法的评分向量 = "我认为号码i的概率偏高/偏低"
  - 可信度: 方法的跨时间验证ρ = 观点有多可信
  - 后验: 可信度高的方法把分布拉得更远

数学 (简化版, 避免矩阵求逆):
  posterior_alpha[i] = prior_alpha[i] + Σ_m (confidence_m × view_m[i])
  其中 view_m[i] = method_score[i] - 1/33 (偏离均匀的程度)
      confidence_m = ρ_m (跨时间Spearman, 0~1)

这等价于: 可信的方法给Dirichlet"加伪计数", 不可信的方法几乎不影响.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import math


def _load_data():
    from server.db import load_draws
    return load_draws()


# ═══════════════════════════════════════════════════════════
# 方法可信度: 跨时间验证 recall@15
# ═══════════════════════════════════════════════════════════

def compute_method_confidences(data, k=15, window=50):
    """计算每个方法的跨时间验证 recall@K 作为可信度.

    返回 {method_name: confidence (0~1)}.
    """
    from ml.ensemble_aggregator import METHOD_REGISTRY, _init_registry
    _init_registry()

    if len(data) < window + 10:
        return {name: 0.5 for name in METHOD_REGISTRY}

    recalls = {name: [] for name in METHOD_REGISTRY}
    start = max(len(data) - window, window // 2)

    for i in range(start, len(data)):
        train = data[:i]
        actual = set(data[i][1:7])

        for name, fn in METHOD_REGISTRY.items():
            try:
                scores = fn(train)
                # top-K by score
                indexed = [(j, s) for j, s in enumerate(scores)]
                indexed.sort(key=lambda x: -x[1])
                top_k = set(idx + 1 for idx, _ in indexed[:k])
                hit = len(actual & top_k)
                recalls[name].append(hit / 6.0)
            except Exception:
                recalls[name].append(0.0)

    # 平均recall, 下限0.01
    result = {}
    for name, vals in recalls.items():
        result[name] = max(0.01, sum(vals) / len(vals)) if vals else 0.01

    return result


# ═══════════════════════════════════════════════════════════
# Black-Litterman融合
# ═══════════════════════════════════════════════════════════

def bl_fusion(data):
    """Black-Litterman: Dirichlet先验 + 方法观点(ρ加权) → 后验参数.

    Returns:
        posterior_alphas: [33] Dirichlet后验参数 (融合了所有方法观点)
        weights: {method_name: confidence} 每个方法的可信度
    """
    from ml.bias_engine import dirichlet_red_posterior
    from ml.ensemble_aggregator import METHOD_REGISTRY, _init_registry

    # 1. Dirichlet先验 (纯频率)
    prior_alphas = dirichlet_red_posterior(data)

    # 2. 方法可信度
    confidences = compute_method_confidences(data)

    # 3. 每个方法的"观点": 评分偏离均匀的程度
    _init_registry()
    method_scores = {}
    for name, fn in METHOD_REGISTRY.items():
        try:
            method_scores[name] = fn(data)
        except Exception:
            method_scores[name] = [0.5] * 33

    # 4. Black-Litterman融合
    # posterior_alpha[i] = prior_alpha[i] + scale × Σ_m (conf_m × view_m[i])
    # view_m[i] = score_m[i] - uniform (正=偏高, 负=偏低)
    # scale: 控制方法观点对先验的影响力 [工程: 先验强度≈12000, 观点加到~5%]
    posterior = list(prior_alphas)  # 拷贝先验
    uniform = 1.0 / 33
    total_confidence = sum(confidences.values()) or 1.0

    for name, scores in method_scores.items():
        conf = confidences.get(name, 0.01)
        norm_conf = conf / total_confidence  # 归一化
        for i in range(33):
            view = scores[i] - uniform  # 正=偏高, 负=偏低
            # [工程] scale=先验总数×5%: 观点相当于约600个伪观测
            scale = sum(prior_alphas) * 0.05
            posterior[i] += norm_conf * view * scale

    # 确保所有alpha为正
    posterior = [max(0.01, a) for a in posterior]

    return posterior, confidences


# ═══════════════════════════════════════════════════════════
# BL增强出号
# ═══════════════════════════════════════════════════════════

def bl_tickets(k=15, t=4, n=6):
    """Black-Litterman增强出号: BL融合后验 → Thompson → Gumbel-Max → 覆盖设计."""
    from ml.covering_design import greedy_t_covering
    from ml.bias_engine import thompson_sample, gumbel_max_topk, dirichlet_blue_posterior
    from ml.micro_portfolio import _pick_unique_blue
    from ml.ssq_constants import TICKET_PRICE, RANDOM_SINGLE_EV

    data = _load_data()
    if len(data) < 100:
        return {"ok": False, "msg": f"数据不足, 当前{len(data)}期"}

    # 1. Black-Litterman融合后验
    red_alphas, confidences = bl_fusion(data)
    blue_alphas = dirichlet_blue_posterior(data)

    # 2. Thompson采样
    theta = thompson_sample(red_alphas)

    # 3. Gumbel-Max选hot_numbers
    hot = gumbel_max_topk(theta, k=k)

    # 4. 覆盖设计
    best_tickets, best_cov = greedy_t_covering(hot, n, t)

    if not best_tickets:
        return {"ok": False, "msg": "覆盖设计失败"}

    # 5. 蓝球 (Thompson + Gumbel)
    blue_theta = thompson_sample(blue_alphas)
    used_blues = set()
    result_tickets = []
    for reds in best_tickets:
        candidates = [b for b in range(1, 17) if b not in used_blues]
        if not candidates:
            candidates = list(range(1, 17))
        cand_thetas = [blue_theta[b-1] if b in candidates else 0 for b in range(1, 17)]
        blue = gumbel_max_topk(cand_thetas, k=1)[0]
        used_blues.add(blue)
        result_tickets.append({"reds": reds, "blue": blue})

    # 6. 方法权重展示
    weight_display = {name: round(c, 4) for name, c in
                      sorted(confidences.items(), key=lambda x: -x[1])}

    return {
        "ok": True,
        "algorithm": f"BlackLitterman-v{k}-t{t}",
        "tickets": result_tickets,
        "budget": len(result_tickets),
        "cost_rmb": len(result_tickets) * TICKET_PRICE,
        "hot_numbers": hot,
        "hot_count": k,
        "method_weights": weight_display,
        "method_count": len(confidences),
        "coverage_pct": best_cov,
        "guarantee": (f"如果全部6个开奖红球都在{k}个BL热号中, "
                      f"≈{best_cov:.0f}%至少命中{t}个红球"),
        "ev_estimate": {
            "ev_per_draw": round(RANDOM_SINGLE_EV * len(result_tickets), 2),
            "cost_per_draw": len(result_tickets) * TICKET_PRICE,
        },
    }


if __name__ == "__main__":
    result = bl_tickets(k=15, t=4, n=6)
    if result["ok"]:
        print(f"Black-Litterman出号:")
        for i, t in enumerate(result["tickets"]):
            print(f"  #{i+1} {' '.join(str(n).zfill(2) for n in t['reds'])} | {str(t['blue']).zfill(2)}")
        print(f"热号: {result['hot_numbers']}")
        print(f"方法权重: {dict(list(result['method_weights'].items())[:5])}")
    else:
        print(f"失败: {result.get('msg')}")
