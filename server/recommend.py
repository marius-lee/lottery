"""推荐引擎 — 频率 + 策略共识权重，生成复式/胆拖购买建议"""
import math

from server import db


def _comb(n, k):
    if k < 0 or k > n:
        return 0
    return math.comb(n, k)


def _freq_weights(data, total, max_n, is_red=True):
    """计算频率权重字典。"""
    weights = {}
    for n in range(1, max_n + 1):
        cnt = 0
        omission = total
        for d in range(total - 1, -1, -1):
            if is_red:
                hit = n in data[d][1:7]
            else:
                hit = data[d][7] == n
            if hit:
                cnt += 1
                omission = total - 1 - d
                break
        weights[n] = (cnt / total) * 0.6 + (1.0 - omission / total) * 0.4
    return weights


def generate_recommendations():
    all_data = db.load_draws()
    if not all_data or len(all_data) < 10:
        return None

    # 1. 频率权重（ML模型已归档，直接使用频率+遗漏）
    total = len(all_data)

    # 2. 频率+遗漏权重
    red_scores = _freq_weights(all_data, total, 33, is_red=True)
    blue_scores = _freq_weights(all_data, total, 16, is_red=False)

    top12 = sorted(red_scores, key=lambda x: red_scores[x], reverse=True)[:12]
    top4 = sorted(blue_scores, key=lambda x: blue_scores[x], reverse=True)[:4]

    # 4. 生成购买方案
    suggestions = []
    suggestions.append({"type": "单式 6+1", "reds": top12[:6], "blue": top4[0],
                        "tickets": 1, "cost": 2})
    if len(top12) >= 7:
        suggestions.append({"type": "复式 7+1", "reds": top12[:7], "blue": top4[0],
                            "tickets": 7, "cost": 14})
    if len(top12) >= 8:
        suggestions.append({"type": "复式 8+1", "reds": top12[:8], "blue": top4[0],
                            "tickets": 28, "cost": 56})
    if len(top12) >= 8 and len(top4) >= 2:
        suggestions.append({"type": "复式 8+2", "reds": top12[:8], "blues": top4[:2],
                            "tickets": 56, "cost": 112})
    if len(top12) >= 9:
        suggestions.append({"type": "复式 9+1", "reds": top12[:9], "blue": top4[0],
                            "tickets": 84, "cost": 168})
    if len(top12) >= 10:
        suggestions.append({"type": "复式 10+1", "reds": top12[:10], "blue": top4[0],
                            "tickets": 210, "cost": 420})

    # 胆拖方案
    if len(top12) >= 12:
        suggestions.append({"type": "胆拖 5+7 (1蓝)", "bankers": top12[:5], "drags": top12[5:12],
                            "blue": top4[0], "tickets": _comb(7, 1), "cost": _comb(7, 1) * 2})
    if len(top12) >= 12:
        suggestions.append({"type": "胆拖 4+8 (1蓝)", "bankers": top12[:4], "drags": top12[4:12],
                            "blue": top4[0], "tickets": _comb(8, 2), "cost": _comb(8, 2) * 2})
    if len(top12) >= 12:
        suggestions.append({"type": "胆拖 3+9 (1蓝)", "bankers": top12[:3], "drags": top12[3:12],
                            "blue": top4[0], "tickets": _comb(9, 3), "cost": _comb(9, 3) * 2})
    if len(top12) >= 12 and len(top4) >= 2:
        suggestions.append({"type": "胆拖 4+8 (2蓝)", "bankers": top12[:4], "drags": top12[4:12],
                            "blues": top4[:2], "tickets": _comb(8, 2) * 2,
                            "cost": _comb(8, 2) * 2 * 2})

    return {
        "hasML": False,
        "reds": [{"n": n, "score": red_scores[n]} for n in top12],
        "blues": [{"n": n, "score": blue_scores[n]} for n in top4],
        "top12_reds": top12,
        "top4_blues": top4,
        "suggestions": suggestions,
    }
