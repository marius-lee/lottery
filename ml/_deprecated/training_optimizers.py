"""训练优化方法 3: AutoCyclic LR

来源: Arthur et al. (2024) IEEE Access
https://ieeexplore.ieee.org/document/10912480
在 ETTm2/M4/WindTurbine 上测试 Transformer/LSTM/RNN
一致优于静态 Adam + 余弦 CLR
"""

import numpy as np


def compute_autocorr_lr_bounds(draws, base_min=5e-5, base_max=1e-3):
    """从训练数据自相关确定 LR 边界。

    AutoCyclic: 自相关越强 → 模式越可预测 → LR 可以更高
    来源: Arthur et al. (2024) IEEE Access
    https://ieeexplore.ieee.org/document/10912480

    base_min=5e-5, base_max=1e-3:
      Adam 默认 lr=1e-3 (Kingma & Ba 2014 https://arxiv.org/abs/1412.6980)
      5e-5 是 fine-tuning 常用下限 (Devlin et al. 2019 BERT)
    """
    n = min(500, len(draws))  # 500 ≈ 最近2年数据, 足够估计自相关
    reds_seq = []
    for r in draws[-n:]:
        reds_seq.extend(r[1:7])
    if len(reds_seq) < 2:
        return base_min, base_max
    autocorr = np.corrcoef(reds_seq[:-1], reds_seq[1:])[0, 1]
    strength = abs(autocorr)
    # strength ∈ [0,1] → lr_max ∈ [base_min, base_min+2*(base_max-base_min)]
    # 自相关=1 → lr_max=base_max; 自相关=0 → lr_max≈base_min
    lr_max = base_min + (base_max - base_min) * strength * 2
    lr_min = base_min * max(0.5, 1 - strength)  # floor=0.5: LR不低于base_min/2 (Arthur et al. 2024)
    return max(5e-6, lr_min), min(5e-3, lr_max)


def cyclic_lr(step, total_steps, lr_min, lr_max):
    """三角波循环学习率 (Smith 2017 1-cycle 简化版)"""
    cycle = step % total_steps
    half = total_steps // 2
    if cycle < half:
        return lr_min + (lr_max - lr_min) * (cycle / half)
    else:
        return lr_max - (lr_max - lr_min) * ((cycle - half) / half)
