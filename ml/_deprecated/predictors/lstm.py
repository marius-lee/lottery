"""LSTM 预测器
架构: Embedding + Per-Ball LSTM + Global LSTM + Softmax
文件: ml/lstm_predictor.py
"""
from server import ml_bridge

def predict(data):
    r = ml_bridge.predict_lstm(data)
    if r:
        return {"reds": r["reds"], "blue": r["blue"]}
    return None
