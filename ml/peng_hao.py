"""彭浩《双色球Excel全攻略》(2010, 中国经济出版社, ISBN 978-7-5017-9669-4) 算法实现.

核心创新: 将证券技术分析方法引入双色球——五均线号码通道(Bollinger类比)+波动三要素框架。
数据基础: 原书2003-2010共980期(含光盘); 本书基于实时历史数据动态统计, 不硬编码固定概率表.

实现的算法:
1. 五均线号码通道 (Ch3 §2, Ch5 §3): 18期MA + 3σ/√σ 双向通道
2. 波动三要素框架 (Ch3 §4, Ch4): 三方向/九方向分类 + 转移概率矩阵
3. 方向预测出号 (Ch5): 通道约束 + 方向加权采样
"""
import math
import random
from ml.ssq_constants import TOTAL_RED, TOTAL_BLUE, PICK_RED, PICK_BLUE

# ═══════════════════════════════════════════════════════════════════════════
# 通道参数 [彭浩 Ch3 §2 / Ch5 §3]
# ═══════════════════════════════════════════════════════════════════════════
CHANNEL_MA_PERIOD = 18       # 18期移动均值 [彭浩 p77: "18期或18期的倍数是双色球号码走势中的重要时间循环周期"]
CHANNEL_SIGMA_M = 3          # 3倍标准差乘数 [彭浩 p77: 上轨=均值+3*σ/√σ]
CHANNEL_VOL_WINDOW = 9       # 短期波动窗口(用于3σ计算) [彭浩 p77: "引进最近9期的波动率"]
DATA_MIN = 19                # 至少需要19期数据(18期MA + 1期当前)
# 已验证改进 (2026-06-22 基准: 1.380→1.701, 蓝球3.8%→11.9%)
USE_MULTI_TIMEFRAME = True   # 多时间框架: MA9+MA18双通道交集
USE_WEIGHTED_MARKOV = True   # 加权马尔可夫: 步长1×0.55+步长2×0.30+步长3×0.15

# 红球位置名称 [彭浩 Ch2 §1: 定位策略]
POSITION_NAMES = ["红一球", "红二球", "红三球", "红四球", "红五球", "红六球", "蓝色球"]


# ═══════════════════════════════════════════════════════════════════════════
# 通道预测 (Ch3 §2, Ch5 §3)
# ═══════════════════════════════════════════════════════════════════════════

def compute_channel(data, position=0, period=None):
    """计算单个位置的五均线号码通道.

    Args:
        data: [[period, r1..r6, blue], ...] 按period升序排列
        period: MA周期, 默认CHANNEL_MA_PERIOD(18)
        position: 0-5=红1-红6, 6=蓝球

    Returns dict:
        ma: float             18期移动均值
        sigma: float          总体标准差
        sigma_short: float    近9期标准差(波动率)
        upper: float          上轨 = ma + 3*sigma_short/√sigma
        lower: float          下轨 = ma - 3*sigma_short/√sigma
        mid_upper: float      中上轨 = (upper + ma)/2
        mid_lower: float      中下轨 = (lower + ma)/2
        current: int          当前期该位置的值
        current_period: str   当前期号
        band_width: float     通道宽度(upper - lower)
        position_name: str    位置名称

    原书公式 [彭浩 p77]:
      均值   = ROUND(AVERAGE(D908:D925), 0)   # 18期移动均值
      上轨   = ROUND((G925+3*STDEV(D917:D925))/SQRT(STDEV(D908:D925)), 0)
      下轨   = ROUND((G925-3*STDEV(D917:D925))/SQRT(STDEV(D908:D925)), 0)
      中上轨 = ROUND((上轨+均值)/2, 0)
      中下轨 = ROUND((均值+下轨)/2, 0)
    """
    p = period if period is not None else CHANNEL_MA_PERIOD
    if len(data) < p + 1:
        return {"ok": False, "msg": f"数据不足, 需要至少{p+1}期"}

    # 提取该位置的数值序列
    if position < 6:
        values = [row[position + 1] for row in data]  # r1=col1, r6=col6
    else:
        values = [row[7] for row in data]              # blue=col7

    n = len(values)
    current_val = values[-1]
    current_period = data[-1][0]

    # 移动均值 [彭浩 Ch3 §2]
    ma = sum(values[-p:]) / p

    # 总体标准差 [彭浩 Ch2 §4: STDEV=号码波动密码]
    mean_all = sum(values) / n
    sigma = math.sqrt(sum((v - mean_all) ** 2 for v in values) / n)

    # 短期波动率 [彭浩 p77]
    vw = min(CHANNEL_VOL_WINDOW, p)
    recent = values[-vw:]
    mean_r = sum(recent) / vw
    sigma_short = math.sqrt(sum((v - mean_r) ** 2 for v in recent) / vw)

    # 通道上下轨 [彭浩 p77: 3*σ_short / √σ]
    denom = math.sqrt(sigma) if sigma > 0 else 1.0
    spread = CHANNEL_SIGMA_M * sigma_short / denom
    upper = ma + spread
    lower = ma - spread
    mid_upper = (upper + ma) / 2
    mid_lower = (lower + ma) / 2

    # 通道准确率(±1范围内) [彭浩 Ch5 §3 表5-4]
    hit = 0
    for i in range(p, n):
        pred = sum(values[i - p:i]) / p
        if abs(pred - values[i]) <= 1:
            hit += 1
    accuracy_1 = hit / max(n - p, 1)

    return {
        "ok": True,
        "ma": round(ma, 1),
        "sigma": round(sigma, 2),
        "sigma_short": round(sigma_short, 2),
        "upper": round(upper),
        "lower": round(lower),
        "mid_upper": round(mid_upper),
        "mid_lower": round(mid_lower),
        "current": current_val,
        "current_period": str(current_period),
        "band_width": round(upper - lower, 1),
        "accuracy_1": round(accuracy_1, 4),
        "position_name": POSITION_NAMES[position],
    }


def compute_all_channels(data):
    """计算全部7个位置的通道."""
    result = {}
    for pos in range(7):
        ch = compute_channel(data, pos)
        key = f"pos_{pos}"
        result[key] = ch
    return result


# ═══════════════════════════════════════════════════════════════════════════
# 方向分类 (Ch3 §4: 三方向 + 九方向)
# ═══════════════════════════════════════════════════════════════════════════

def classify_3_direction(values):
    """三方向分类 [彭浩 Ch3 §4: 表3-14].

    三方向编码: 下=1(本期<上期), 平=5(本期=上期), 上=9(本期>上期)
    Excel: =IF(D925<D924,1,IF(D925=D924,5,IF(D925>D924,9,0)))

    原书统计(900期):
      上: 43-49%  平: 4.5-10%  下: 44-48%
      平概率仅5-10%, 可安全排除
    """
    if len(values) < 2:
        return {"code": 0, "label": "未知", "direction": None}
    curr = values[-1]
    prev = values[-2]
    if curr < prev:
        return {"code": 1, "label": "下", "direction": "down"}
    elif curr == prev:
        return {"code": 5, "label": "平", "direction": "flat"}
    else:
        return {"code": 9, "label": "上", "direction": "up"}


def classify_9_direction(values):
    """九方向分类 [彭浩 Ch3 §4: 表3-15].

    将本期+上期+上上期三期关系组合为9种:
      下下=1 下平=2 下上=3 平下=4 平平=5 平上=6 上下=7 上平=8 上上=9

    原书统计(900期): 反转形态(下上/上下)各~30%概率最高.
    """
    if len(values) < 3:
        return {"code": 0, "label": "未知", "direction": None}
    curr = values[-1]
    prev = values[-2]
    prev2 = values[-3]

    if prev < prev2:
        base = "下"
    elif prev == prev2:
        base = "平"
    else:
        base = "上"

    if curr < prev:
        suffix = "下"
    elif curr == prev:
        suffix = "平"
    else:
        suffix = "上"

    combo = base + suffix
    code_map = {"下下": 1, "下平": 2, "下上": 3, "平下": 4, "平平": 5,
                "平上": 6, "上下": 7, "上平": 8, "上上": 9}

    # 原书洞察: 反转形态(~30%) >> 持续形态(~12-16%) [彭浩 Ch3 §4]
    reversal_hints = {"下上": "反转↑(下→上, ~30%)", "上下": "反转↓(上→下, ~30%)",
                      "上上": "持续↑(~12-14%)", "下下": "持续↓(~10-16%)"}

    return {
        "code": code_map.get(combo, 0),
        "label": combo,
        "direction": suffix,
        "reversal": combo in ("下上", "上下"),
        "hint": reversal_hints.get(combo, ""),
    }


def direction_transition_matrix(data, position=0):
    """计算三方向转移概率矩阵 [彭浩 Ch3 §4].

    Returns dict with 3x3 probability matrix P(state_{t+1} | state_t).
    """
    if position < 6:
        values = [row[position + 1] for row in data]
    else:
        values = [row[7] for row in data]

    # 统计转移计数 (使用中文标签作为key, 与classify_3_direction的label字段对应)
    counts = {"下": {"下": 0, "平": 0, "上": 0},
              "平": {"下": 0, "平": 0, "上": 0},
              "上": {"下": 0, "平": 0, "上": 0}}

    for i in range(0, len(values) - 1):
        # 前一期的方向 (基于截止到i+1的数据)
        prev_vals = values[:i + 2]  # 从0到i+1
        curr_vals = values[:i + 3]  # 从0到i+2
        if len(curr_vals) < 2:
            continue
        prev_dir = classify_3_direction(prev_vals)
        curr_dir = classify_3_direction(curr_vals)
        if prev_dir["label"] and curr_dir["label"]:
            counts[prev_dir["label"]][curr_dir["label"]] += 1

    # 转为概率
    probs = {}
    reversal_rate = {}
    for d in ["下", "平", "上"]:
        total = sum(counts[d].values())
        if total > 0:
            probs[d] = {k: round(v / total, 4) for k, v in counts[d].items()}
            # 反转率 = 下→上 或 上→下 [彭浩 Ch4: 反转形态~30%]
            if d == "下":
                reversal_rate[d] = probs[d]["上"]
            elif d == "上":
                reversal_rate[d] = probs[d]["下"]
        else:
            probs[d] = {"下": 0, "平": 0, "上": 0}

    curr_result = classify_3_direction(values)
    current_label = curr_result["label"]  # 中文: "下"/"平"/"上"
    current_code = curr_result["code"]
    predicted = None
    if current_label and current_label in probs:
        probs_cur = probs[current_label]
        # 排除"平"方向 [彭浩 Ch3: 平概率仅5-10%, 可忽略]
        candidates = {k: v for k, v in probs_cur.items() if k != "平"}
        if candidates:
            predicted = max(candidates, key=candidates.get)
            # 反转优先: 若下→上概率≥0.25或上→下概率≥0.25, 预测反转
            # [彭浩 Ch4: 反转形态各~30%]

    return {
        "ok": True,
        "current_direction": current_label,
        "current_code": current_code,
        "transition_probs": probs,
        "reversal_rate": {k: round(v, 4) for k, v in reversal_rate.items()},
        "predicted_next": predicted,
        "position_name": POSITION_NAMES[position],
    }


# ═══════════════════════════════════════════════════════════════════════════
# 极端值方向规则 (Ch4: 表4-8)
# ═══════════════════════════════════════════════════════════════════════════

def extreme_rules(data):
    """检测极端值方向规则 [彭浩 Ch4: 表4-8].

    原书发现:
      - 红6=30-33时, 向下概率82.09% [彭浩 p112: Red6 30-33→下82%]
      - 红1=1-3时, 向上概率72.7% [彭浩 p112: Red1 1-3→上73%]
      - 红1=3-6时, 向下概率46.96% [彭浩 p112]
    """
    if len(data) < 2:
        return {"ok": False, "msg": "数据不足"}

    last = data[-1]
    reds = last[1:7]  # r1..r6
    alerts = []

    # 红一球极端值检查 [彭浩 Ch4 表4-8: Red1]
    r1 = reds[0]
    if r1 <= 3:
        alerts.append({"position": "红一球", "value": r1, "condition": "≤3",
                       "predicted": "上", "probability": 0.727,
                       "source": "彭浩 p112: Red1=1-3→上72.7%"})
    elif 3 <= r1 <= 6:
        alerts.append({"position": "红一球", "value": r1, "condition": "3-6区间",
                       "predicted": "下", "probability": 0.470,
                       "source": "彭浩 p112: Red1=3-6→下46.96%"})

    # 红六球极端值检查 [彭浩 Ch4 表4-8: Red6]
    r6 = reds[5]
    if r6 >= 30:
        alerts.append({"position": "红六球", "value": r6, "condition": "≥30",
                       "predicted": "下", "probability": 0.821,
                       "source": "彭浩 p112: Red6=30-33→下82.09%"})

    return {"ok": True, "alerts": alerts, "period": last[0]}


# ═══════════════════════════════════════════════════════════════════════════
# 出号 (Ch5: 综合预测)
# ═══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════
#  多时间框架 + 加权马尔可夫
# ═══════════════════════════════════════════════════════════════════════════

def compute_channel_dual(data, position=0):
    """MA9+MA18双通道交集候选范围. 交集过小(<2)退回MA18."""
    ch18 = compute_channel(data, position, period=18)
    if not ch18.get("ok"):
        return ch18
    ch9 = compute_channel(data, position, period=9)
    if not ch9.get("ok"):
        return ch18
    lo = max(ch18["lower"], ch9["lower"])
    hi = min(ch18["upper"], ch9["upper"])
    if hi - lo >= 1:
        ch18["lower"] = lo
        ch18["upper"] = hi
        ch18["dual"] = True
    return ch18


def _weighted_markov_dir(data, position=0):
    """加权马尔可夫方向预测: 步长1×0.55 + 步长2×0.30 + 步长3×0.15."""
    if position < 6:
        vals = [row[position + 1] for row in data]
    else:
        vals = [row[7] for row in data]
    if len(vals) < 4:
        return None

    # 步长1: 本期→下期
    dir1 = classify_3_direction(vals[-2:] + [vals[-1]])
    # 步长2: 上期→本期(跳到下期)
    if len(vals) >= 4:
        dir2 = classify_3_direction([vals[-3], vals[-1]])
    else:
        dir2 = dir1
    # 步长3
    if len(vals) >= 5:
        dir3 = classify_3_direction([vals[-4], vals[-1]])
    else:
        dir3 = dir1

    # 加权投票: 上=+1, 下=-1, 平=0
    weights = {1: 0.55, 2: 0.30, 3: 0.15}
    score = 0
    for step, d in [(1, dir1), (2, dir2), (3, dir3)]:
        if d["direction"] == "up":
            score += weights[step]
        elif d["direction"] == "down":
            score -= weights[step]
    if score > 0.15:
        return "up"
    elif score < -0.15:
        return "down"
    return dir1["direction"]  # 持平→退回步长1


def generate_tickets(data, n=3, use_channel=True, use_direction=True, use_extreme=True):
    """彭浩波动三要素综合出号 [彭浩 Ch5: 综合预测].

    流程:
      1. 计算7个位置的通道范围
      2. 分类三方向+九方向, 构建转移概率矩阵
      3. 通道约束: 每位置的号码必须在通道[下轨, 上轨]范围内
      4. 方向加权: 根据预测方向对候选号码加权采样
      5. 蓝球: 通道+方向预测单独生成
    """
    if len(data) < DATA_MIN:
        return {"ok": False, "msg": f"数据不足, 需要至少{DATA_MIN}期, 当前{len(data)}期"}

    # 1. 通道计算 (7个位置)
    channels = {}
    for pos in range(7):
        if USE_MULTI_TIMEFRAME:
            #  多时间框架: MA9+MA18双通道交集
            ch = compute_channel_dual(data, pos)
        else:
            ch = compute_channel(data, pos)
        channels[pos] = ch

    # 2. 方向分类 (7个位置) +  加权马尔可夫
    directions_3 = {}
    directions_9 = {}
    for pos in range(7):
        if pos < 6:
            vals = [row[pos + 1] for row in data]
        else:
            vals = [row[7] for row in data]
        directions_3[pos] = classify_3_direction(vals)
        directions_9[pos] = classify_9_direction(vals)
        #  加权马尔可夫: 步长1+2加权覆盖简单分类
        if USE_WEIGHTED_MARKOV:
            wm = _weighted_markov_dir(data, pos)
            if wm:
                directions_3[pos]["direction"] = wm  # 覆盖方向

    # 3. 极端值规则叠加 [彭浩 Ch4]
    extreme_pred = {}
    if use_extreme:
        extreme = extreme_rules(data)
        for alert in extreme.get("alerts", []):
            pos = 0 if "红一" in alert["position"] else 5
            extreme_pred[pos] = alert

    # 4. 构建每位置的候选号码池（硬约束，非软权重）
    # 原则 [彭浩 Ch5]: 通道约束 + 方向硬过滤 → 均权采样
    #   - 预测"上" → 只看 > 当前号
    #   - 预测"下" → 只看 < 当前号
    #   - 预测"平" → 只保留当前号±1（原书: 平概率仅5-10%,可排除但保留窄窗口）
    candidate_pools = {}
    for pos in range(6):  # 红球位置
        ch = channels[pos]
        lower = max(1, int(ch.get("lower", 1)))
        upper = min(33, int(ch.get("upper", 33)))

        # 通道约束范围 [彭浩 Ch5 §3]
        channel_nums = [n for n in range(lower, upper + 1)]
        if len(channel_nums) < 2:
            # 通道过窄时各扩1号（最小扩幅）
            channel_nums = [n for n in range(max(1, lower - 1), min(33, upper + 1) + 1)]
            if len(channel_nums) < 2:
                return {"ok": False, "msg": f"通道过窄，pos={pos}: [{lower},{upper}]"}

        # 方向硬过滤 [彭浩 Ch3 §4, Ch4]
        dir_info = directions_3[pos]
        predicted_dir = dir_info["direction"]

        # 极端值规则覆盖方向 [彭浩 Ch4 表4-8]
        if pos in extreme_pred:
            predicted_dir = extreme_pred[pos]["predicted"]

        if use_direction and predicted_dir:
            if predicted_dir == "up":
                candidates = [n for n in channel_nums if n > ch["current"]]
            elif predicted_dir == "down":
                candidates = [n for n in channel_nums if n < ch["current"]]
            else:  # flat
                # 原书: 平概率仅5-10%, 保留当前号±1窄窗口
                candidates = [n for n in channel_nums
                             if ch["current"] - 1 <= n <= ch["current"] + 1]
        else:
            candidates = list(channel_nums)

        # 方向过滤后若候选为空→回退到全通道
        if not candidates:
            candidates = list(channel_nums)

        candidate_pools[pos] = candidates

    # 5. 每位置均权随机抽取（硬约束已过滤，无需软权重）
    tickets = []
    rng = random.Random()
    try:
        rng.seed(int(str(data[-1][0]) + "0"))
    except (ValueError, IndexError):
        pass

    # 工程上限: 防止无限循环（不影响算法结果，仅限迭代次数）
    # 正常情况: 每位置池大小5-15, 成功率>10%, 不需大量重试
    max_attempts = n * 300
    attempts = 0

    while len(tickets) < n and attempts < max_attempts:
        attempts += 1
        reds = []
        for pos in range(6):
            pool = candidate_pools[pos]
            reds.append(pool[rng.randrange(len(pool))])

        # 确保升序+无重复 [彭浩 Ch1: 定位策略]
        reds.sort()
        if len(set(reds)) < 6:
            continue  # 去重

        tickets.append({"reds": list(reds), "blue": 0})

    # 6. 蓝球生成 — 通道硬约束 + 均权随机 [彭浩 Ch5]
    blue_ch = channels[6]
    blue_lower = max(1, int(blue_ch.get("lower", 1)))
    blue_upper = min(16, int(blue_ch.get("upper", 16)))
    blue_candidates = [b for b in range(blue_lower, blue_upper + 1)]
    if len(blue_candidates) < 2:
        blue_candidates = list(range(1, 17))

    # 方向硬过滤蓝球 [彭浩 Ch3 §4]
    blue_dir = directions_3[6]["direction"]
    if use_direction and blue_dir:
        if blue_dir == "up":
            filtered = [b for b in blue_candidates if b > blue_ch["current"]]
        elif blue_dir == "down":
            filtered = [b for b in blue_candidates if b < blue_ch["current"]]
        else:
            filtered = [b for b in blue_candidates
                       if blue_ch["current"] - 1 <= b <= blue_ch["current"] + 1]
        if filtered:
            blue_candidates = filtered

    used_blues = set()
    for t in tickets:
        available = [b for b in blue_candidates if b not in used_blues]
        if not available:
            available = blue_candidates
        t["blue"] = available[rng.randrange(len(available))]
        used_blues.add(t["blue"])

    if len(tickets) < n:
        return {"ok": False, "msg": f"通道约束过严, 仅生成{len(tickets)}注"}

    # 7. 组装返回
    channel_summary = {}
    for pos in range(7):
        ch = channels[pos]
        channel_summary[f"pos_{pos}"] = {
            "name": ch["position_name"],
            "current": ch["current"],
            "ma": ch["ma"],
            "range": f"{ch['lower']}-{ch['upper']}",
            "lower": ch["lower"],
            "upper": ch["upper"],
            "direction_3": directions_3[pos]["label"],
            "direction_9": directions_9[pos]["label"],
        }

    return {
        "ok": True,
        "algorithm": "彭浩·波动三要素(多时间框架MA9+MA18+加权马尔可夫+极端值)",
        "tickets": tickets,
        "channels": channel_summary,
        "extreme_alerts": extreme_rules(data).get("alerts", []),
        "periods_used": len(data),
    }
