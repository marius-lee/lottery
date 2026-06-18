"""隐Markov模型机制检测 — 自动发现抽奖的"隐藏状态"

你的核心观察的数学表达:
  "某段时间内01在pos_1连出概率高, 过段时间又不高了"
  ≡ 隐藏状态(regime)切换 → 发射概率变化 → 肉眼在手动检测切换

HMM结构:
  隐藏状态 z_t ∈ {1..K}  — "抽奖模式/机制"
  观测 o_t = (pos_1..pos_6, blue) — 当期开奖
  转移 P(z_t | z_{t-1}) — 机制切换概率
  发射 P(o_t | z_t) — 该机制下的号码分布

训练: Baum-Welch (EM算法) 从历史数据学习隐藏机制
推断: Forward算法 实时跟踪"当前处于哪个机制"
预测: 用当前机制的发射分布采样

为什么不同于之前所有方法:
  - 不假设"全局规律" → 显式建模"规律随时间变化"
  - 不预测哪个球会出 → 推断当前是哪种机制, 再按该机制生成
  - 和用户的做法完全同构: 看最近几期→判断当前模式→按模式选号

来源:
  Rabiner (1989) "A Tutorial on Hidden Markov Models", Proc IEEE
  Baum et al. (1970) "A Maximization Technique...", Ann Math Stat
  Robert & Titterington (1998) "HMM in signal processing"
"""

import math
import random
import json
import numpy as np
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent.parent
CACHE_DIR = ROOT / ".cache"


class RegimeHMM:
    """隐藏机制HMM — K个隐藏抽奖模式, 每模式有独立的号码分布。

    观测模型: 每位置独立分类分布 (6红球位 × 33类 + 1蓝球位 × 16类)
    这比建模完整组合空间(17M)可行得多, 且保留位置结构。
    """

    def __init__(self, K=4, seed=42):
        """
        Args:
            K: 隐藏机制数 (3-6推荐。太少→分辨不出, 太多→过拟合)
            seed: 随机种子
        """
        self.K = K
        np.random.seed(seed)
        random.seed(seed)

        # ── HMM参数 ──
        # 初始状态分布 π[k] = P(z_1 = k)
        self.pi = None
        # 状态转移矩阵 A[k][j] = P(z_t = j | z_{t-1} = k)
        self.A = None
        # 发射概率:
        #   B_red[pos][k][ball] = P(ball at pos | state=k)  (6 × K × 33)
        #   B_blue[k][ball] = P(blue=ball | state=k)        (K × 16)
        self.B_red = None
        self.B_blue = None

        self._trained = False

    # ═══════════════════════════════════════════════════════════════
    # 训练: Baum-Welch (EM)
    # ═══════════════════════════════════════════════════════════════

    def train(self, draws, max_iter=50, tol=1e-4, verbose=True):
        """Baum-Welch EM算法训练HMM。

        Args:
            draws: [[period, r1..r6, blue], ...]
            max_iter: 最大EM迭代
            tol: 对数似然收敛阈值
            verbose: 打印进度
        """
        N = len(draws)
        K = self.K

        # 提取观测序列: 每期 → (pos1..pos6 0-based, blue 0-based)
        obs = []
        for d in draws:
            reds = sorted(d[1:7])
            obs.append(([r - 1 for r in reds], d[7] - 1))

        # ── 初始化参数 ──
        # π: 均匀 + 噪声
        self.pi = np.ones(K) / K + np.random.uniform(-0.05, 0.05, K)
        self.pi = np.clip(self.pi, 0.01, None)
        self.pi /= self.pi.sum()

        # A: 偏自转移 (机制应有一定持续性)
        self.A = np.zeros((K, K))
        for k in range(K):
            self.A[k, k] = 0.8 + random.uniform(-0.1, 0.1)  # 80%自转移
            remaining = 1.0 - self.A[k, k]
            for j in range(K):
                if j != k:
                    self.A[k, j] = remaining / (K - 1) * random.uniform(0.8, 1.2)
            self.A[k] /= self.A[k].sum()

        # B_red: 每个机制有偏好的球位分布
        # 用K-means对初始分布做聚类 (从历史数据取K个随机窗口)
        self.B_red = np.zeros((6, K, 33))
        for k in range(K):
            # 取一段100期的窗口作为第k个机制的初始分布
            seg_start = (N * k) // K
            seg_end = min(seg_start + 100, N)
            for pos in range(6):
                for i in range(seg_start, seg_end):
                    ball_idx = obs[i][0][pos]
                    self.B_red[pos, k, ball_idx] += 1.0
                # Laplace平滑
                self.B_red[pos, k] += 1.0
                self.B_red[pos, k] /= self.B_red[pos, k].sum()
        self.B_red += np.random.uniform(-0.01, 0.01, (6, K, 33))
        self.B_red = np.clip(self.B_red, 0.001, None)
        for k in range(K):
            for pos in range(6):
                self.B_red[pos, k] /= self.B_red[pos, k].sum()

        # B_blue
        self.B_blue = np.ones((K, 16)) / 16.0
        self.B_blue += np.random.uniform(-0.02, 0.02, (K, 16))
        self.B_blue = np.clip(self.B_blue, 0.001, None)
        for k in range(K):
            self.B_blue[k] /= self.B_blue[k].sum()

        # ── Baum-Welch EM ──
        prev_ll = -float('inf')

        for iteration in range(max_iter):
            # ---- E-step: Forward-Backward ----
            alpha, beta, scale = self._forward_backward(obs)

            # ---- 对数似然 ----
            ll = np.log(scale).sum()
            if verbose and iteration % 10 == 0:
                print(f"  [HMM] iter {iteration}: LL={ll:.1f}")

            if abs(ll - prev_ll) < tol:
                if verbose:
                    print(f"  [HMM] 收敛于 iter {iteration}")
                break
            prev_ll = ll

            # ---- M-step: 更新参数 ----
            # γ_t(k) = P(z_t = k | O)
            gamma = alpha * beta  # (T, K)
            gamma /= gamma.sum(axis=1, keepdims=True)

            # ξ_t(i,j) = P(z_t = i, z_{t+1} = j | O)
            xi = np.zeros((N - 1, K, K))
            for t in range(N - 1):
                for i in range(K):
                    for j in range(K):
                        xi[t, i, j] = (alpha[t, i] *
                                       self.A[i, j] *
                                       self._emit_prob(obs[t + 1], j) *
                                       beta[t + 1, j])
                xi_t_sum = xi[t].sum()
                if xi_t_sum > 0:
                    xi[t] /= xi_t_sum

            # 更新 π
            self.pi = gamma[0].copy()

            # 更新 A
            for i in range(K):
                denom = gamma[:-1, i].sum()
                if denom > 0:
                    for j in range(K):
                        self.A[i, j] = xi[:, i, j].sum() / denom
                else:
                    self.A[i] = np.ones(K) / K
                self.A[i] = np.clip(self.A[i], 0.001, None)
                self.A[i] /= self.A[i].sum()

            # 更新 B_red: 加权计数
            for pos in range(6):
                for k in range(K):
                    counts = np.ones(33) * 0.1  # 平滑
                    for t in range(N):
                        ball_idx = obs[t][0][pos]
                        counts[ball_idx] += gamma[t, k]
                    self.B_red[pos, k] = counts / counts.sum()

            # 更新 B_blue
            for k in range(K):
                counts = np.ones(16) * 0.1
                for t in range(N):
                    blue_idx = obs[t][1]
                    counts[blue_idx] += gamma[t, k]
                self.B_blue[k] = counts / counts.sum()

        self._trained = True

        # ── 后训练: 标注每个状态、计算状态统计 ──
        self._state_info = self._analyze_states(gamma, draws)

        if verbose:
            print(f"  [HMM] 训练完成: K={K}, LL={ll:.1f}")
            self._print_state_summary()

    def _emit_prob(self, obs_t, state_k):
        """计算 P(o_t | z_t = k): 各位置发射概率的乘积"""
        reds, blue = obs_t
        log_p = 0.0
        for pos in range(6):
            log_p += math.log(max(self.B_red[pos, state_k, reds[pos]], 1e-10))
        log_p += math.log(max(self.B_blue[state_k, blue], 1e-10))
        return math.exp(log_p)

    def _forward_backward(self, obs):
        """Forward-Backward算法。

        Returns:
            alpha: (T, K) forward概率
            beta: (T, K) backward概率
            scale: (T,) 归一化因子 (用于计算似然)
        """
        T = len(obs)
        K = self.K
        alpha = np.zeros((T, K))
        beta = np.zeros((T, K))
        scale = np.zeros(T)

        # Forward
        for k in range(K):
            alpha[0, k] = self.pi[k] * self._emit_prob(obs[0], k)
        scale[0] = alpha[0].sum()
        if scale[0] > 0:
            alpha[0] /= scale[0]

        for t in range(1, T):
            for j in range(K):
                s = 0.0
                for i in range(K):
                    s += alpha[t - 1, i] * self.A[i, j]
                alpha[t, j] = s * self._emit_prob(obs[t], j)
            scale[t] = alpha[t].sum()
            if scale[t] > 0:
                alpha[t] /= scale[t]

        # Backward
        beta[T - 1] = 1.0
        for t in range(T - 2, -1, -1):
            for i in range(K):
                s = 0.0
                for j in range(K):
                    s += self.A[i, j] * self._emit_prob(obs[t + 1], j) * beta[t + 1, j]
                beta[t, i] = s
            if scale[t] > 0:
                beta[t] /= scale[t]

        return alpha, beta, scale

    def _analyze_states(self, gamma, draws):
        """为每个隐藏机制打标，便于人类理解。"""
        info = {}
        N = len(draws)

        # 硬分配: 每期属于概率最高的机制
        hard_assign = gamma.argmax(axis=1)

        for k in range(self.K):
            # 该机制包含的期数
            n_assign = (hard_assign == k).sum()

            # 该机制下pos_1的最偏好号码
            top3_pos1 = sorted(
                [(b + 1, self.B_red[0, k, b]) for b in range(33)],
                key=lambda x: -x[1],
            )[:3]

            # 该机制下pos_6的最偏好号码
            top3_pos6 = sorted(
                [(b + 1, self.B_red[5, k, b]) for b in range(33)],
                key=lambda x: -x[1],
            )[:3]

            # 蓝球偏好
            top3_blue = sorted(
                [(b + 1, self.B_blue[k, b]) for b in range(16)],
                key=lambda x: -x[1],
            )[:3]

            # 自转移率
            self_trans = self.A[k, k]

            info[k] = {
                "state_id": k,
                "n_periods": int(n_assign),
                "fraction": round(n_assign / N * 100, 1),
                "self_transition": round(self_trans, 3),
                "top_pos1": top3_pos1,
                "top_pos6": top3_pos6,
                "top_blue": top3_blue,
            }

        return info

    def _print_state_summary(self):
        for k in sorted(self._state_info.keys()):
            info = self._state_info[k]
            pos1_str = ", ".join([f"{n}({p:.1%})" for n, p in info["top_pos1"]])
            pos6_str = ", ".join([f"{n}({p:.1%})" for n, p in info["top_pos6"]])
            blue_str = ", ".join([f"{n}({p:.1%})" for n, p in info["top_blue"]])
            print(f"  机制{k}: {info['n_periods']}期({info['fraction']}%) "
                  f"自转={info['self_transition']:.2f}")
            print(f"    pos1→{pos1_str}  pos6→{pos6_str}")
            print(f"    蓝→{blue_str}")

    # ═══════════════════════════════════════════════════════════════
    # 推断: Forward滤波 → 当前处于哪个机制
    # ═══════════════════════════════════════════════════════════════

    def infer_state(self, recent_draws):
        """给定最近N期, 推断当前最可能的隐藏机制。

        用Forward算法计算 P(z_t | o_1..o_t) for last draw.

        Returns:
            state_probs: {state_id: probability}  当前机制的后验分布
            dominant_state: 最可能的机制ID
            state_info: 该机制的偏好分布
        """
        if not self._trained:
            return None

        T = len(recent_draws)
        obs = []
        for d in recent_draws:
            reds = sorted(d[1:7])
            obs.append(([r - 1 for r in reds], d[7] - 1))

        # Forward pass
        alpha = np.zeros((T, self.K))

        for k in range(self.K):
            alpha[0, k] = self.pi[k] * self._emit_prob(obs[0], k)
        alpha[0] /= alpha[0].sum()

        for t in range(1, T):
            for j in range(self.K):
                s = 0.0
                for i in range(self.K):
                    s += alpha[t - 1, i] * self.A[i, j]
                alpha[t, j] = s * self._emit_prob(obs[t], j)
            alpha[t] /= alpha[t].sum()

        # 最后一期的后验
        probs = alpha[-1]
        dominant = int(probs.argmax())

        return {
            "state_probs": {k: round(float(probs[k]), 4) for k in range(self.K)},
            "dominant_state": dominant,
            "dominant_confidence": round(float(probs[dominant]), 4),
            "state_info": self._state_info.get(dominant, {}),
        }

    # ═══════════════════════════════════════════════════════════════
    # 生成: 从当前机制的发射分布采样
    # ═══════════════════════════════════════════════════════════════

    def generate(self, inference_result, n_tickets=3, temperature=1.0):
        """从当前机制的发射分布生成彩票。

        如果推断出多个机制的可能性相近 (>20%), 用概率加权混合各机制的发射分布。

        Args:
            inference_result: infer_state()的结果
            n_tickets: 生成注数
            temperature: 采样温度 (0.5=保守, 1.0=正常, 2.0=探索)

        Returns:
            list of dicts
        """
        probs = inference_result["state_probs"]

        # 混合各机制的发射分布
        mixed_red = np.zeros((6, 33))
        mixed_blue = np.zeros(16)

        for k, weight in probs.items():
            if weight < 0.05:  # 忽略<5%的机制
                continue
            for pos in range(6):
                mixed_red[pos] += weight * self.B_red[pos, k]
            mixed_blue += weight * self.B_blue[k]

        # 温度缩放
        if temperature != 1.0:
            for pos in range(6):
                mixed_red[pos] = mixed_red[pos] ** (1.0 / temperature)
                mixed_red[pos] /= mixed_red[pos].sum()
            mixed_blue = mixed_blue ** (1.0 / temperature)
            mixed_blue /= mixed_blue.sum()

        tickets = []
        for _ in range(n_tickets):
            # 顺序采样: 按pos_1到pos_6, 逐位采样, 排除已选号码
            chosen = []
            for pos in range(6):
                available = [b for b in range(33) if b not in chosen]
                w = np.array([mixed_red[pos, b] for b in available])
                w /= w.sum()
                ball_idx = int(np.random.choice(available, p=w))
                chosen.append(ball_idx)

            # 蓝球
            blue_w = mixed_blue / mixed_blue.sum()
            blue_idx = int(np.random.choice(16, p=blue_w))

            tickets.append({
                "reds": sorted([b + 1 for b in chosen]),
                "blue": blue_idx + 1,
            })

        return tickets

    # ═══════════════════════════════════════════════════════════════
    # 持久化
    # ═══════════════════════════════════════════════════════════════

    def save(self, path=None):
        if path is None:
            path = CACHE_DIR / "hmm_regime.json"
        data = {
            "K": self.K,
            "pi": self.pi.tolist(),
            "A": self.A.tolist(),
            "B_red": [[self.B_red[p, k].tolist() for k in range(self.K)] for p in range(6)],
            "B_blue": self.B_blue.tolist(),
            "state_info": {str(k): v for k, v in self._state_info.items()},
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f)

    def load(self, path=None):
        if path is None:
            path = CACHE_DIR / "hmm_regime.json"
        if not Path(path).exists():
            return False
        with open(path) as f:
            data = json.load(f)
        self.K = data["K"]
        self.pi = np.array(data["pi"])
        self.A = np.array(data["A"])
        self.B_red = np.array(data["B_red"])
        self.B_blue = np.array(data["B_blue"])
        self._state_info = {int(k): v for k, v in data.get("state_info", {}).items()}
        self._trained = True
        return True


# ═══════════════════════════════════════════════════════════════════
# 便捷接口
# ═══════════════════════════════════════════════════════════════════

def train_and_predict(draws, K=4, recent_window=20, n_tickets=3):
    """端到端: 训练HMM→推断当前机制→生成彩票。

    Args:
        draws: 全部历史数据
        K: 隐藏机制数
        recent_window: 用最近N期推断当前机制
        n_tickets: 生成注数

    Returns:
        (tickets, inference_result, hmm)
    """
    hmm = RegimeHMM(K=K)
    hmm.train(draws, verbose=True)

    # 用最近20期推断当前机制
    recent = draws[-recent_window:]
    inference = hmm.infer_state(recent)

    # 生成
    tickets = hmm.generate(inference, n_tickets=n_tickets)

    return tickets, inference, hmm
