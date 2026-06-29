# 路径C: 方法聚合 + 覆盖设计 — 设计方案

日期: 2026-06-24 | 状态: 已确认 | 北极星: 中一等奖

---

## 1. 问题

当前系统本质是"过滤+随机采样"。12+书本方法被用作过滤器(排除差的)，而非预测器(选出对的)。从80万过滤后组合中随机抽3注，一等奖概率≈3/17,721,088。

## 2. 方案: 路径C

**聚合书本方法→高概率号码集(K=15红球)→Steiner覆盖设计**

两步:
1. 12+作者方法各产生33个红球评分 → 回测校准权重 → 加权聚合 → top-15
2. 在15个热号上做t=4覆盖设计 → 4-6注 → 蓝球多作者投票分配

## 3. 架构

```
12+方法 → score_reds(data) → [33]float
              ↓
回测校准 → 滑动窗口recall@15 → 方法权重
              ↓
实时聚合 → weighted_sum → top-15红球
              ↓
覆盖设计 → Steiner t=4 SA → 6注红球 (零改动)
              ↓
蓝球分配 → 多作者投票交集 (零改动)
```

## 4. 新增模块: ml/ensemble_aggregator.py

### 4.1 方法注册表

统一接口: `score_reds(data) -> list[float]` (33个分数, 0-1)

初始注册12方法:
- 吴明·5期重号: `_period5_hotness()` → 热号=1.0, 其他=0.3
- 吴明·9期冷号反转: `_period9_cold()` → 遗漏9-20期=1.0
- 吴明·6区间排除: `_zone6_exclusion()` → 非空区=1.0
- 吴明·极值优先: `_extreme_value_dan()` → 位置极值候选=1.0
- 彭浩·MA双通道: `_get_peng_channels()` → 通道内=1.0
- 蒋加林·排列型: 位间隔/位跨度/位形态 → 模式匹配=1.0
- 张委铭·围号选号: 18杀号→存活=1.0
- 李志林·八招定胆: 8定胆→被选中=1.0
- 刘大军·定尾选号: position_tail_analysis() → 高频尾数=1.0
- 刘大军·重合码: COINCIDENCE_TAILS {1,3,6,8} → 匹配=1.0
- 李相春·趋势分析: dashboard() → 散度/偏度/AC综合
- 频率基线: Laplace平滑频率 → 归一化

新增方法只需: 实现score_reds + 一行register_method()。

### 4.2 回测校准

```
backtest_calibrate(data, k=15, window=50):
  for 每方法m:
    recalls = []
    for i in [len(data)-50, len(data)):
      train = data[:i]
      actual = set(data[i][1:7])
      top_k = argsort(m.score_reds(train))[:k]
      recall = |actual ∩ top_k| / 6
      recalls.append(recall)
    weight[m] = mean(recalls)
  return softmax(weights, temperature=0.5)
```

参数:
- K=15 (C(15,6)=5005组合, SA可收敛)
- 验证窗口=50期 (~4个月)
- 权重下限=0.01 (不归零)
- 存SQLite strategy_weights表 (已有)

### 4.3 实时聚合

```
aggregate_scores(method_scores, weights) -> [33]float:
  final[n] = Σ(w_m × score_m[n]) / Σw_m

select_hot_numbers(final, k=15) -> list[int]:
  return argsort(final)[:k]
```

## 5. 覆盖设计参数 (零改动)

| 参数 | 值 | 理由 |
|------|-----|------|
| K (热号数) | 15 | C(15,6)=5005, SA<1秒收敛到99%+ |
| t (覆盖强度) | 4 | 保底四等奖(¥200) |
| 注数 | 6 | SA收敛下限+冗余 |
| 注间分散 | max_overlap=2 | 防止扎堆 |

## 6. API

```
GET /api/ensemble/tickets?k=15&t=4&n=6

Response:
{
  "ok": true,
  "algorithm": "Ensemble-Covering-v15-t4",
  "tickets": [{reds:[...], blue:N}, ...],
  "hot_numbers": [3,7,12,15,18,21,24,26,27,28,29,30,31,32,33],
  "method_weights": {"吴明·5期重号": 0.15, ...},
  "coverage_pct": 99.2,
  "guarantee": "如果全部6个开奖红球都在15个热号中，则≥99%概率至少命中4个红球",
  "cost_rmb": 12,
  "ev_estimate": {...}
}
```

## 7. 数据流

```
用户点击"智能覆盖" → GET /api/ensemble/tickets
  → ensemble_aggregator.ensemble_tickets(k=15, t=4, n=6)
    → backtest_calibrate(data) → 权重(带缓存)
    → score_all_methods(data) → 12×33分数矩阵
    → aggregate_scores → top-15红球
    → covering_design.build_covering_tickets(hot_15, t=4) → 6注红球
    → 蓝球多作者投票 → 蓝球分配
  → 返回票集
```

## 8. 文件变更

| 文件 | 操作 | 说明 |
|------|------|------|
| `ml/ensemble_aggregator.py` | **新增** | 方法注册表+回测+聚合 |
| `server/ml_bridge.py` | 修改 | +ensemble_tickets()桥接 |
| `server/handler.py` | 修改 | +/api/ensemble/tickets路由 |
| `static/js/ui/draw.js` | 修改 | +"智能覆盖"按钮 |
| `index.html` | 不修改 | 零改动 |

不修改: micro_portfolio.py, covering_design.py, db.py, 蓝球逻辑, 现有UI

## 9. 验收标准

1. `/api/ensemble/tickets` 返回6注, 每注6红+1蓝
2. 热号集大小=15, 覆盖≥95%
3. 回测权重非全等(方法有区分度)
4. 现有"生成号码"功能不受影响
5. `python3 -m pytest tests/ -v --tb=short` 全绿
6. 新增方法→只需加注册表一行, 不碰其他代码

## 10. 现实主义边界

- K=15含全部6红的组合数学上限=0.45% (C(15,6)/C(33,6))
- 方法聚合的目标是让这0.45%尽可能接近100%实现(即每次开奖号都在top-15中)
- 基线(纯频率top-15)的recall@15≈0.44 (=15/33)
- 方法聚合需超过此基线才有价值
