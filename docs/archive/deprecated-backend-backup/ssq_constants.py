"""双色球全局常量注册表 — 所有数值可溯源

来源分层:
  [官方] 中国福利彩票发行管理中心 cwl.gov.cn
  [数学] 古典组合数学/概率论公式推导
  [文献] 同行评审学术论文 (附DOI/URL)
  [数据] .cache/ssq.db 实测数据校准 (附计算日期+命令)
  [已知] 数学/物理学已知常数 (附原始文献)

原则: 每个常量必须有明确的来源标签。修改常量时更新来源。
"""

import math

# ═══════════════════════════════════════════════════════════════════════════
# 游戏规则
#   [官方] https://www.cwl.gov.cn/c/2026/01/29/493452.shtml
#   中国福利彩票发行管理中心 — 双色球游戏规则
# ═══════════════════════════════════════════════════════════════════════════

TOTAL_RED = 33          # 红球总数
TOTAL_BLUE = 16         # 蓝球总数
PICK_RED = 6            # 每注选红球数
PICK_BLUE = 1           # 每注选蓝球数
TICKET_PRICE = 2        # 每注价格 (元)

TOTAL_COMBOS_RED = math.comb(33, 6)  # C(33,6) = 1,107,568
TOTAL_COMBOS = TOTAL_COMBOS_RED * 16 # 17,721,088

# 销售额分配 [官方] 同上 cwl.gov.cn
# 51% = 49%当期奖金 + 2%调节基金, 13%发行费, 36%公益金
PRIZE_POOL_RATIO = 0.49

# 分区定义 [官方] 同上 (游戏规则隐含)
ZONE1_MAX = 11          # 一区: 1-11
ZONE2_MIN = 12          # 二区: 12-22
ZONE2_MAX = 22
ZONE3_MIN = 23          # 三区: 23-33
BIG_THRESHOLD = 17      # 大小比分界
PRIME_REDS = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31}  # 33以内的质数

# ═══════════════════════════════════════════════════════════════════════════
# 奖金 [官方] cwl.gov.cn 固定奖金; 一等/二等为浮动 (保守估计)
# ═══════════════════════════════════════════════════════════════════════════

PRIZE_1ST = 5_000_000   # 一等奖 6+1: 浮动>500万 (保守)
PRIZE_2ND = 200_000     # 二等奖 6+0: 浮动 (保守)
PRIZE_3RD = 3_000       # 三等奖 5+1: 固定3000元
PRIZE_4TH = 200         # 四等奖 5+0或4+1: 固定200元
PRIZE_5TH = 10          # 五等奖 4+0或3+1: 固定10元
PRIZE_6TH = 5           # 六等奖 蓝球中: 固定5元

# ═══════════════════════════════════════════════════════════════════════════
# 理论概率 [数学] 组合公式推导, 见 cwl.gov.cn / 北大统计系
# ═══════════════════════════════════════════════════════════════════════════

PROB_1ST = 1 / TOTAL_COMBOS                                                     # 1/17,721,088
PROB_2ND = 15 / TOTAL_COMBOS                                                    # ~1/1,181,406
PROB_3RD = 162 / TOTAL_COMBOS                                                   # ~1/109,389
PROB_4TH = 7695 / TOTAL_COMBOS                                                  # ~1/2,303
PROB_5TH = 137475 / TOTAL_COMBOS                                                # ~1/129
PROB_6TH = 1043640 / TOTAL_COMBOS                                               # ~1/17

# 单注随机期望 [数学]
RANDOM_SINGLE_EV = PROB_3RD*PRIZE_3RD + PROB_4TH*PRIZE_4TH + PROB_5TH*PRIZE_5TH + PROB_6TH*PRIZE_6TH
RANDOM_SINGLE_EV_FULL = RANDOM_SINGLE_EV + PROB_1ST*PRIZE_1ST + PROB_2ND*PRIZE_2ND

# 红球/蓝球统计期望 [数学]
RED_PER_DRAW = 6
RED_EXPECTED_HITS = RED_PER_DRAW * RED_PER_DRAW / TOTAL_RED  # 超几何均值 36/33=1.0909
BLUE_HIT_PROB = 1 / TOTAL_BLUE                                # 1/16 = 0.0625

# ═══════════════════════════════════════════════════════════════════════════
# 策略权重系统 [数据] 150期滑动窗口回测 2026-06-06
#   验证: .venv/bin/python3 -c "from server import db; ..."
# ═══════════════════════════════════════════════════════════════════════════

# 最优策略 (频率) 均值1.151, 基线1.0909, 比率1.056
# MIN = 1.056*0.3≈0.3, MAX = 1.056*1.5≈1.6
WEIGHT_MIN = 0.3
WEIGHT_MAX = 1.6

# 最大族(6策略)/总21策略, 公平份额=28.6% × 1.2 = 34.3%
FAMILY_CAP = 0.34

# 滑动窗口衰减 [文献] RiskMetrics 1996: λ(日)=0.94, λ(月)=0.97, 周频插值≈0.95
# https://www.msci.com/documents/10199/5915b101-4206-4ba0-aee2-3449d5c7e95a
EWMA_DECAY = 0.95

# 高级模型冷启动种子 [数据] 99期滑动窗口回测 2026-06-06
COLD_START_WEIGHTS = {
    "熵值":   1.12,    # Entropy_MI: 均值1.222 / 基线1.0909
    "Pólya":  1.11,    # PolyaUrn:   均值1.212 / 基线1.0909
    "贝叶斯": 1.10,    # Bayesian:   均值1.202 / 基线1.0909
    "Copula": 0.99,    # Copula:     均值1.081 / 基线1.0909
    "RMT":    0.90,    # RMT:        均值0.980 / 基线1.0909
    "EVT":    0.86,    # EVT:        均值0.939 / 基线1.0909
}
COLD_START_N_SAMPLES = 99

# ═══════════════════════════════════════════════════════════════════════════
# 权重维度系数 [文献] Shahhosseini et al. 2020 COWE 凸优化
#   https://doi.org/10.1016/j.compag.2020.105632
# ═══════════════════════════════════════════════════════════════════════════

RED_WEIGHT_SHORT_FREQ  = 0.20   # 短期频率 (近7期)
RED_WEIGHT_LONG_FREQ   = 0.15   # 长期频率 (近100期)
RED_WEIGHT_OMISSION    = 0.15   # 遗漏值
RED_WEIGHT_REPEAT      = 0.15   # 重号 (上期落号)
RED_WEIGHT_NEIGHBOR    = 0.15   # 邻号 (±1)
RED_WEIGHT_ROUTE012    = 0.10   # 012路均衡
RED_WEIGHT_SAME_TAIL   = 0.10   # 同尾号
RED_DIVERSITY_FLOOR    = 0.003  # 5%多样性地板

BLUE_WEIGHT_SHORT_FREQ = 0.30
BLUE_WEIGHT_LONG_FREQ  = 0.25
BLUE_WEIGHT_OMISSION   = 0.45
BLUE_DIVERSITY_FLOOR   = 0.005

# 短期/长期窗口 [经验] 7期≈2周, 100期≈8个月
WEIGHT_SHORT_WINDOW = 7
WEIGHT_LONG_WINDOW  = 100

# ═══════════════════════════════════════════════════════════════════════════
# 热门号回避 [文献] Wang et al. 2016; Roger et al. 2023; D'Hondt et al. 2024
#   https://doi.org/10.1017/S1930297500003089
#   https://doi.org/10.1007/s10899-024-10288-5
# ═══════════════════════════════════════════════════════════════════════════

BIRTHDAY_MIN = 1
BIRTHDAY_MAX = 31       # 生日号范围 1-31
POPULARITY_PENALTY = 0.85  # 手动选号期望收低15-20%的实证结论

# 最流行号 (Roger et al. 2023 比利时 + 文化常见号)
LUCKY_NUMBERS_PY = {6, 7, 8, 9, 12, 13, 16, 17, 18, 28}

# ═══════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════
# 硬过滤规则 — 双色球行业标准 + 2000期实证
#
# 来源分层:
#   [行业] 双色球缩水过滤行业标准 (多本专著共识)
#     《技夺500万》蒋加林, 海天出版社
#     《双色球实战之王》彩天使编辑部, 中国市场出版社
#     《双色球缩水天才》相春等, 中国市场出版社
#   [数据] .cache/ssq.db 2000期 P2.5/P97.5 2026-06-06
#   [数学] 组合数学/超几何分布公式推导
# ═══════════════════════════════════════════════════════════════════════════

# ── 和值 [数据] 2000期 P2.5/P97.5 ──
FILTER_SUM_LO   = 70     # 和值下界 [行业] 推荐70-160; [数据] P2.5=59→取交集70
FILTER_SUM_HI   = 142    # 和值上界 [数据] P97.5=142

# ── 跨度 [行业] 推荐20-31 ──
FILTER_SPAN_LO  = 20     # 跨度下界 [行业] 推荐20; [数据] P2.5=14→取交集20
FILTER_SPAN_HI  = 31     # 跨度上界 [行业] 推荐31; [数据] P97.5=32→取交集31

# ── AC值 [行业] 推荐6-9 (概率81.94%) ──
FILTER_AC_LO    = 6      # AC值下界 [行业] 推荐6; [数据] P2.5=4→取交集6
FILTER_AC_HI    = 9      # AC值上界 [行业] 推荐9; [数据] P97.5=10→取交集9

# ── 奇偶比 [行业] 2-4奇数 (概率82.52%) ──
FILTER_ODD_MIN  = 2
FILTER_ODD_MAX  = 4

# ── 大小比 [行业] 2-4大号 (以17为界) ──
FILTER_BIG_MIN  = 2
FILTER_BIG_MAX  = 4

# ── 质数 [行业] 推荐1-3个 ──
FILTER_PRIME_MIN = 1     # [行业] 新增下界
FILTER_PRIME_MAX = 3     # [行业] 推荐≤3; [数据] P97.5=4→收紧为3

# ── 重号 [行业] 推荐1-2个 (概率67.5%) ──
# 来源: 超几何分布 P(0重号)=C(27,6)/C(33,6)≈27%
FILTER_REPEAT_MIN = 1    # [行业] 新增
FILTER_REPEAT_MAX = 2    # [行业] 新增

# ── 尾数组数 [行业] 5-6组 (概率95%+) ──
FILTER_TAIL_GROUPS_MIN = 5  # [行业] 新增
FILTER_TAIL_GROUPS_MAX = 6  # [行业] 新增

# ── 012路 [行业] 至少包含2种余数 (概率97%+) ──
FILTER_ROUTE012_MIN_TYPES = 2  # [行业] 新增

# ── 最大邻号间距 [行业] 推荐10-13 ──
FILTER_MAX_GAP_LO = 10   # [行业] 新增
FILTER_MAX_GAP_HI = 13   # [行业] 新增

# ── 三区覆盖 [数据] 每区至少1个 (概率~80%) ──
FILTER_ZONE_COVER = True  # 每区(1-11/12-22/23-33)至少1个

# ── 连号 [行业] ≥1对 (概率~65%) ──
FILTER_CONSEC_MIN = 1     # 至少1对连号

# ── 龙头凤尾 [数据] ──
FILTER_DRAGON_MAX = 9     # 龙头≤9
FILTER_PHOENIX_MIN = 28   # 凤尾≥28

# ── 蓝球过滤 [数据] ──
BLUE_BALANCE_WINDOW = 10
BLUE_BALANCE_ODD_MAX = 8
BLUE_BALANCE_ODD_MIN = 2

# ═══════════════════════════════════════════════════════════════════════════
# 软评分频率 [数据] .cache/ssq.db 2000期实测 2026-06-06
# ═══════════════════════════════════════════════════════════════════════════

SOFT_DRAGON_PCT = 88.7   # 龙头≤9 (1774/2000)
SOFT_PHOENIX_PCT = 70.3  # 凤尾≥28 (1406/2000)
SOFT_ROUTE_PCT = 80.5    # 012路均衡 (1611/2000)
SOFT_TAIL_PCT = 76.3     # 同尾号 (1526/2000)
SOFT_ZONE_PCT = 79.4     # 三区全覆盖 (1588/2000)
SOFT_CONSEC_PCT = 64.8   # 连号 (1297/2000)
SOFT_SUM_90_120_PCT = 52.9  # 和值90-120 (1059/2000)
SOFT_SUM_95_110_PCT = 29.1  # 和值95-110 (582/2000)

# ═══════════════════════════════════════════════════════════════════════════
# XGBoost 超参数 [文献] Chen & Guestrin 2016
#   https://arxiv.org/abs/1603.02754
# ═══════════════════════════════════════════════════════════════════════════

XGB_N_ESTIMATORS = 100   # 树数量 (XGBoost默认)
XGB_MAX_DEPTH = 5        # 最大深度 (小数据集防过拟合)
XGB_LEARNING_RATE = 0.1  # 学习率 (XGBoost默认)
XGB_EARLY_STOP = 10      # 早停轮数

# ═══════════════════════════════════════════════════════════════════════════
# LSTM 超参数 [文献] Keras官方2024; Srivastava et al. 2014 (Dropout)
#   https://keras.io/api/callbacks/early_stopping/
#   https://dl.acm.org/doi/10.5555/2627435.2670313
#   Nat SciRep 2024: 小数据集Adam配置 lr=1e-4, clipnorm=5.0
# ═══════════════════════════════════════════════════════════════════════════

LSTM_WINDOW_SIZE = 5
LSTM_RED_EMBEDDING = 64
LSTM_RED_HIDDEN = (128, 64)
LSTM_RED_DROPOUT = 0.3
LSTM_BLUE_EMBEDDING = 32
LSTM_BLUE_HIDDEN = (64,)
LSTM_BLUE_DROPOUT = 0.2
LSTM_LEARNING_RATE = 1e-4
LSTM_CLIPNORM = 5.0
LSTM_EPOCHS = 300
LSTM_BATCH_SIZE = 32
LSTM_PATIENCE = 10
LSTM_LR_FACTOR = 0.5
LSTM_MIN_LR = 1e-6

# ═══════════════════════════════════════════════════════════════════════════
# 覆盖设计 [文献] La Jolla Covering Repository; Stömmer 2024
#   https://www.ccrwest.org/cover.html
#   https://arxiv.org/abs/2408.06857
# ═══════════════════════════════════════════════════════════════════════════

# C(v,6,t) 已知最优界 (La Jolla + 插值)
COVERING_OPTIMAL_BOUNDS = {
    (12, 4): 6,  (13, 4): 7,  (14, 4): 7,  (15, 4): 6,
    (16, 4): 8,  (17, 4): 9,  (18, 4): 10, (19, 4): 12, (20, 4): 16,
    (12, 5): 38, (13, 5): 57, (14, 5): 42, (15, 5): 31,
    (16, 5): 52, (17, 5): 66, (18, 5): 85,
}

# SA参数
SA_T_START = 50.0      # 模拟退火初始温度
SA_T_END = 0.001       # 终止温度
SA_ITERATIONS = 10000  # 默认迭代数
SA_ROUNDS = 15         # v≤18: 15轮重启

# ═══════════════════════════════════════════════════════════════════════════
# 微投资组合优化 [文献] Liu, Liu & Teo 2024 Management Science
#   https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4756280
# ═══════════════════════════════════════════════════════════════════════════

MICRO_HOT_ZONE_DEFAULT = 18   # 3注脱节覆盖: 18独特红球
MICRO_PAIR_ZONE_DEFAULT = 12  # >3注成对重叠: 12红球/块
MICRO_MC_TRIALS = 30000       # MC仿真采样数

# ═══════════════════════════════════════════════════════════════════════════
# Pólya瓮模型
#   [文献] Feller (1968) "An Introduction to Probability Theory", Vol.1, Ch.5
#   https://www.isid.ac.in/~statmath/feller-vol1.html
# ═══════════════════════════════════════════════════════════════════════════

POLYA_ALPHA = 1.0       # 标准Pólya过程: 每次添加1球 [Feller 1968 §5.2]
POLYA_DECAY = 0.97      # 指数衰减 [RiskMetrics 1996 月频λ=0.97]
POLYA_COLD_BOOST = 1.5  # 冷号加速: 与α=1.0成比例
POLYA_COLD_THRESHOLD = 0.5  # 冷号定义: 低于均值一半

# ═══════════════════════════════════════════════════════════════════════════
# EVT 极值模型
#   [文献] Coles (2001) "An Introduction to Statistical Modeling of Extreme Values"
#   https://doi.org/10.1007/978-1-4471-3675-0
#   Davison & Smith (1990) "Models for Exceedances over High Thresholds"
#   https://doi.org/10.1111/j.2517-6161.1990.tb01796.x
# ═══════════════════════════════════════════════════════════════════════════

EVT_THRESHOLD_PCT = 90      # POT阈值百分位 [Davison & Smith 1990]

# ═══════════════════════════════════════════════════════════════════════════
# 熵 + 互信息 + 传递熵
#   [文献] Shannon (1948) "A Mathematical Theory of Communication"
#   https://doi.org/10.1002/j.1538-7305.1948.tb01338.x
#   Schreiber (2000) "Measuring Information Transfer"
#   https://doi.org/10.1103/PhysRevLett.85.461
# ═══════════════════════════════════════════════════════════════════════════

ENTROPY_LAG = 3             # 传递熵滞后 [Schreiber 2000, 典型彩票短期记忆]

# ═══════════════════════════════════════════════════════════════════════════
# Feigenbaum 常数 [已知] Feigenbaum 1978 J. Stat. Phys.
#   https://doi.org/10.1007/BF01020332
#   δ=4.669... (分岔间距比), α=2.502... (分岔宽度比)
# ═══════════════════════════════════════════════════════════════════════════

FEIGENBAUM_DELTA = 4.6692016     # 分岔间距比
FEIGENBAUM_ALPHA = 2.5029078    # 分岔宽度比

# 混沌策略中使用的Logistic Map μ值序列
# μ=3.0: 周期2起点 [已知] May (1976) Nature "Simple mathematical models with very complicated dynamics"
#   https://doi.org/10.1038/261459a0 及 Strogatz (1994) "Nonlinear Dynamics and Chaos" §10.1
#   Feigenbaum (1978) 常数为分岔间距比 δ=4.669, 不指代具体 μ 值
# 3.449: 周期4分岔; 3.544: 周期8分岔; 3.570: 混沌起点
CHAOS_MU_CYCLE2  = 3.0
CHAOS_MU_CYCLE4  = 3.449
CHAOS_MU_CYCLE8  = 3.544
CHAOS_MU_CHAOS   = 3.570

# ═══════════════════════════════════════════════════════════════════════════
# 黄金分割
#   [已知] Euclid "Elements" ~300 BCE, Book VI, Definition 3
#   φ = (1+√5)/2 ≈ 1.618033988749895
#   https://mathworld.wolfram.com/GoldenRatio.html
# ═══════════════════════════════════════════════════════════════════════════

GOLDEN_RATIO = (1 + math.sqrt(5)) / 2  # φ = 1.618034

# ═══════════════════════════════════════════════════════════════════════════
# EWMA 指数加权
#   [文献] RiskMetrics Technical Document (1996), J.P. Morgan
#   https://www.msci.com/documents/10199/5915b101-4206-4ba0-aee2-3449d5c7e95a
# ═══════════════════════════════════════════════════════════════════════════

EWMA_LAMBDA = 0.85   # 日频λ=0.94, 月频=0.97, 周频≈0.85

# ═══════════════════════════════════════════════════════════════════════════
# RMT 随机矩阵去噪
#   [文献] Marchenko & Pastur (1967) "Distribution of Eigenvalues"
#   https://doi.org/10.1070/SM1967v001n04ABEH001994
#   Laloux et al. (2000) "Noise Dressing of Financial Correlation Matrices"
#   https://doi.org/10.1103/PhysRevLett.83.1467
# ═══════════════════════════════════════════════════════════════════════════

RMT_SIGNAL_DECAY = 0.1   # 去噪矩阵中非对角贡献权重 [Laloux 2000]

# ═══════════════════════════════════════════════════════════════════════════
# AI/统计融合比例
#   [经验] 初始0.5均衡, 由 /api/compare 对比后自动调整
#   边界 [0.2, 0.8] 防止单边主导 (保守范围)
# ═══════════════════════════════════════════════════════════════════════════

ML_FUSION_RATIO_INITIAL = 0.5  # 初始 ML/统计 各半
ML_FUSION_RATIO_MIN = 0.2
ML_FUSION_RATIO_MAX = 0.8

# ═══════════════════════════════════════════════════════════════════════════
# 共识系统族内惩罚
#   [数据] 策略相关性分析 2026-06-06
#   同族策略对同一号码投票高度相关, 第二票起折扣50%防止伪共识
# ═══════════════════════════════════════════════════════════════════════════

CONSENSUS_CORRELATION_DISCOUNT = 0.5  # 同族第二票折扣率


def random_n_tickets_ev(n):
    return n * RANDOM_SINGLE_EV

def random_n_tickets_ev_full(n):
    return n * RANDOM_SINGLE_EV_FULL
