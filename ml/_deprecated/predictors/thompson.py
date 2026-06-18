"""Thompson Sampling 预测器
架构: Beta后验采样, 贝叶斯多臂老虎机
文件: ml/thompson_sampler.py
参考: Thompson (1933) Biometrika
"""
from ml.thompson_sampler import ThompsonSampler

def predict(data):
    ts = ThompsonSampler()
    ts.update(data)
    t = ts.predict(1)[0]
    return {"reds": t["reds"], "blue": t["blue"]}
