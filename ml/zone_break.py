"""断区转换法 (刘大军 2014, 《双色球终极战法》第2版 第2章)

将33个红球按6行×6列排列, 每期有1-2行/列不出现中奖号码(断区).
将断区位置编码为3D号码, 通过3D走势分析研判下期断区.
"""
from ml.ssq_constants import TICKET_PRICE

# 6×6行列分布表 (刘大军 p27)
ROW_MAP = {
    1: [1,2,3,4,5,6], 2: [7,8,9,10,11,12], 3: [13,14,15,16,17,18],
    4: [19,20,21,22,23,24], 5: [25,26,27,28,29,30], 6: [31,32,33]
}
COL_MAP = {
    1: [1,7,13,19,25,31], 2: [2,8,14,20,26,32], 3: [3,9,15,21,27,33],
    4: [4,10,16,22,28], 5: [5,11,17,23,29], 6: [6,12,18,24,30]
}
ALL_3D_CODES = [
    "000","001","002","003","004","005","006",
    "012","013","014","015","016","023","024","025","026",
    "034","035","036","045","046","056",
    "123","124","125","126","134","135","136","145","146","156",
    "234","235","236","245","246","256","345","346","356","456"
]


def get_zone_break_history(data, window=30):
    """计算最近window期的断行/断列3D号码历史。
    window=30: [工程] 30期≈5个月, 足够覆盖断区变化周期
    """

    Returns: {
        "periods": ["2013144", ...],
        "break_rows": ["045", ...],  # 每期的断行3D号
        "break_cols": ["024", ...],  # 每期的断列3D号
        "distribution": [[row_data], ...],  # 6×6表格: 每格=最近N期出现次数
    }
    """
    recent = data[-window:] if len(data) >= window else data

    # 统计6×6表格每格出现次数
    dist = [[0]*6 for _ in range(6)]
    for row in recent:
        reds = sorted(row[1:7])
        for r in reds:
            ri = (r-1)//6  # 行号0-5 (0=01-06, 5=31-33)
            ci = (r-1)%6   # 列号0-5
            if ri < 6 and ci < 6:
                dist[ri][ci] += 1

    # 计算每期的断行/断列3D号
    periods = []
    break_rows_list = []
    break_cols_list = []
    for row_data in recent:
        periods.append(str(row_data[0]))
        reds = sorted(row_data[1:7])
        rows_with_reds = set()
        cols_with_reds = set()
        for r in reds:
            ri = (r-1)//6
            ci = (r-1)%6
            if ri < 6: rows_with_reds.add(ri+1)
            if ci < 6: cols_with_reds.add(ci+1)

        # 断行 = 没有红球的行的编号 (按从小到大)
        break_r = sorted([i for i in range(1,7) if i not in rows_with_reds])
        break_c = sorted([i for i in range(1,7) if i not in cols_with_reds])

        # 编码为3D号码 (不足3位补0或00)
        def encode_3d(lst):
            if len(lst) == 0: return "000"
            if len(lst) >= 3: return "".join(str(x) for x in lst[:3])
            s = "".join(str(x) for x in lst)
            if len(s) == 1: return "00" + s
            if len(s) == 2: return "0" + s
            return "000"
        break_rows_list.append(encode_3d(break_r))
        break_cols_list.append(encode_3d(break_c))

    return {
        "periods": periods,
        "break_rows": break_rows_list,
        "break_cols": break_cols_list,
        "distribution": dist,
    }


def filter_zone_break(break_rows_code, break_cols_code):
    """按断行/断列3D码过滤_valid_reds全量池。

    Args:
        break_rows_code: 断行3D码, 如 "045" (第0/4/5行断区). "000"=不断行.
        break_cols_code: 断列3D码, 如 "024" (第0/2/4列断区). "000"=不断列.

    Returns:
        dict with tickets, filter_log
    """
    from server.db import load_draws
    import ml.micro_portfolio as mp

    data = load_draws()
    if len(data) < 5:
        return {"ok": False, "msg": "数据不足"}

    # 确保_valid_reds已构建
    try:
        if mp._valid_reds is None or len(data) != mp._past_count:
            mp._build_pool()
    except Exception:
        mp._build_pool()

    valid_reds = mp._valid_reds
    if valid_reds is None or len(valid_reds) < 6:
        return {"ok": False, "msg": "有效池未构建"}

    # 解析3D码
    def parse_3d(code):
        code = code.strip()
        if code == "000": return set()
        # 去前导0
        s = code.lstrip("0")
        if not s: return set()
        return {int(c) for c in s}

    break_rows = parse_3d(break_rows_code)
    break_cols = parse_3d(break_cols_code)

    # 构建被排除的号码集合
    excluded = set()
    for ri in break_rows:
        if ri in ROW_MAP:
            excluded.update(ROW_MAP[ri])
    for ci in break_cols:
        if ci in COL_MAP:
            excluded.update(COL_MAP[ci])

    # 过滤
    n_combos = len(valid_reds) // 6
    filtered = []
    for idx in range(n_combos):
        base = idx * 6
        reds = valid_reds[base:base+6]
        if not any(r in excluded for r in reds):
            filtered.extend(reds)

    n = len(filtered) // 6

    # 蓝球分配
    from ml.micro_portfolio import _blue_freq_weights, _pick_blue
    blue_weights = _blue_freq_weights()
    used_blues = set()
    tickets = []
    for idx in range(n):
        base = idx * 6
        reds = list(filtered[base:base+6])
        blue = _pick_blue(blue_weights)
        used_blues.add(blue)
        tickets.append({"reds": reds, "blue": blue})

    return {
        "ok": True,
        "algorithm": f"ZoneBreak(R{break_rows_code}C{break_cols_code})",
        "tickets": tickets,
        "budget": len(tickets),
        "cost_rmb": len(tickets) * TICKET_PRICE,
        "filter_log": {
            "total_valid_combos": n_combos,
            "excluded_numbers": sorted(excluded),
            "final_count": len(tickets),
        },
    }
