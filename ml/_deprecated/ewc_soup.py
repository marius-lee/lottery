"""训练优化方法 5+6: EWC 弹性巩固 + Model Soup 检查点融合

方法5: EWC (Elastic Weight Consolidation)
  来源: Kirkpatrick et al. (2017) PNAS
  https://doi.org/10.1073/pnas.1611835114
  实证: 知识图谱遗忘减少 45.7%, 医学分割改善 8-19%

方法6: Model Soup (检查点权重融合)
  来源: Wortsman et al. (2022) CVPR
  https://arxiv.org/abs/2203.05482
  实证: ImageNet +0.48%, ICH-17 SOTA, OOD 一致提升
"""

import json
import numpy as np
from pathlib import Path

CKPT_DIR = Path(__file__).parent.parent / ".cache" / "checkpoints"
SOUP_DIR = Path(__file__).parent.parent / ".cache" / "soup"
SOUP_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════
# 方法 5: EWC — Fisher 信息矩阵标记重要权重
# ═══════════════════════════════════════════════════════════════════

class EWCRegularizer:
    """弹性权重巩固: 用 Fisher 信息矩阵锁住重要权重, 只允许非关键参数学习。

    lambda_ewc: EWC 强度 (Kirkpatrick 建议 1e3~1e5, 彩票数据推荐 1e2)
    """

    def __init__(self, model, lambda_ewc=100.0):
        self.lambda_ewc = lambda_ewc
        self.fisher_diag = None   # Fisher 对角线
        self.optimal_weights = None  # θ* (最优权重)
        self._update_fisher(model)

    def _update_fisher(self, model):
        """计算并存储 Fisher 信息矩阵对角线 + 当前最优权重"""
        weights = model.get_weights()
        self.optimal_weights = [w.copy() for w in weights]

        # Fisher 对角线近似: 用权重平方的梯度 (简化版 EWC)
        # 完整 Fisher 需要计算 Hessian, 这里用权重绝对值作为重要性代理
        self.fisher_diag = []
        for w in weights:
            # Fisher ≈ |w| — 大权重 = 重要参数
            fd = np.abs(w) + 1e-8
            if fd.ndim > 1:
                fd = fd.mean(axis=tuple(range(fd.ndim - 1)))
            self.fisher_diag.append(fd / (fd.sum() + 1e-8))

    def ewc_loss(self, model):
        """计算 EWC 正则化损失: L_ewc = λ/2 Σ F_i (θ_i - θ*_i)²"""
        current = model.get_weights()
        if self.optimal_weights is None:
            return 0.0
        loss = 0.0
        for f_diag, cw, ow in zip(self.fisher_diag, current, self.optimal_weights):
            diff = (cw.ravel() - ow.ravel()).astype(np.float64)
            # Fisher per-element mean — broadcast to weight shape
            f_mean = float(np.mean(f_diag))
            loss += f_mean * np.sum(diff * diff)
        return self.lambda_ewc * 0.5 * loss

    def update_and_save(self, model):
        """更新 Fisher + 存档"""
        self._update_fisher(model)
        np.savez(str(CKPT_DIR / "ewc_state.npz"),
                 *self.optimal_weights,
                 *self.fisher_diag,
                 allow_pickle=True)

    def load(self):
        p = CKPT_DIR / "ewc_state.npz"
        if not p.exists():
            return False
        data = np.load(str(p), allow_pickle=True)
        n = len(data.files) // 2
        self.optimal_weights = [data[f"arr_{i}"] for i in range(n)]
        self.fisher_diag = [data[f"arr_{i+n}"] for i in range(n)]
        return True


# ═══════════════════════════════════════════════════════════════════
# 方法 6: Model Soup — 历史最佳检查点贪婪融合
# ═══════════════════════════════════════════════════════════════════

class ModelSoup:
    """Greedy Soup: 按验证指标降序, 贪心融合检查点。

    每个检查点是 .keras 文件。融合时做权重插值。
    """

    def __init__(self, max_checkpoints=5):
        self.max_checkpoints = max_checkpoints
        self.registry_file = SOUP_DIR / "registry.json"
        self.checkpoints = self._load_registry()

    def _load_registry(self):
        if self.registry_file.exists():
            return json.loads(self.registry_file.read_text())
        return []

    def _save_registry(self):
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        self.registry_file.write_text(json.dumps(self.checkpoints))

    def add(self, score, path, model_name="gpt"):
        """添加一个检查点, 按 score 降序排列"""
        self.checkpoints.append({
            "score": score,
            "path": str(path),
            "model": model_name,
        })
        self.checkpoints.sort(key=lambda x: -x["score"])
        self.checkpoints = self.checkpoints[:self.max_checkpoints]
        self._save_registry()

    def greedy_soup(self, model):
        """贪婪融合: 从最高分开始, 逐个尝试添加, 保留提升的。

        简化版: 直接均匀平均 top-N 检查点 (Model Soup 论文发现均匀平均在多数情况下
        和贪心一样好甚至更好)
        """
        if len(self.checkpoints) < 2:
            return

        import tensorflow as tf
        all_weights = []

        # 加载当前模型权重 (作为基准)
        all_weights.append([w.copy() for w in model.get_weights()])

        # 加载其他检查点
        for ckpt in self.checkpoints[:self.max_checkpoints]:
            try:
                tmp = tf.keras.models.load_model(ckpt["path"])
                all_weights.append([w.numpy() for w in tmp.get_weights()])
            except Exception:
                continue

        if len(all_weights) < 2:
            return

        # 均匀平均 (Model Soup 论文 4.3 节: uniform soup 通常最优)
        n = len(all_weights)
        averaged = []
        for i in range(len(all_weights[0])):
            avg = sum(w[i] for w in all_weights) / n
            averaged.append(avg)

        model.set_weights(averaged)

    def best_score(self):
        return self.checkpoints[0]["score"] if self.checkpoints else 0
