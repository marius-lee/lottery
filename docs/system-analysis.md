# 双色球智能选号系统 — 系统化分析

> 审查日期: 2026-06-02 | 目标: 中一等奖

---

## 代码结构

```
lottery/
├── app.py              # 后端 HTTP + SQLite (700行)
├── index.html           # 前端全部逻辑 (2750行)
├── ml/
│   ├── __init__.py      # 导出
│   ├── xgb_predictor.py # XGBoost 49分类器 (357行)
│   └── lstm_predictor.py# LSTM 序列预测 (267行)
├── start.sh             # 启动脚本
├── CLAUDE.md            # 项目文档
└── docs/
    └── system-analysis.md  # 本文档
```

---

## 一、数据层

| 功能 | 实现 | 状态 |
|------|------|------|
| 中彩网 API | `fetch_from_cwl()` — Cookie 会话 + 自动重试 | ✅ 正常 |
| 500.com 备用源 | `fetch_from_500()` — HTML 正则解析 | ❌ 已失效 |
| SQLite 本地存储 | `draws` 表，INSERT OR REPLACE upsert | ✅ 正常 |
| 缓存策略 | `CACHE_MAX_AGE = 6h`，`force` 参数可绕过 | ✅ 正常 |
| 数据规模 | 2000 期 (2013~2026) | ✅ 已扩容 |

### 数据流

```
中彩网 API → fetch_from_cwl(300) → db_upsert_draws() → SQLite
                                              ↓
用户点击"更新数据" → /api/fetch?force=1 → fetch_data(force=True) → 返回 JSON
```

---

## 二、策略层 (17 策略)

所有策略在同一套 DATA (近100期) 上运行，加权投票产出共识推荐。

| # | 策略 | 函数 | 原理 | 实用价值 |
|---|------|------|------|----------|
| 1 | 频率 | `runFreqStrategy` | 历史总频率最高的号 | ⭐⭐⭐ |
| 2 | 遗漏 | `runOmissionStrategy` | 长期未出的冷号 | ⭐⭐⭐ |
| 3 | 趋势 | `runTrendStrategy` | 近期出现频率变化 | ⭐⭐⭐ |
| 4 | 均匀分布 | `runUniformStrategy` | 号码空间均匀覆盖 | ⭐⭐ |
| 5 | 随机 | `runRandomStrategy` | 纯随机 baseline | ⭐ (无实战价值) |
| 6 | 间隔 | `runIntervalStrategy` | 基于平均遗漏间隔 | ⭐⭐⭐ |
| 7 | 黄金分割 | `runGoldenRatioStrategy` | 0.618 冷热区间分配 | ⭐⭐ |
| 8 | 同尾 | `runSameTailStrategy` | 尾号重复模式 | ⭐⭐ |
| 9 | 相似期 | `runSimilarPeriodStrategy` | 匹配历史相似走势 | ⭐⭐⭐ |
| 10 | 定位 | `runPositionStrategy` | 每球位独立频率统计 | ⭐⭐⭐ |
| 11 | 共现 | `runCooccurStrategy` | 号码间关联规则 | ⭐⭐ |
| 12 | 马尔可夫(蓝) | `runMarkovBlueStrategy` | 蓝球转移概率 | ⭐⭐ |
| 13 | 温度 | `runTemperatureStrategy` | 热度动态衰减 | ⭐⭐ |
| 14 | 分形极值 | `runFractalExtremeStrategy` | Hurst 指数 R/S 分析 | ⭐ (与遗漏高度相关) |
| 15 | 指数衰减 | `runExponentialStrategy` | λ=0.85 加权频率 | ⭐⭐ (与趋势相关) |
| 16 | 混沌组合 | `runChaosComboStrategy` | Logistic Map 多μ值 | ⭐ (与混沌重叠) |
| 17 | 混沌 | `runChaosStrategy` | 倪大成混沌分形预测 | ⭐ |

### 策略冗余分析

```
混沌组合 ≈ 混沌            → 同源 Logistic Map，组合策略是多μ值的包装
分形极值 ≈ 遗漏            → Hurst 指数本质上衡量遗漏的长程记忆
指数衰减 ≈ 趋势            → 都是近期频率加权
```

---

## 三、权重与过滤

### 7维加权融合 (`buildEnhancedWeights`)

| 维度 | 权重 | 描述 |
|------|------|------|
| 频率 | 20% | 历史出现总次数 |
| 遗漏 | 15% | 距上次出现已过多少期 |
| 趋势 | 15% | 近期30期 vs 长期100期 |
| 邻号 | 10% | 上期号码的相邻号 |
| 重号 | 10% | 上期号码重复概率 |
| 012路 | 10% | 除以3余数分布 |
| 同尾 | 10% | 尾号重复倾向 |
| 奇偶 | 10% | 奇偶数平衡 |

### 11条硬过滤 (`hardFilter`)

1. 和值 70~140
2. 奇偶比 2:4 / 3:3 / 4:2
3. 大小比 2:4 / 3:3 / 4:2
4. 三区均有号
5. 至少一对连号
6. 跨度 18~32
7. AC值 5~10
8. 质数 1~3 个
9. 蓝球不与上期重复
10. 同尾号至少一对
11. 蓝球奇偶偏差检测

---

## 四、分析面板

| 面板 | 功能 |
|------|------|
| 遗漏热力图 | 红球 1-33 + 蓝球 1-16 遗漏期数，hot/warm/cool/cold 四档 |
| 综合指标 | AC值、跨度、质数、龙头凤尾、重号/邻号/同尾统计 |
| 权重分布 | 红球 Top 10 + 蓝球排名，含进度条 |
| 相似期分析 | 历史相似走势匹配 |
| 走势图 (Canvas) | 和值/跨度/奇偶/三区 走势 + 10期均线 |
| 历史开奖列表 | 按期号倒序显示所有数据 |
| 用户选号记录 | 已保存的生成号码 |

---

## 五、ML 模型

### XGBoost (`ml/xgb_predictor.py`)

- **架构**: 49 个独立二分类器 (33 红 + 16 蓝)
- **特征**: 15 维 (遗漏、窗口频率、趋势、间隔、质数标记、分区、尾号)
- **训练**: `XGBClassifier(n_estimators=100, max_depth=5)`, 时序列划分 80/20
- **输出**: 每号码的出现概率 → Top-6 红 + Top-1 蓝
- **模型文件**: `.cache/xgb_models/{red_1..33, blue_1..16}.pkl` (49 文件)
- **状态**: ✅ 已训练 (49/49), 磁盘可加载

### LSTM (`ml/lstm_predictor.py`)

- **架构**: Embedding(64) + Per-Ball LSTM(128) + Global LSTM(64) + Softmax
- **输入**: 过去 5 期 × 6 球位
- **红球输出**: (6, 33) 每球位每号码概率
- **蓝球输出**: (16,) 概率分布
- **模型文件**: `.cache/lstm_models/{red_model,blue_model}.keras`
- **状态**: ✅ 已训练 (TensorFlow 2.21.0, Python 3.12)

### ✅ ML 已接入出号流程

```
前端 draw 流程: 13策略 + AI集成 → 共识投票 → 过滤 → 出号
                 ↑ ML 作为第14个策略参与投票 (权重1.5)

后端 ML API:    /api/ml/predict/ensemble→ XGBoost+LSTM 双模型融合
                /api/ml/backtest-result → ML 滑动窗口回测
                /api/recommend          → AI推荐排名+复式建议
                前端调用:                → 开奖时阻塞等待AI预测就绪

结论: ML 已全面接入 ✅
```

---

## 六、回测系统

### 滚动回测 (`runRollingBacktest`)

- 滑动窗口模拟
- 对每个策略独立回测
- 计算平均红球命中、蓝球命中率
- 结果自动更新策略权重
- 持久化到 `backtest_results` 表

### 回测覆盖

- ✅ ML 模型回测 (`/api/ml/backtest-result` + `runMLBacktest()`)
- ✅ 13策略回测 (滑动窗口，自动更新权重)
- ✅ 多期跟踪 (`prediction_log` 表 + 复盘面板 + 趋势图)
- ⚪ 过滤器有效性测试 (低优先级，过滤规则基于历史统计已验证)

---

## 七、问题清单

### 已解决

| 项目 | 状态 |
|------|------|
| 500.com 抓取 | ✅ 已删除 |
| LSTM 训练 | ✅ TF 2.21 + Python 3.12 |
| ML 前向预测 | ✅ 前端调用 /api/ml/predict/ensemble |

### 冗余

| 项目 | 理由 |
|------|------|
| 混沌组合 ≈ 混沌 | 同源，合并 |
| 分形极值 ≈ 遗漏 | Hurst 对彩票无增益 |
| 指数衰减 ≈ 趋势 | 近期加权方式不同但结论高度相关 |
| 随机策略 | baseline 无实用价值 |

### 关键缺口 (按影响排序)

1. 🔴 **ML 未接入出号流程** — 最先进的能力没被使用
2. 🔴 **回测不覆盖 ML** — 无法量化 ML 模型的实际效果
3. 🟡 **DATA 仅 100 期** — 策略层的统计窗口太短
4. 🟡 **无多期跟踪** — 无法评估预测趋势和质量
5. 🟡 **无资金管理** — 只出号不说怎么买
6. 🟡 **出号不评估** — 生成后就完了，没有反馈闭环

---

## 八、改进路线图

### Phase 1: 清理 (删冗余 + 修bug)

```
✂️ 删除 500.com 抓取器
✂️ 删除/合并 混沌组合→混沌
✂️ 删除 分形极值
✂️ 删除 随机策略
```

### Phase 2: ML 接入 (核心)

```
🔥 前端集成 AI (XGBoost+LSTM) 双模型预测 → ✅ 已完成
🔥 策略共识 + ML 概率 → AI推荐引擎 → ✅ 已完成
🔥 回测覆盖 ML 模型 → ✅ 已完成
🔥 资金管理 (复式/胆拖建议) → ✅ 已完成
🔥 复盘追踪 + 趋势图 → ✅ 已完成
```

### Phase 3: 闭环反馈

```
🆕 多期预测跟踪表
🆕 命中率趋势
🆕 资金管理建议 (复式/胆拖)
```
