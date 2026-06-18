"""XGBoost 预测器
架构: 49个独立二分类器 (33红+16蓝), 15维特征
文件: ml/xgb_predictor.py
"""
from server import ml_bridge

def predict(data):
    r = ml_bridge.predict_xgb(data)
    if r:
        return {"reds": r["reds"], "blue": r["blue"]}
    return None
