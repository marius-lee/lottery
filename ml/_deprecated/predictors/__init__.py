"""预测器注册表 — 每个模型独立文件, 统一接口 predict(data) → {reds, blue}"""
from ml.predictors import gpt, xgb, lstm, thompson, lasso

ALL = {
    "gpt":       gpt,
    "xgb":       xgb,
    "lstm":      lstm,
    "thompson":  thompson,
    "lasso":     lasso,
}

def predict_all(data, models=None):
    """运行指定模型, 返回 [{reds, blue, model}, ...].
    GPT返回list, 其他返回单dict."""
    if models is None:
        models = ALL.keys()
    results = []
    for name in models:
        try:
            p = ALL[name].predict(data)
            if isinstance(p, list):
                for item in p:
                    if item:
                        item["model"] = name
                        results.append(item)
            elif p:
                p["model"] = name
                results.append(p)
        except Exception as e:
            results.append({"model": name, "error": str(e)})
    return results
