# 开奖对比 — 权重优化方案 v4（终版）

## 方案演进

```
v1 (当前):  点估计 + 固定7:3融合           → 单期噪声大，新策略无冷启动
v2 (初稿):  Thompson Sampling + 滑动窗口   → TS 用于臂选择，不适用于权重估计
v3 (草案):  James-Stein + 精选12个运行     → 剪枝在分类场景有效，彩票选号不适用
v4 (终版):  James-Stein + 全量运行 + 族上限 → 保留独有号码覆盖 + 数学最优权重
```

## 为什么全量运行 + 不剪枝

彩票是加权投票取 top-K，不是多数决。每个策略贡献的是候选号码，
弱策略可能贡献独有正确号码（别人没选、只有它选了、且开出来了）。
剪掉弱策略 = 丢失独有号码 = 可能少中球。

```
分类问题（可剪枝）:              彩票选号（不可剪枝）:
3猫 vs 1狗 → 剪掉投狗的          策略A: {3,8,15,21,27,32}
→ 精度不变 ✓                    Chaos: {1,7,15,19,27,31}  ← 独有27号
→ 少噪音 ✓                      剪掉Chaos → 27号没人提名 → 少中1球 ✗
```

**结论：全量运行，用族上限防抱团，用收缩权重压噪声。**

---

## 核心算法：James-Stein 收缩估计

### 数学原理

多个均值同时估计时，独立MLE不是最优。James-Stein估计量在均方误差下一致优于MLE。

### 红球权重

```
输入: strategy_performance_log（每个策略的历史红球命中记录）

Step 1 — 滑动窗口折扣:
  discount = 0.97^age           // 每期衰减3%，等效窗口~33期
  n_i = Σ discount              // 有效测试次数
  obs_i = Σ(discount × hits) / n_i  // 加权平均命中数

Step 2 — 计算总均值:
  grand = Σ(n_i × obs_i) / Σ(n_i)

Step 3 — 估计方差:
  σ² = Σ(n_i × (obs_i - grand)²) / Σ(n_i)   // 组间方差
  τ² = 0.5                                    // 先验方差（彩票命中率自然波动范围）

Step 4 — 收缩:
  λ_i = τ² / (τ² + σ² / max(n_i, 1))
  shrunk_i = grand + (1 - λ_i) × (obs_i - grand)
  shrunk_i = clamp(0.5, shrunk_i, 2.5)

Step 5 — 转为权重:
  red_weight_i = shrunk_i / 1.09   // 1.09 = 随机期望（6/33 × 6 ≈ 1.09）
  red_weight_i = clamp(0.3, red_weight_i, 2.0)
```

### 蓝球权重

```
同理，但基线不同:
  obs_i = Σ(discount × blue_hits) / n_i  // 蓝球命中率 (0或1)
  grand_b = Σ(n_i × obs_i) / Σ(n_i)
  blue_weight_i = shrunk_i / 0.0625      // 0.0625 = 1/16 随机概率
  blue_weight_i = clamp(0.3, blue_weight_i, 2.0)
```

### 收缩效果示例

| 策略 | 红球n | 红球obs | λ收缩 | shrunk | 红球权重 |
|------|------|--------|------|--------|---------|
| 频率 | 50 | 1.45 | 0.12 | 1.42 | 1.30 |
| 遗漏 | 50 | 1.38 | 0.12 | 1.36 | 1.25 |
| Copula | 3 | 2.00 | 0.87 | 1.22 | 1.12 |
| 贝叶斯 | 1 | 5.00 | 0.98 | 1.14 | 1.05 |
| Pólya | 0 | N/A | 1.00 | 1.09 | 1.00 |

> Copula 3测2中 → 不收缩时权重=1.83（虚高），收缩后=1.12（合理）
> 贝叶斯 1测5中 → 不收缩时权重=4.59（荒谬），收缩后=1.05（保守）

### 冷启动先验

新策略（无实盘数据）用回测结果初始化：

```
n_init = min(backtest_tests, 20) × 0.5    // 回测打5折
obs_init = backtest_avg_red
// 这些作为 strategy_performance_log 的种子数据写入
```

---

## 策略族多样性上限

防同类策略抱团绑架投票：

```
策略分组:
  G1 频率族: 频率, 遗漏, 趋势, 温度, Pólya, 指数优化       (6个)
  G2 模式族: 均匀, 间隔, 黄金分割, 同尾, 相似期, 位置     (6个)
  G3 结构族: 共现, 马尔可夫蓝, 混沌                        (3个)
  G4 ML族:   AI集成(XGBoost+LSTM)                          (1个)
  G5 高级族: Copula, 贝叶斯, 熵值, EVT, RMT                (5个)

规则: 单族红球总权重 ≤ 红球总权重 × 30%
      单族蓝球总权重 ≤ 蓝球总权重 × 30%
      超限时族内等比缩放
```

---

## 红/蓝分离投票

共识机制改为红蓝独立权重：

```
computeConsensus(strategies):
  // 红球投票: 使用 red_weight
  for each strategy s:
    for each red number n in s.reds:
      rCount[n] += red_weight[s.name]

  // 蓝球投票: 使用 blue_weight
  for each strategy s:
    bCount[s.blue] += blue_weight[s.name]

  // 红球取 top-6, 蓝球取 top-1
  consReds = top6(rCount)
  consBlue = top1(bCount)
```

---

## 权重重算触发

- 每次 `/api/compare` 后，写入 `strategy_performance_log`
- 累积 ≥5 期新数据后，自动触发 `/api/strategy-weights/recalculate`
- 也提供手动触发按钮（回测面板）

---

## 实施清单

| 文件 | 内容 | 行数 |
|------|------|------|
| `server/db.py` | +strategy_performance_log 表 + CRUD | ~25 |
| `server/weight_optimizer.py` | James-Stein + 族上限 + 滑动窗口 | ~100 |
| `server/handler.py` | /api/compare 后写 performance_log + 调 optimizer | ~10 |
| `static/js/consensus.js` | 红蓝分离权重投票 | ~15 |
| `static/js/store.js` | redWeight/blueWeight 分离 + 策略族定义 | ~20 |
| `static/js/ui/compare.js` | 显示红蓝分离表现 | ~10 |

**总改动 ~180行，6个文件。**

---

## 参考

- James-Stein: Efron & Morris (1977), "Stein's Paradox in Statistics"
- Empirical Bayes: Casella (1985), "An Introduction to Empirical Bayes Data Analysis"
- Ensemble Pruning: FusionShot (2024), arXiv:2404.04434
