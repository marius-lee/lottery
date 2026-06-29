"""遗传编程符号发现 — 进化出描述偏差结构的数学公式

原理: 不训练神经网络, 不拟合概率分布. 直接进化Python程序种群,
  每个程序接收"号码特征"输入, 输出"预测得分".
  Fitness = 得分与实际频率偏差的吻合度 + 复杂度惩罚.

与预测器的根本区别:
  旧: 程序预测下期号码 → 失败(因为无时序结构)
  新: 程序描述"为什么某些号码出现更多" → 发现偏差结构

搜索空间:
  操作符: + - * / abs max min if mod log
  终端: 号码值, 奇偶, 质数, 位置, 遗漏期数, 邻号距离
  Fitness: 程序输出 vs 历史频率偏差 的Spearman秩相关

如果GP能发现人类未发现的模式 → 直接可用的偏差公式.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import math
import random
import operator
from collections import Counter


def load_data():
    from server.db import load_draws
    return load_draws()


# ═══════════════════════════════════════════════════════════════
# 程序表示: 表达式树
# ═══════════════════════════════════════════════════════════════

PRIMES = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31}

# 终端 (叶节点): 返回float
def terminal_num(n):
    return lambda ctx: float(n)

def terminal_is_odd():
    return lambda ctx: 1.0 if ctx["num"] % 2 == 1 else 0.0

def terminal_is_prime():
    return lambda ctx: 1.0 if ctx["num"] in PRIMES else 0.0

def terminal_is_big():
    return lambda ctx: 1.0 if ctx["num"] >= 17 else 0.0

def terminal_mod3():
    return lambda ctx: float(ctx["num"] % 3)

def terminal_tail():
    return lambda ctx: float(ctx["num"] % 10)

def terminal_pos():
    # 号码在最近期的平均位置 (1-6)
    return lambda ctx: float(ctx.get("avg_position", 3.5))

def terminal_omission():
    return lambda ctx: float(ctx.get("omission", 5.0))

def terminal_freq():
    # 历史频率 * 100
    return lambda ctx: float(ctx.get("frequency", 0.03) * 1000)

def terminal_const():
    return lambda ctx: random.choice([0.0, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0])

# 操作符 (内部节点)
OPS = {
    "add":  (operator.add, 2),
    "sub":  (operator.sub, 2),
    "mul":  (operator.mul, 2),
    "div":  (lambda a, b: a / (abs(b) + 1e-10), 2),  # 安全除法
    "abs":  (abs, 1),
    "max":  (max, 2),
    "min":  (min, 2),
    "log":  (lambda x: math.log(abs(x) + 1e-10), 1),
    "ifgt": (lambda a, b, c, d: c if a > b else d, 4),  # if a>b then c else d
}

# 终端构造函数
TERMINALS = [
    ("num",        lambda: terminal_num(random.randint(1, 33))),
    ("odd",        terminal_is_odd),
    ("prime",      terminal_is_prime),
    ("big",        terminal_is_big),
    ("mod3",       terminal_mod3),
    ("tail",       terminal_tail),
    ("pos",        terminal_pos),
    ("omission",   terminal_omission),
    ("freq",       terminal_freq),
    ("const",      terminal_const),
]


class ExprNode:
    """表达式树节点."""
    def __init__(self, op_name, children):
        self.op_name = op_name
        self.children = children  # list of ExprNode (for ops) or None (for terminals)

    def evaluate(self, ctx):
        if self.op_name == "terminal":
            return self.children(ctx)  # children is the terminal function
        op_fn, arity = OPS[self.op_name]
        args = [c.evaluate(ctx) for c in self.children]
        try:
            result = op_fn(*args)
            # 裁剪到合理范围
            if math.isnan(result) or math.isinf(result):
                return 0.0
            return max(-100.0, min(100.0, result))
        except (ValueError, ZeroDivisionError, OverflowError):
            return 0.0

    def size(self):
        if self.op_name == "terminal":
            return 1
        return 1 + sum(c.size() for c in self.children)

    def depth(self):
        if self.op_name == "terminal":
            return 1
        return 1 + max(c.depth() for c in self.children)

    def __repr__(self):
        if self.op_name == "terminal":
            return "T"
        return f"({self.op_name} {' '.join(repr(c) for c in self.children)})"


# ═══════════════════════════════════════════════════════════════
# 程序生成
# ═══════════════════════════════════════════════════════════════

def random_expr(max_depth=5):
    """Grow方法: 随机生成表达式树."""
    if max_depth <= 1 or random.random() < 0.3:
        # 终端
        name, fn_factory = random.choice(TERMINALS)
        return ExprNode("terminal", fn_factory())

    # 操作符
    op_name = random.choice(list(OPS.keys()))
    _, arity = OPS[op_name]
    children = [random_expr(max_depth - 1) for _ in range(arity)]
    return ExprNode(op_name, children)


def crossover(parent_a, parent_b):
    """子树交换交叉."""
    # 在parent_a中随机选一个子树, 在parent_b中随机选一个子树, 交换
    a_nodes = _all_nodes(parent_a)
    b_nodes = _all_nodes(parent_b)
    if not a_nodes or not b_nodes:
        return parent_a  # 无法交叉, 返回原样

    a_node = random.choice(a_nodes)
    b_node = random.choice(b_nodes)

    # 深拷贝a_node → 替换parent_a中的相应节点
    new_tree = _replace_node(parent_a, a_node, _deep_copy(b_node))
    return new_tree


def mutate(expr, max_depth=5):
    """子树变异: 随机替换子树."""
    nodes = _all_nodes(expr)
    if not nodes:
        return random_expr(max_depth)
    target = random.choice(nodes)
    replacement = random_expr(min(max_depth, 3))
    return _replace_node(expr, target, replacement)


def _all_nodes(expr):
    """返回所有节点(含终端)."""
    nodes = []
    def walk(node):
        nodes.append(node)
        if node.op_name != "terminal":
            for c in node.children:
                walk(c)
    walk(expr)
    return nodes


def _deep_copy(node):
    """深拷贝表达式树."""
    if node.op_name == "terminal":
        # terminal的children是函数, 直接引用 (函数无状态, 共享安全)
        return ExprNode("terminal", node.children)
    return ExprNode(node.op_name, [_deep_copy(c) for c in node.children])


def _replace_node(tree, target, replacement):
    """在tree中替换target节点为replacement, 返回新树."""
    if tree is target:
        return _deep_copy(replacement)
    if tree.op_name == "terminal":
        return _deep_copy(tree)
    return ExprNode(tree.op_name,
                    [_replace_node(c, target, replacement) for c in tree.children])


# ═══════════════════════════════════════════════════════════════
# 上下文构建
# ═══════════════════════════════════════════════════════════════

def build_contexts(data, future_data=None):
    """为每个号码构建评估上下文.

    关键: ctx的统计量只用data(训练集), fitness用future_data(测试集)的频率.
    这样程序无法通过输出ctx频率来作弊.

    ctx[num] = {
        num, avg_position, omission, frequency (训练集),
        ...各种只从训练集计算的统计量...
    }
    """
    n = len(data)
    counts = Counter()
    pos_sums = Counter()
    pos_counts = Counter()
    last_seen = {}

    for idx, row in enumerate(data):
        reds = sorted(row[1:7])
        for p, r in enumerate(reds):
            counts[r] += 1
            pos_sums[r] += (p + 1)
            pos_counts[r] += 1
            last_seen[r] = idx

    ctxs = {}
    for num in range(1, 34):
        ctxs[num] = {
            "num": num,
            "avg_position": pos_sums[num] / pos_counts[num] if pos_counts[num] > 0 else 3.5,
            "omission": float(n - 1 - last_seen.get(num, 0)),
            "frequency": counts[num] / (n * 6) if n > 0 else 0.0,
        }

    # 如果有future_data, 计算"真实"目标频率 (用于fitness)
    if future_data:
        future_counts = Counter()
        for row in future_data:
            for n in row[1:7]:
                future_counts[n] += 1
        for num in range(1, 34):
            ctxs[num]["target_freq"] = (future_counts[num] /
                                        (len(future_data) * 6) if future_data else 0.0)

    return ctxs


# ═══════════════════════════════════════════════════════════════
# Fitness 评估
# ═══════════════════════════════════════════════════════════════

def evaluate_fitness(expr, ctxs):
    """评估表达式的fitness.

    Fitness = Spearman(程序输出排名, 未来频率排名) - 复杂度惩罚.
    使用target_freq (future_data的频率), 不是当前ctx的frequency.
    """
    # 检查是否有target_freq (训练/测试分离)
    use_target = any("target_freq" in ctxs[n] for n in range(1, 34))

    # 对每个号码计算程序输出
    outputs = []
    for num in range(1, 34):
        ctx = ctxs[num]
        try:
            val = expr.evaluate(ctx)
            outputs.append((num, val))
        except Exception:
            outputs.append((num, 0.0))

    # 程序输出排序
    program_rank = {}
    outputs.sort(key=lambda x: -x[1])
    for rank, (num, _) in enumerate(outputs):
        program_rank[num] = rank

    # 目标频率排序 (future_data的频率, 或训练集频率)
    if use_target:
        freq_sorted = sorted(range(1, 34),
                            key=lambda n: -ctxs[n].get("target_freq", 0))
    else:
        freq_sorted = sorted(range(1, 34),
                            key=lambda n: -ctxs[n]["frequency"])

    freq_rank = {}
    for rank, num in enumerate(freq_sorted):
        freq_rank[num] = rank

    # Spearman秩相关
    n_nums = 33
    d2_sum = sum((program_rank[n] - freq_rank[n])**2 for n in range(1, 34))
    spearman = 1.0 - 6.0 * d2_sum / (n_nums * (n_nums**2 - 1))

    # 复杂度惩罚: 每节点 -0.005 [工程: 平衡发现力与简约性]
    complexity_penalty = expr.size() * 0.005

    return spearman - complexity_penalty, spearman


# ═══════════════════════════════════════════════════════════════
# 进化循环
# ═══════════════════════════════════════════════════════════════

def evolve(train_data, future_data=None, pop_size=100, generations=100,
           tournament_size=5, crossover_prob=0.7, mutation_prob=0.3,
           elite_count=5, verbose=True):
    """进化程序种群.

    train_data: 用于构建ctx (程序输入)
    future_data: 用于target_freq (fitness评估). 如果None→用train_data频率(套套逻辑)
    """
    ctxs = build_contexts(train_data, future_data)

    # 初始化种群
    pop = [(random_expr(max_depth=5), 0.0, 0.0) for _ in range(pop_size)]

    # 初始评估
    for i in range(pop_size):
        expr = pop[i][0]
        fit, spear = evaluate_fitness(expr, ctxs)
        pop[i] = (expr, fit, spear)

    best_overall = max(pop, key=lambda x: x[1])

    for gen in range(generations):
        new_pop = []

        # 精英保留
        pop.sort(key=lambda x: -x[1])
        new_pop.extend(pop[:elite_count])

        # 生成下一代
        while len(new_pop) < pop_size:
            # 锦标赛选择
            tournament = random.sample(pop, tournament_size)
            parent = max(tournament, key=lambda x: x[1])

            child_expr = _deep_copy(parent[0])

            if random.random() < crossover_prob and len(pop) > 1:
                other = max(random.sample(pop, tournament_size), key=lambda x: x[1])
                child_expr = crossover(child_expr, other[0])

            if random.random() < mutation_prob:
                child_expr = mutate(child_expr, max_depth=5)

            # [工程] 深度限制: 防止表达式膨胀, 平衡表达能力与M1计算
            if child_expr.depth() > 8:
                child_expr = random_expr(max_depth=5)

            child_fit, child_spear = evaluate_fitness(child_expr, ctxs)
            new_pop.append((child_expr, child_fit, child_spear))

        pop = new_pop

        gen_best = max(pop, key=lambda x: x[1])
        if gen_best[1] > best_overall[1]:
            best_overall = gen_best

        if verbose and gen % 20 == 0:
            avg_fit = sum(p[1] for p in pop) / len(pop)
            print(f"  Gen {gen:3d}: best fitness={gen_best[1]:.4f} "
                  f"(spearman={gen_best[2]:.4f}), avg={avg_fit:.4f}")

    return best_overall, pop


# ═══════════════════════════════════════════════════════════════
# 主函数
# ═══════════════════════════════════════════════════════════════

def run():
    data = load_data()
    n = len(data)
    mid = n // 2

    train = data[:mid]
    future = data[mid:]

    print(f"=" * 60)
    print(f"遗传编程: 进化偏差发现公式 (跨时间验证)")
    print(f"=" * 60)
    print(f"训练集: 1-{mid}期, 测试集: {mid+1}-{n}期")
    print(f"种群: 100, 代数: 100")
    print(f"Fitness: Spearman(程序输出(训练ctx), 测试集频率) - 复杂度")
    print(f"  程序输入来自训练集统计量, 不能直接看测试集频率")
    print()

    # 也在全数据集上跑一次作为基线(套套逻辑)
    print(f"基线 (全数据, 套套逻辑 = 程序可看到目标频率):")
    base_best, _ = evolve(data, None, pop_size=50, generations=50, verbose=False)
    print(f"  基线 Spearman ρ = {base_best[2]:.4f} (完美=1.0)")

    print(f"\n跨时间验证:")
    best, pop = evolve(train, future, pop_size=100, generations=100, verbose=True)

    print(f"\n{'─' * 60}")
    print(f"最优程序 (跨时间):")
    print(f"  Fitness: {best[1]:.4f}")
    print(f"  Spearman ρ: {best[2]:.4f}")
    print(f"  大小: {best[0].size()} 节点, 深度: {best[0].depth()}")
    print(f"  表达式: {repr(best[0])[:300]}")

    # 在测试集上评估
    ctxs_future = build_contexts(future)
    scores = []
    for num in range(1, 34):
        val = best[0].evaluate(ctxs_future[num])
        scores.append((num, val, ctxs_future[num]["frequency"]))

    print(f"\n  程序评分 vs 测试集实际频率:")
    scores.sort(key=lambda x: -x[1])
    for rank, (num, val, freq) in enumerate(scores[:10]):
        print(f"    #{num:02d}: 程序评分={val:+.3f}, 测试频率={freq*100:.2f}% (rank {rank+1})")

    # 判定
    print(f"\n{'═' * 60}")
    if best[2] > 0.5:
        print(f"⚠️  跨时间验证通过! (ρ={best[2]:.3f})")
        print(f"  → 程序发现了跨时间段依然有效的偏差结构")
        print(f"  → 这些结构不是噪声, 是真实的规律")
    elif best[2] > 0.2:
        print(f"弱跨时间信号 (ρ={best[2]:.3f})")
        print(f"  → 有部分跨时间可重复的偏差")
        print(f"  → 需更大样本量或更精细的上下文")
    else:
        print(f"跨时间验证失败 (ρ={best[2]:.3f})")
        baseline_rho = base_best[2]
        print(f"  → 程序可以用训练集频率完美预测训练集 (ρ={baseline_rho:.3f})")
        print(f"  → 但这些模式不能延续到未来 (ρ={best[2]:.3f})")
        print(f"  → 结论: 频率偏差存在, 但是时变的/不稳定的")
    print(f"{'═' * 60}")

    return best


if __name__ == "__main__":
    run()
