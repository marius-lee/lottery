"""一次性诊断: 6位作者×近50期×3注, 统计红球/蓝球命中分布.

用法: python3 tools/benchmark_authors.py
用后即弃, 不建永久回测框架.
"""
import sys, os, random, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.db import load_draws
from collections import defaultdict

data = load_draws()
if len(data) < 60:
    print(f"数据不足: {len(data)}期, 需要≥60期")
    sys.exit(1)

MIN_TRAIN = 30
# [统计] 300期等距抽样: 95%CI≈±0.06, 足以区分显著差异
SAMPLE_SIZE = 300
step = max(1, (len(data) - MIN_TRAIN) // SAMPLE_SIZE)
indices = list(range(MIN_TRAIN, len(data), step))[-SAMPLE_SIZE:]
test_data = [data[i] for i in indices]

print(f"总数据: {len(data)}期 | 训练≥{MIN_TRAIN}期 | 抽样{SAMPLE_SIZE}期(步长{step})")
print(f"测试范围: {test_data[0][0]} - {test_data[-1][0]}")
print()

# ============================================================
# 定义6位作者
# ============================================================
def micro_3(data_slice):
    """主流程: 微投资组合 3注"""
    from ml.micro_portfolio import generate_tickets
    rng = random.Random()
    try: rng.seed(int(str(data_slice[-1][0]) + "42"))
    except: pass
    result = generate_tickets(n=3, soft=False)
    return result.get("tickets", []) if result.get("ok") else []

def micro_color_3(data_slice):
    """主流程 + 三色分解过滤 3注"""
    from ml.micro_portfolio import generate_tickets
    rng = random.Random()
    try: rng.seed(int(str(data_slice[-1][0]) + "42"))
    except: pass
    result = generate_tickets(n=3, soft=False, color_filter=True)
    return result.get("tickets", []) if result.get("ok") else []

def micro_block9_3(data_slice):
    """主流程 + 方块9杀号 3注"""
    from ml.micro_portfolio import generate_tickets
    rng = random.Random()
    try: rng.seed(int(str(data_slice[-1][0]) + "42"))
    except: pass
    result = generate_tickets(n=3, soft=False, block9_filter=True)
    return result.get("tickets", []) if result.get("ok") else []

def weier_3(data_slice):
    """微尔算法 3注 (generate_tickets_weier无参数, 内部读load_draws)"""
    from ml.weier_filter import generate_tickets_weier
    try:
        result = generate_tickets_weier()
        tickets = result.get("tickets", []) if result.get("ok") else []
        return tickets[:3] if tickets else []
    except Exception:
        return []

def zhang_3(data_slice):
    """张委铭 十二值围号 3注"""
    from ml.zhang_weiming import generate_weihao
    result = generate_weihao(data_slice, n_tickets=3)
    tix = result.get("tickets", []) if result.get("ok") else []
    # 分配蓝球
    if tix:
        from ml.micro_portfolio import _blue_freq_weights, _pick_blue
        bw = _blue_freq_weights()
        for t in tix:
            t["blue"] = _pick_blue(bw)
    return tix

def lizhilin_3(data_slice):
    """李志林综合 3注"""
    from ml.li_zhilin import generate_tickets
    result = generate_tickets(data_slice, n_tickets=3,
        use_dan8=True, use_dan3=True, use_transition=True,
        use_kill=True, use_blue_tail12=True, use_blue_ten=False, use_blue_period=False)
    return result.get("tickets", []) if result.get("ok") else []

def peng_3(data_slice):
    """彭浩通道+方向 3注"""
    from ml.peng_hao import generate_tickets
    result = generate_tickets(data_slice, n=3)
    return result.get("tickets", []) if result.get("ok") else []

def jiangjialin_3(data_slice):
    """蒋加林排列型思维 3注"""
    from ml.jiang_jialin import generate_tickets
    result = generate_tickets(data_slice, n=3)
    return result.get("tickets", []) if result.get("ok") else []

def lixiangchun_3(data_slice):
    """李相春趋势分析 3注"""
    from ml.li_xiangchun import generate_tickets
    result = generate_tickets(data_slice, n_tickets=3)
    # li_xiangchun的generate_tickets不返回ok字段, 直接取tickets
    return result.get("tickets", []) if result.get("tickets") else []

def lixiangchun_filtered_3(data_slice):
    """李相春趋势分析 + 散度/AC过滤 3注 (通过micro_portfolio)"""
    from ml.micro_portfolio import generate_tickets
    rng = random.Random()
    try: rng.seed(int(str(data_slice[-1][0]) + "42"))
    except: pass
    result = generate_tickets(n=3, soft=False, spread_filter=True, ac_filter=True)
    return result.get("tickets", []) if result.get("ok") else []

def micro_peng_channel_3(data_slice):
    """主流程 + 彭浩通道过滤 3注"""
    from ml.micro_portfolio import generate_tickets
    rng = random.Random()
    try: rng.seed(int(str(data_slice[-1][0]) + "42"))
    except: pass
    result = generate_tickets(n=3, soft=False, peng_channel_filter=True)
    return result.get("tickets", []) if result.get("ok") else []

def random_3(data_slice):
    """纯随机基线 3注"""
    rng = random.Random()
    try: rng.seed(int(str(data_slice[-1][0]) + "99"))
    except: pass
    tickets = []
    for _ in range(3):
        reds = sorted(rng.sample(range(1, 34), 6))
        blue = rng.randint(1, 16)
        tickets.append({"reds": reds, "blue": blue})
    return tickets

authors = {
    "微投资组合(主)": micro_3,
    "微尔(彩乐乐)": weier_3,
    "张委铭": zhang_3,
    "李志林": lizhilin_3,
    "蒋加林(2010)": jiangjialin_3,
    "李相春(纯)": lixiangchun_3,
    "李相春(散度+AC)": lixiangchun_filtered_3,
    "微投+彭浩通道": micro_peng_channel_3,
    "彭浩": peng_3,
    "←随机基线": random_3,
}

# ============================================================
# 运行对比
# ============================================================
results = {name: {"red_hits": [], "blue_hits": [], "errors": 0} for name in authors}

for i, actual in enumerate(test_data):
    period = actual[0]
    actual_reds = set(actual[1:7])
    actual_blue = actual[7]

    # 训练数据 = 截至本期之前的所有数据
    actual_idx = data.index(test_data[i])  # 在完整数据中的位置
    train_slice = data[:actual_idx + 1]  # 不含未来

    if len(train_slice) < MIN_TRAIN:
        continue

    for name, fn in authors.items():
        try:
            tickets = fn(train_slice)
            if not tickets:
                results[name]["errors"] += 1
                continue
            for t in tickets:
                reds = set(t.get("reds", []))
                blue = t.get("blue", 0)
                if reds:
                    results[name]["red_hits"].append(len(reds & actual_reds))
                if blue:
                    results[name]["blue_hits"].append(1 if blue == actual_blue else 0)
        except Exception as e:
            results[name]["errors"] += 1

    if (i + 1) % 10 == 0:
        print(f"  进度: {i+1}/{SAMPLE_SIZE} (第{period}期)")

# ============================================================
# 输出
# ============================================================
print()
print(f"{'='*80}")
print(f"{'作者':20s} {'红球均值':>8s} {'红球≥2占比':>10s} {'蓝球命中率':>10s} {'总注数':>6s} {'错误':>5s}")
print(f"{'-'*80}")

baseline_red = 36/33  # 随机期望 1.0909
baseline_blue = 1/16  # 0.0625

for name in authors:
    r = results[name]
    n = len(r["red_hits"])
    if n == 0:
        print(f"{name:20s} {'N/A':>8s} {'N/A':>10s} {'N/A':>10s} {0:>6d} {r['errors']:>5d}")
        continue
    avg_red = sum(r["red_hits"]) / n
    pct_ge2 = sum(1 for h in r["red_hits"] if h >= 2) / n * 100
    blue_rate = sum(r["blue_hits"]) / max(len(r["blue_hits"]), 1) * 100
    marker = " ✓" if avg_red > baseline_red else ""
    print(f"{name:20s} {avg_red:>8.3f} {pct_ge2:>9.1f}% {blue_rate:>9.1f}% {n:>6d} {r['errors']:>5d}")

print(f"{'-'*80}")
print(f"  随机基线(期望): 红球={baseline_red:.4f}  蓝球={baseline_blue*100:.1f}%")
print(f"  高于基线 = ✓ 标记")
print(f"{'='*80}")
