# 对话归档 — 2026-06-29 深度信号整合

## 背景

用户北极星目标：中一等奖。核心理念：大模型作为算法外脑，挖掘一切可行的组合数学/统计检验/信息论/决策论方法，系统性地优化双色球出号流程。

## 本轮完成的工作

### 1. 修复 changepoint_window 类型 bug
- 文件：`ml/micro_portfolio.py:1171-1180`
- 问题：`detect_recent_window()` 返回 `int`（如 100 期），代码当 `list` 调用 `len()` → `test_generate_tickets_with_soft` 崩溃
- 修复：整数窗口大小自动切片 `load_draws()`，同时兼容 list 类型

### 2. _windowed_data 真正消费
- 问题：变量声明后蓝球/红球选择仍调用 `load_draws()`，变点窗口未被使用
- 修复：3 处调用点改为 `_windowed_data`
  - 条件熵蓝球选号：`entropy_blue_candidates(_windowed_data, n=6)`
  - 精确覆盖热号：`analyze_conditional_entropy(_windowed_data, n_red=15)`
  - 差集热号：同上

### 3. FDR 信号融入 Bandit 策略选择
- 文件：`ml/bandit_strategy.py`、`ml/micro_portfolio.py`
- `collect_signals` 提前到 bandit 分支内部，FDR 结果传入 `bandit_select_and_generate(fdr_signals=...)`
- 新增 `BanditState.set_fdr_bias()`：
  - FDR 所有方法不显著 → 复杂 arm 初始 alpha 降至 0.5 → Thompson 偏向简单策略（pool+freq）
  - 有显著方法 → 正常先验

### 4. 覆盖表统一
- 文件：`ml/exact_cover.py`、`ml/combinatorial_math.py`
- WHEEL_V8~V11 同步至 `exact_cover.py` 的 `KNOWN_COVERS`（从 6 条目增至 10 条目）
- `get_known_wheel()` 优先查 `exact_cover.KNOWN_COVERS`（canonical source），本地 `KNOWN_WHEELS` 保留回退

### 5. 验证
- 100 个测试全部通过
- 所有导入链正常

## 当前系统架构

```
用户界面 → /api/micro/tickets → handler.py → ml_bridge → generate_tickets()
                                                          ├── Bandit 策略 (FDR偏置arm)
                                                          ├── 作者模式
                                                          ├── pool (随机/贪心/回测)
                                                          ├── exact_cover (La Jolla)
                                                          └── diffset (差集构造)
                    
深度信号层 (deep_signals.py):
  SPRT → 检测到偏倚时加大注数
  Kelly → 最优投注数
  FDR → 过滤不显著方法 + 偏置Bandit
  Changepoint → 只用变化点后数据
  NIST → 物理偏倚检测
```

## 已知剩余问题（本次未处理）

1. 吴明系列 4 个方法回测返回 0 — 未排查
2. 前端 377 行 index.html + 4474 行 JS 单文件 — 未模块化
3. 部分按钮功能未实现（智能覆盖、偏差增强、B-L融合、分位策略）
4. 回测系统不完整 — backtest_results 表空
5. prediction_log 写入但缺少分析/闭环
