"""
LSTM 序列预测模块。

借鉴 KittenCN/predict_Lottery_ticket 的 Embedding + LSTM + Softmax 架构：
- 每个号码通过 Embedding 层编码为稠密向量
- 对每个球位使用独立 LSTM 通道
- 全局 LSTM 建模球间依赖
- Softmax 输出每个号码的出现概率分布

红球: 6 个位置，33 类 → 6 × Softmax(33)
蓝球: 1 个位置，16 类 → 1 × Softmax(16)
"""

import os
import json
import pickle
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent
MODEL_DIR = ROOT / ".cache" / "lstm_models"

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")


def prepare_sequence_data(draws, window_size=5):
    """准备训练序列数据。

    Args:
        draws: [[period, r1..r6, blue], ...] sorted ascending
        window_size: 用过去 window_size 期预测下一期

    Returns:
        red_X, red_y: (N, window, 6), (N, 6) — 红球
        blue_X, blue_y: (N, window, 1), (N,) — 蓝球
    """
    reds = np.array([d[1:7] for d in draws], dtype=np.int32) - 1  # 0-based
    blues = np.array([d[7] for d in draws], dtype=np.int32) - 1

    red_X, red_y = [], []
    blue_X, blue_y = [], []

    for i in range(window_size, len(reds)):
        red_X.append(reds[i - window_size:i])
        red_y.append(reds[i])
        blue_X.append(blues[i - window_size:i].reshape(-1, 1))
        blue_y.append(blues[i])

    return (
        np.array(red_X, dtype=np.int32), np.array(red_y, dtype=np.int32),
        np.array(blue_X, dtype=np.int32), np.array(blue_y, dtype=np.int32),
    )


def build_lstm_red_model(window_size=None, num_classes=33, seq_len=6,
                         embedding_dim=None, hidden_units=None, dropout=None):
    from ml.ssq_constants import (
        LSTM_WINDOW_SIZE, LSTM_RED_EMBEDDING, LSTM_RED_HIDDEN, LSTM_RED_DROPOUT,
        LSTM_LEARNING_RATE, LSTM_CLIPNORM, TOTAL_RED,
    )
    if window_size is None: window_size = LSTM_WINDOW_SIZE
    if embedding_dim is None: embedding_dim = LSTM_RED_EMBEDDING
    if hidden_units is None: hidden_units = LSTM_RED_HIDDEN
    if dropout is None: dropout = LSTM_RED_DROPOUT

    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers

    inputs = layers.Input(shape=(window_size, seq_len), dtype=tf.int32, name="red_input")
    embedding = layers.Embedding(
        input_dim=num_classes, output_dim=embedding_dim,
        embeddings_initializer="he_normal", name="red_embedding"
    )(inputs)

    per_ball = layers.Permute((2, 1, 3), name="red_permute")(embedding)
    per_ball_encoded = layers.TimeDistributed(
        layers.LSTM(hidden_units[0], return_sequences=False),
        name="per_ball_lstm"
    )(per_ball)

    x = per_ball_encoded
    for idx, units in enumerate(hidden_units[1:], start=1):
        x = layers.LSTM(
            units, return_sequences=True,
            dropout=dropout, name=f"global_lstm_{idx}"
        )(x)

    x = layers.Dropout(dropout, name="dropout")(x)
    logits = layers.Dense(num_classes, name="logits")(x)
    outputs = layers.Activation("softmax", name="softmax")(logits)

    model = keras.Model(inputs, outputs, name="ssq_red_model")
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=LSTM_LEARNING_RATE, clipnorm=LSTM_CLIPNORM),
        loss=keras.losses.SparseCategoricalCrossentropy(),
        metrics=[keras.metrics.SparseCategoricalAccuracy(name="accuracy")],
    )
    return model


def build_lstm_blue_model(window_size=None, num_classes=16, seq_len=1,
                          embedding_dim=None, hidden_units=None, dropout=None):
    from ml.ssq_constants import (
        LSTM_WINDOW_SIZE, LSTM_BLUE_EMBEDDING, LSTM_BLUE_HIDDEN, LSTM_BLUE_DROPOUT,
        LSTM_LEARNING_RATE, LSTM_CLIPNORM,
    )
    if window_size is None: window_size = LSTM_WINDOW_SIZE
    if embedding_dim is None: embedding_dim = LSTM_BLUE_EMBEDDING
    if hidden_units is None: hidden_units = LSTM_BLUE_HIDDEN
    if dropout is None: dropout = LSTM_BLUE_DROPOUT

    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers

    inputs = layers.Input(shape=(window_size, seq_len), dtype=tf.int32, name="blue_input")
    embedding = layers.Embedding(
        input_dim=num_classes, output_dim=embedding_dim,
        embeddings_initializer="he_normal", name="blue_embedding"
    )(inputs)  # (batch, window, 1, embed_dim)

    x = layers.Reshape((window_size, embedding_dim), name="blue_reshape")(embedding)  # (batch, window, embed_dim)

    for idx, units in enumerate(hidden_units):
        x = layers.LSTM(
            units, return_sequences=(idx < len(hidden_units) - 1),
            dropout=dropout, name=f"blue_lstm_{idx}"
        )(x)

    x = layers.Dropout(dropout, name="blue_dropout")(x)
    logits = layers.Dense(num_classes, name="blue_logits")(x)
    outputs = layers.Activation("softmax", name="blue_softmax")(logits)

    model = keras.Model(inputs, outputs, name="ssq_blue_model")
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=LSTM_LEARNING_RATE, clipnorm=LSTM_CLIPNORM),
        loss=keras.losses.SparseCategoricalCrossentropy(),
        metrics=[keras.metrics.SparseCategoricalAccuracy(name="accuracy")],
    )
    return model


class LSTMPredictor:
    """LSTM 序列预测器。

    架构来源: KittenCN/predict_Lottery_ticket (GitHub)
    超参数来源:
      window_size=5: 用过去5期预测下期 (经验值, 彩票序列短期记忆)
      embedding_dim=64: 中等嵌入维度, 平衡表达力与过拟合风险
      hidden_units=(128, 64): 递减LSTM层, 参考 KittenCN 原架构
      dropout=0.3: 中等正则化, 防止小数据集过拟合
        Srivastava et al. (2014): "Dropout: A Simple Way to Prevent Neural Networks from Overfitting"
      learning_rate=1e-4, clipnorm=5.0:
        Nature Scientific Reports (2024) 推荐的小数据集训练配置
      epochs=300, EarlyStopping(patience=10):
        Keras 官方最佳实践 (2024), 配合 ReduceLROnPlateau 防止过拟合
        https://keras.io/api/callbacks/early_stopping/
    """

    def __init__(self, model_dir=None, window_size=5):
        self.model_dir = Path(model_dir) if model_dir else MODEL_DIR
        self.window_size = window_size
        self.red_model = None
        self.blue_model = None
        self._trained = False

    @property
    def is_trained(self):
        return self._trained

    def train(self, draws, epochs=None, batch_size=None, verbose=True):
        from ml.ssq_constants import (
            LSTM_EPOCHS, LSTM_BATCH_SIZE, LSTM_PATIENCE, LSTM_LR_FACTOR, LSTM_MIN_LR,
        )
        if epochs is None: epochs = LSTM_EPOCHS
        if batch_size is None: batch_size = LSTM_BATCH_SIZE

        import tensorflow as tf
        from tensorflow import keras

        red_X, red_y, blue_X, blue_y = prepare_sequence_data(draws, self.window_size)

        if len(red_X) < 20:
            if verbose:
                print("[LSTM] Not enough data for training (need >= 20 windows)")
            return False

        self.model_dir.mkdir(parents=True, exist_ok=True)

        # Red model
        self.red_model = build_lstm_red_model(
            window_size=self.window_size, hidden_units=(128, 64), dropout=0.3
        )
        if verbose:
            print(f"[LSTM] Training red model on {len(red_X)} windows, window={self.window_size}")
        self.red_model.fit(
            red_X, red_y,
            epochs=epochs, batch_size=batch_size,
            validation_split=0.1,
            callbacks=[
                keras.callbacks.EarlyStopping(patience=LSTM_PATIENCE, restore_best_weights=True),
                keras.callbacks.ReduceLROnPlateau(factor=LSTM_LR_FACTOR, patience=LSTM_PATIENCE//2, min_lr=LSTM_MIN_LR, verbose=0),
            ],
            verbose=1 if verbose else 0,
        )

        # Blue model
        self.blue_model = build_lstm_blue_model(
            window_size=self.window_size, hidden_units=(64,), dropout=0.2
        )
        if verbose:
            print(f"[LSTM] Training blue model on {len(blue_X)} windows")
        self.blue_model.fit(
            blue_X, blue_y,
            epochs=epochs, batch_size=batch_size,
            validation_split=0.1,
            callbacks=[
                keras.callbacks.EarlyStopping(patience=LSTM_PATIENCE, restore_best_weights=True),
                keras.callbacks.ReduceLROnPlateau(factor=LSTM_LR_FACTOR, patience=LSTM_PATIENCE//2, min_lr=LSTM_MIN_LR, verbose=0),
            ],
            verbose=1 if verbose else 0,
        )

        # Save
        self.red_model.save(str(self.model_dir / "red_model.keras"))
        self.blue_model.save(str(self.model_dir / "blue_model.keras"))
        with open(self.model_dir / "config.json", "w") as f:
            json.dump({"window_size": self.window_size}, f)

        self._trained = True
        return True

    def load(self):
        """加载已训练的模型。"""
        red_path = self.model_dir / "red_model.keras"
        blue_path = self.model_dir / "blue_model.keras"
        config_path = self.model_dir / "config.json"

        if not red_path.exists() or not blue_path.exists():
            return False

        import tensorflow as tf

        self.red_model = tf.keras.models.load_model(str(red_path))
        self.blue_model = tf.keras.models.load_model(str(blue_path))

        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
                self.window_size = config.get("window_size", 5)

        self._trained = True
        return True

    def predict(self, draws):
        """预测下一期号码。

        Returns:
            dict with 'reds', 'blue', 'red_probs', 'blue_probs'
        """
        if not self._trained:
            return None

        reds = np.array([d[1:7] for d in draws], dtype=np.int32) - 1
        blues = np.array([d[7] for d in draws], dtype=np.int32) - 1

        if len(reds) < self.window_size:
            return None

        # Prepare input
        red_X = reds[-self.window_size:].reshape(1, self.window_size, 6)
        blue_X = blues[-self.window_size:].reshape(1, self.window_size, 1)

        # Predict
        red_probs = self.red_model.predict(red_X, verbose=0)[0]  # (6, 33) — per position probs
        blue_probs = self.blue_model.predict(blue_X, verbose=0)[0]  # (16,)

        # Aggregate: sum probabilities across positions, then pick top 6
        red_agg = {i + 1: float(red_probs[:, i].sum()) for i in range(33)}
        blue_agg = {i + 1: float(blue_probs[i]) for i in range(16)}

        top6 = sorted(red_agg, key=lambda x: red_agg[x], reverse=True)[:6]
        top_blue = max(blue_agg, key=lambda x: blue_agg[x])

        return {
            "reds": sorted(top6),
            "blue": top_blue,
            "red_probs": {str(k): round(v, 4) for k, v in red_agg.items()},
            "blue_probs": {str(k): round(v, 4) for k, v in blue_agg.items()},
            "red_per_position": [[round(float(red_probs[p, i]), 4) for i in range(33)] for p in range(6)],
        }

    def validate_oot(self, draws, holdout=50):
        """Out-of-Time 验证: 留出最近holdout期，在早期数据训练，在留出集测试。"""
        import tensorflow as tf
        from tensorflow import keras

        total = len(draws)
        if total < holdout + self.window_size + 20:
            return {"ok": False, "msg": f"数据不足: {total} < {holdout + self.window_size + 20}"}

        train_draws = draws[:-holdout]
        red_X, red_y, blue_X, blue_y = prepare_sequence_data(train_draws, self.window_size)
        if len(red_X) < 20:
            return {"ok": False, "msg": "训练窗口不足"}

        # Train OOT models
        red_model = build_lstm_red_model(window_size=self.window_size, hidden_units=(128, 64), dropout=0.3)
        red_model.fit(red_X, red_y, epochs=100, batch_size=32, validation_split=0.1,
            callbacks=[keras.callbacks.EarlyStopping(patience=10, restore_best_weights=True),
                       keras.callbacks.ReduceLROnPlateau(factor=0.5, patience=5, min_lr=1e-6, verbose=0)],
            verbose=0)

        blue_model = build_lstm_blue_model(window_size=self.window_size, hidden_units=(64,), dropout=0.2)
        blue_model.fit(blue_X, blue_y, epochs=100, batch_size=32, validation_split=0.1,
            callbacks=[keras.callbacks.EarlyStopping(patience=10, restore_best_weights=True),
                       keras.callbacks.ReduceLROnPlateau(factor=0.5, patience=5, min_lr=1e-6, verbose=0)],
            verbose=0)

        # In-sample: last 20 of training
        is_hits = []
        for i in range(len(train_draws) - 20, len(train_draws)):
            window = draws[:i]
            actual = draws[i]
            if len(window) < self.window_size:
                continue
            reds_arr = np.array([d[1:7] for d in window], dtype=np.int32) - 1
            rX = reds_arr[-self.window_size:].reshape(1, self.window_size, 6)
            probs = red_model.predict(rX, verbose=0)[0]
            agg = {i + 1: float(probs[:, i].sum()) for i in range(33)}
            top6 = sorted(agg, key=lambda x: agg[x], reverse=True)[:6]
            is_hits.append(len(set(top6) & set(actual[1:7])))

        # OOT
        oot_hits = []
        oot_blue = 0
        for t_idx in range(holdout):
            cutoff = len(train_draws) + t_idx
            window = draws[:cutoff]
            actual = draws[cutoff]
            if len(window) < self.window_size:
                continue
            reds_arr = np.array([d[1:7] for d in window], dtype=np.int32) - 1
            rX = reds_arr[-self.window_size:].reshape(1, self.window_size, 6)
            probs = red_model.predict(rX, verbose=0)[0]
            agg = {i + 1: float(probs[:, i].sum()) for i in range(33)}
            top6 = sorted(agg, key=lambda x: agg[x], reverse=True)[:6]
            oot_hits.append(len(set(top6) & set(actual[1:7])))
            blues_arr = np.array([d[7] for d in window], dtype=np.int32) - 1
            bX = blues_arr[-self.window_size:].reshape(1, self.window_size, 1)
            bProbs = blue_model.predict(bX, verbose=0)[0]
            top_blue = int(bProbs.argmax()) + 1
            if top_blue == actual[7]:
                oot_blue += 1

        random_baseline = 1.09
        is_mean = sum(is_hits) / len(is_hits) if is_hits else 0
        oot_mean = sum(oot_hits) / len(oot_hits) if oot_hits else 0

        return {
            "ok": True,
            "train_draws": len(train_draws),
            "holdout_draws": holdout,
            "is_mean_red_hit": round(is_mean, 3),
            "oot_mean_red_hit": round(oot_mean, 3),
            "oot_blue_hit_rate": round(oot_blue / holdout, 3) if holdout > 0 else 0,
            "random_baseline": random_baseline,
            "oot_vs_random": round(oot_mean - random_baseline, 3),
            "delta_is_to_oot": round(is_mean - oot_mean, 3),
            "overfit_warning": (is_mean - oot_mean) > 0.3,
            "verdict": "beats_random" if oot_mean > random_baseline + 0.1 else (
                "at_random" if abs(oot_mean - random_baseline) <= 0.1 else "below_random"),
        }
