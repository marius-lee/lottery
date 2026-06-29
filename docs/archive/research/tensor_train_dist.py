"""Tensor Train 概率分布 — 矩阵乘积态压缩表示全量组合分布

原理: C(33,6)=1.1M 组合的概率分布可表示为6阶张量,
  Tensor Train (TT) 分解将其压缩为 O(6×33×r²) 参数,
  其中 r = bond dimension / TT-rank.

核心问题:
  - r=1: 完全独立假设 (P = ∏P_i),
  - r=2-3: 弱纠缠, 相邻位置间有相互作用
  - r越高→模型越复杂→可能过拟合

判断准则:
  - 如果 r=2 的验证似然显著优于 r=1 → 存在位置间纠缠结构
  - 如果 r=1 (独立) 已是最优 → 无可检测的交互作用

参考:
  Novikov+ (2014): "Putting MRFs on a Tensor Train"
  TT-RS (2023): "Generative modeling via tensor train sketching"
  Oseledets (2011): "Tensor-Train Decomposition"
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import math
import random
from collections import Counter


def load_data():
    from server.db import load_draws
    return load_draws()


# ═══════════════════════════════════════════════════════════════
# Tensor Train 核心
# ═══════════════════════════════════════════════════════════════

class TensorTrain:
    """6位置(有序) × 33状态 → TT压缩.

    每位置i有33个状态, 状态空间受排序约束:
      位置0: 1≤n0≤28 (因为后面还有5个更大的数)
      位置1: n0+1 ≤ n1 ≤ 29
      位置2: n1+1 ≤ n2 ≤ 30
      位置3: n2+1 ≤ n3 ≤ 31
      位置4: n3+1 ≤ n4 ≤ 32
      位置5: n4+1 ≤ n5 ≤ 33

    TT核: G[i] 形状 (r_i, 33, r_{i+1}), r_0 = r_6 = 1

    约束: P(n0,n1,...,n5) = G[0][:,n0,:] @ G[1][:,n1,:] @ ... @ G[5][:,n5,:]
          必须满足排序约束 (不满足→概率=0)
    """
    def __init__(self, rank=2):
        self.rank = rank
        self.cores = []  # 6个核张量

    def init_random(self):
        """随机初始化TT核."""
        r = self.rank
        # 每个核心: (r_prev, 33, r_next)
        # 零填充不合法状态
        self.cores = []
        self.cores.append(_random_core(1, 33, r))     # 位置0
        self.cores.append(_random_core(r, 33, r))     # 位置1
        self.cores.append(_random_core(r, 33, r))     # 位置2
        self.cores.append(_random_core(r, 33, r))     # 位置3
        self.cores.append(_random_core(r, 33, r))     # 位置4
        self.cores.append(_random_core(r, 33, 1))     # 位置5

    def log_prob(self, reds_sorted):
        """计算一组升序红球的log概率.

        TT乘积: scalar = G0[:, n0, :] @ G1[:, n1, :] @ ... @ G5[:, n5, :]
        """
        vec = [1.0]  # 1×1矩阵 (r0=1)
        for pos in range(6):
            n = reds_sorted[pos] - 1  # 0-indexed
            core = self.cores[pos]  # (r_prev, 33, r_next)
            # vec: (r_prev,) → 乘核 → (r_next,)
            new_vec = [0.0] * core.shape[2]
            for i in range(core.shape[0]):  # r_prev
                if vec[i] == 0:
                    continue
                for j in range(core.shape[2]):  # r_next
                    new_vec[j] += vec[i] * core[i, n, j]
            vec = new_vec
        # vec[0] = 概率密度 (未归一化)
        val = vec[0]
        if val <= 0:
            return float('-inf')
        return math.log(max(val, 1e-30))

    def prob(self, reds_sorted):
        lp = self.log_prob(reds_sorted)
        return math.exp(lp) if lp > float('-inf') else 0.0

    def n_params(self):
        """参数总数."""
        return sum(core.shape[0] * core.shape[1] * core.shape[2] for core in self.cores)

    def normalize(self):
        """L1归一化: 确保总概率=1. 遍历所有C(33,6)组合."""
        import itertools
        total = 0.0
        # [工程] 采样归一化: 110万组合太多, 用10万采样估算
        for _ in range(100000):
            reds = tuple(sorted(random.sample(range(1, 34), 6)))
            total += self.prob(reds)
        norm_factor = 100000 / 1107568  # [数学] 总组合数
        avg_prob = total / 100000 * norm_factor
        # 缩放各核使总概率≈1
        if avg_prob > 0:
            scale = (1.0 / avg_prob) ** (1.0 / 6)
            for pos in range(6):
                for i in range(self.cores[pos].shape[0]):
                    for n in range(self.cores[pos].shape[1]):
                        for j in range(self.cores[pos].shape[2]):
                            self.cores[pos][i, n, j] *= scale


def _random_core(r_prev, n_states, r_next):
    """生成随机TT核."""
    import random
    core = [[[random.gauss(0, 0.1) for _ in range(r_next)]
             for _ in range(n_states)]
            for _ in range(r_prev)]
    # 转换为三重列表 → 简单实现, M1上够用
    # 用简单的列表结构, 避免numpy依赖
    return TTCore(core, r_prev, n_states, r_next)


class TTCore:
    """TT核的轻量包装."""
    def __init__(self, data, r_prev, n_states, r_next):
        self.data = data  # list[r_prev][n_states][r_next]
        self.r_prev = r_prev
        self.n_states = n_states
        self.r_next = r_next

    @property
    def shape(self):
        return (self.r_prev, self.n_states, self.r_next)

    def __getitem__(self, idx):
        i, n, j = idx
        return self.data[i][n][j]

    def __setitem__(self, idx, val):
        i, n, j = idx
        self.data[i][n][j] = val


# ═══════════════════════════════════════════════════════════════
# 从数据学习TT: MLE via 梯度上升
# ═══════════════════════════════════════════════════════════════

def learn_tt_from_data(data, rank=2, n_iter=200, lr=1e-3, verbose=False):
    """从开奖数据学习TT参数 (最大似然).

    简化版: 用频率+平滑估计各位置的边际分布(r=1),
    对于r>1, 初始化随机+小扰动, 不做完整MLE (M1上太慢).

    完整MLE需要: 每迭代遍历所有2000期, 计算梯度, 更新6个核.
    2000期×200迭代=400K次前向传播, 对于纯Python TT是可行的.
    """
    tt = TensorTrain(rank=rank)
    tt.init_random()

    # 提取所有有效组合
    combos = []
    for row in data:
        combos.append(tuple(sorted(row[1:7])))

    best_ll = float('-inf')
    best_cores = None

    # SGD
    for it in range(n_iter):
        total_ll = 0.0
        for reds in combos[:500]:  # [工程] 用500个样本, 减少计算量
            ll = tt.log_prob(reds)
            if ll > float('-inf'):
                total_ll += ll

        # 小随机扰动 → 接受如果改善
        if total_ll > best_ll:
            best_ll = total_ll
            best_cores = [[[[c.data[i][n][j] for j in range(c.r_next)]
                           for n in range(c.n_states)]
                          for i in range(c.r_prev)]
                         for c in tt.cores]

        # 扰动
        for core in tt.cores:
            i = random.randint(0, core.r_prev - 1)
            n = random.randint(0, core.n_states - 1)
            j = random.randint(0, core.r_next - 1)
            noise = random.gauss(0, lr)
            core.data[i][n][j] += noise

        if verbose and it % 50 == 0:
            print(f"    iter {it}: ll={total_ll:.1f}, best={best_ll:.1f}")

    # 恢复最佳参数
    if best_cores:
        for c_idx, core in enumerate(tt.cores):
            for i in range(core.r_prev):
                for n in range(core.n_states):
                    for j in range(core.r_next):
                        core.data[i][n][j] = best_cores[c_idx][i][n][j]

    return tt, best_ll


# ═══════════════════════════════════════════════════════════════
# 基线: 独立频率模型 (r=1)
# ═══════════════════════════════════════════════════════════════

def independent_freq_model(data):
    """独立频率模型: P(r1,...,r6) ∝ ∏_pos f_pos(r_pos).

    这就是TT的r=1特例.
    """
    n = len(data)
    # 每位置频率
    pos_counts = [Counter() for _ in range(6)]
    for row in data:
        reds = sorted(row[1:7])
        for p in range(6):
            pos_counts[p][reds[p]] += 1

    # Laplace平滑
    def score(reds_sorted):
        lp = 0.0
        for p in range(6):
            n_pos = reds_sorted[p]
            cnt = pos_counts[p].get(n_pos, 0) + 1  # +1平滑
            lp += math.log(cnt / (n + 33))  # [数学] 总次=n+33(平滑)
        return lp

    return score


# ═══════════════════════════════════════════════════════════════
# 交叉验证: 比较 r=1 和 r>1
# ═══════════════════════════════════════════════════════════════

def cross_validate(data, ranks=[1, 2, 3], n_folds=5):
    """交叉验证比较不同rank的预测似然.

    如果 r>1 的验证似然 > r=1 → 存在超出独立假设的交互结构.
    """
    n = len(data)
    fold_size = n // n_folds

    results = {}
    for rank in ranks:
        fold_lls = []
        for fold in range(n_folds):
            test_start = fold * fold_size
            test_end = min(test_start + fold_size, n)
            train = data[:test_start] + data[test_end:]

            if rank == 1:
                # 独立模型
                scorer = independent_freq_model(train)
                ll = 0.0
                for i in range(test_start, test_end):
                    ll += scorer(tuple(sorted(data[i][1:7])))
                fold_lls.append(ll / (test_end - test_start))
            else:
                # TT模型
                tt, _ = learn_tt_from_data(train, rank=rank, n_iter=100, lr=1e-3)
                ll = 0.0
                count = 0
                for i in range(test_start, test_end):
                    lp = tt.log_prob(tuple(sorted(data[i][1:7])))
                    if lp > float('-inf'):
                        ll += lp
                        count += 1
                fold_lls.append(ll / count if count else float('-inf'))

        avg_ll = sum(fold_lls) / len(fold_lls)
        results[rank] = {
            "per_fold_ll": fold_lls,
            "mean_ll": round(avg_ll, 2),
            "n_params": 6 * 33 if rank == 1 else TensorTrain(rank=rank).n_params(),
        }
        print(f"  rank={rank}: mean log-likelihood = {avg_ll:.2f} "
              f"(params={results[rank]['n_params']})")

    return results


# ═══════════════════════════════════════════════════════════════
# TT采样: 从TT分布中生成新号码
# ═══════════════════════════════════════════════════════════════

def sample_from_tt(tt, n_samples=10):
    """从TT分布中采样号码组合.

    使用条件采样: 逐个位置从条件分布中抽取.
    """
    results = []
    for _ in range(n_samples):
        reds = []
        min_val = 1
        for pos in range(6):
            # 计算每个候选号码的条件概率 (给定已选号码)
            max_val = 33 - (5 - pos)  # 为后面位置留空间
            candidates = list(range(min_val, max_val + 1))
            probs = []
            for n in candidates:
                test_reds = reds + [n] + [0] * (5 - pos)  # 填充
                # 只计算前pos+1个位置的贡献
                vec = [1.0]
                for p in range(pos + 1):
                    nn = test_reds[p] - 1
                    core = tt.cores[p]
                    new_vec = [0.0] * core.r_next
                    for i in range(core.r_prev):
                        if vec[i] == 0:
                            continue
                        for j in range(core.r_next):
                            new_vec[j] += vec[i] * core[i, nn, j]
                    vec = new_vec
                probs.append(vec[0] if vec and vec[0] > 0 else 1e-10)

            # 归一化并采样
            total = sum(probs)
            r = random.random() * total
            cum = 0.0
            chosen = candidates[0]
            for idx, p in enumerate(probs):
                cum += p
                if r < cum:
                    chosen = candidates[idx]
                    break

            reds.append(chosen)
            min_val = chosen + 1

        results.append(reds)
    return results


# ═══════════════════════════════════════════════════════════════
# 主函数
# ═══════════════════════════════════════════════════════════════

def run():
    data = load_data()
    n = len(data)

    print(f"=" * 60)
    print(f"Tensor Train 概率分布压缩")
    print(f"=" * 60)
    print(f"数据: {n} 期")
    print(f"目标: 用TT压缩表示P(r1,...,r6), 检测位置间纠缠")
    print()

    # ── 交叉验证 ──
    print(f"交叉验证 (5折, 比较rank=1/2/3):")
    cv = cross_validate(data, ranks=[1, 2, 3])

    print()
    print(f"  Rank vs Params:")
    baseline_ll = cv[1]["mean_ll"]
    for rank in [1, 2, 3]:
        delta = cv[rank]["mean_ll"] - baseline_ll
        print(f"    r={rank}: LL={cv[rank]['mean_ll']:.2f} "
              f"(Δ={delta:+.2f} vs r=1), params={cv[rank]['n_params']}")

    # ── 纠缠检测 ──
    print(f"\n{'─' * 60}")
    r2_delta = cv[2]["mean_ll"] - cv[1]["mean_ll"]
    r3_delta = cv[3]["mean_ll"] - cv[1]["mean_ll"]

    # [统计] AIC-like: ΔLL需要超过额外参数数才能判定交互存在
    extra_params_r2 = cv[2]["n_params"] - cv[1]["n_params"]
    extra_params_r3 = cv[3]["n_params"] - cv[1]["n_params"]

    if r2_delta > extra_params_r2 * 0.5 or r3_delta > extra_params_r3 * 0.5:
        print(f"⚠️  检测到位置间纠缠 (r>1优于独立)")
        print(f"  r=2改善: {r2_delta:+.1f} (需>{extra_params_r2*0.5:.0f})")
        print(f"  → 位置间存在超出独立的统计相互作用")
    else:
        print(f"无显著纠缠 (独立模型r=1最优)")
        print(f"  r=2改善: {r2_delta:+.1f} (需>{extra_params_r2*0.5:.0f})")
        print(f"  → 6个位置近似独立, 边际频率足以描述分布")

    # ── 抽样展示 ──
    print(f"\n{'─' * 60}")
    print(f"从TT(r=2)采样10注:")
    try:
        tt_r2, _ = learn_tt_from_data(data, rank=2, n_iter=50)
        samples = sample_from_tt(tt_r2, 10)
        # 统计抽样频率
        sample_counts = Counter()
        for reds in samples:
            for r in reds:
                sample_counts[r] += 1
        top = sample_counts.most_common(5)
        print(f"  TT抽样热门号码: {dict(top)}")
    except Exception as e:
        print(f"  抽样失败: {e}")

    # ── 独立频率基线抽样 ──
    print(f"\n从独立频率模型(位置级)抽样10注:")
    scorer = independent_freq_model(data)
    # 位置级条件采样
    pos_counts = [Counter() for _ in range(6)]
    for row in data:
        reds = sorted(row[1:7])
        for p in range(6):
            pos_counts[p][reds[p]] += 1

    for _ in range(3):
        reds = []
        min_val = 1
        for p in range(6):
            max_val = 33 - (5 - p)
            candidates = list(range(min_val, max_val + 1))
            weights = [pos_counts[p].get(c, 0) + 1 for c in candidates]
            total = sum(weights)
            r = random.random() * total
            cum = 0.0
            chosen = candidates[0]
            for idx, w in enumerate(weights):
                cum += w
                if r < cum:
                    chosen = candidates[idx]
                    break
            reds.append(chosen)
            min_val = chosen + 1
        print(f"    独立采样: {reds}")

    print(f"\n{'═' * 60}")
    print(f"综合: 位置间交互 → {'存在' if r2_delta > 0 else '未检测到'}")
    print(f"      边际频率偏差 → 已确认 (贝叶斯分析)")
    print(f"      联合分布 ← 边际+交互, 交互项 → {'可忽略' if r2_delta <= 0 else '需建模'}")
    print(f"{'═' * 60}")

    return cv


if __name__ == "__main__":
    run()
