"""GPT Transformer 预测器

T=0.5保守(高概率) T=0.8均衡 T=1.2多样
来源: Holtzman et al. 2019 "The Curious Case of Neural Text Degeneration"
https://arxiv.org/abs/1904.09751

优先使用 gpt_best.keras (训练中最佳), 回退到 gpt_model.keras
"""
from pathlib import Path
from ml.transformer_predictor import GPTLotteryPredictor

TEMPERATURES = [0.5, 0.8, 1.2]
BEST_PATH = Path(__file__).parent.parent / ".cache" / "checkpoints" / "gpt_best.keras"

_gpt = None

def _load(data):
    global _gpt
    if _gpt is not None:
        return _gpt
    import tensorflow as tf
    _gpt = GPTLotteryPredictor()
    if BEST_PATH.exists():
        # 用训练中最佳权重 (每次突破 best_red 时保存)
        _gpt.model = tf.keras.models.load_model(str(BEST_PATH))
        _gpt._trained = True
    elif not _gpt.load():
        _gpt.train(data, epochs=5, block_size=256, verbose=False)  # 256 = nanoGPT default (Karpathy 2023)
    return _gpt

def predict(data, invalidate_cache=False):
    global _gpt
    if invalidate_cache:
        _gpt = None  # 强制重新加载 (训练突破 best 时调用)
    gpt = _load(data)
    results = []
    seen = set()
    for temp in TEMPERATURES:
        p = gpt.predict(data, temperature=temp, use_swa=True)
        key = tuple(p["reds"])
        if key not in seen:
            seen.add(key)
            results.append({"reds": p["reds"], "blue": p["blue"]})
            if len(results) == 3:
                break
    return results

