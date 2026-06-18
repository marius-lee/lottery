"""LASSO 预测器
架构: L1正则化稀疏偏差检测, 闭式软阈值解
文件: ml/compressed_sensing.py
参考: Candès & Wakin (2008), Donoho (2006)
"""
from ml.compressed_sensing import lasso_top_balls

def predict(data):
    hot = lasso_top_balls(data, n_top=6)
    bf = {}
    for r in data:
        bf[r[7]] = bf.get(r[7], 0) + 1
    return {"reds": sorted(hot), "blue": max(bf, key=bf.get)}
