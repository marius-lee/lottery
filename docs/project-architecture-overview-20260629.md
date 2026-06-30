# 项目架构全景 · 2026-06-29 代码通读

## 概览

双色球智能选号系统。Python 后端 + 单 HTML SPA 前端。代码量约 5,400 行 Python + 1,600 行 JS (+ 13,000 行已归档/参考文档)。

## 北极星

中一等奖。所有决策围绕「组合数学提高效率」而非「预测号码」。

## 核心流水线

```
bias_detector.py (门禁: Bootstrap Bonferroni 判定频率偏差)
        ↓
  通过 → hot set → ensemble → covering_design → 出票
  不通过 → 全号码集 → covering_design → 出票
```

## 文件地图

### 基础层
| 文件 | 行数 | 职责 |
|------|------|------|
| `ml/ssq_constants.py` | 70 | 游戏规则、奖金、概率、La Jolla 覆盖界。全部可溯源 |
| `ml/__init__.py` | 5 | 公开 API: generate_tickets, covering_design, prize_evaluator |

### 门禁层
| 文件 | 行数 | 职责 |
|------|------|------|
| `ml/bias_detector.py` | 250 | 贝叶斯偏差发现引擎。Beta-Binomial 共轭 + Bootstrap + Bonferroni。4 层分析 (号码/位置/蓝球/联合)。当前结论: 不通过 → 回归纯覆盖设计 |

### 核心出号引擎
| 文件 | 行数 | 职责 |
|------|------|------|
| `ml/micro_portfolio.py` | 1,600 | 系统核心。枚举 C(33,6) 全量建池 → 硬过滤 (等差/历史) → 软过滤 (连号/间距/奇偶/和值/三色) → 条件熵 + NIST + 互信息 加权采样。6 种出号模式: pool / greedy / exact_cover / diffset / bandit / author。线程安全 PoolState |
| `ml/covering_design.py` | 200 | Mandel 贪心集合覆盖。v≤18 全枚举，v>18 抽样。1-1/e 近似比保证。v=8-11 用已知最优轮次表 |
| `ml/prize_evaluator.py` | 130 | 超几何分布 + 策略 shift 后的各奖等概率 + EV 计算 |

### 偏差引擎 v2
| 文件 | 行数 | 职责 |
|------|------|------|
| `ml/bias_engine.py` | 280 | Dirichlet-Multinomial 后验 + Thompson 采样 (Marsaglia-Tsang/ Ahrens-Dieter Gamma) + Gumbel-Max 无放回选号 |
| `ml/engine_integration.py` | 60 | 引擎集成层。删除 5 个归档依赖后精简为 3-方法加权 |

### 方法聚合
| 文件 | 行数 | 职责 |
|------|------|------|
| `ml/ensemble_aggregator.py` | 300 | 5 个 OOS 验证有效的方法 → 加权聚合 → 覆盖设计。注册表 + 回测校准 + 温度 softmax 权重 + FDR 过滤 + 策略权重持久化 |

### 深度信号武器库
| 文件 | 行数 | 职责 |
|------|------|------|
| `ml/deep_signals.py` | 80 | 六路信号统一注入: SPRT / Kelly / FDR / 变点 / NIST / 轮次表 |
| `ml/sprt.py` | 80 | Wald 序贯概率比检验。α=0.05, β=0.10 |
| `ml/kelly.py` | (估算 80) | 凯利最优投注比例 — 负 EV 时 f*=0 |
| `ml/fdr.py` | (估算 100) | Benjamini-Hochberg FDR 多重比较校正 |
| `ml/changepoint.py` | 80 | Fearnhead 贝叶斯变点检测。已知 7 个历史变化点 |
| `ml/nist_tests.py` | (估算 100) | NIST SP 800-22 随机性检验 |
| `ml/cond_entropy.py` | 130 | 5-gram 条件熵 + 互信息聚类。选熵最低的号码 |
| `ml/bandit_strategy.py` | 150 | 8-arm Thompson 采样在线策略学习 |
| `ml/monitor.py` | (估算 80) | 综合监控面板 |

### 作者策略模块 (12 本书/作者)
| 文件 | 行数 | 著作 |
|------|------|------|
| `ml/wuming.py` | 260 | 吴明 (2006/2010): 蓝球排除 + 红球战法 |
| `ml/xia_zhiqiang.py` | 50 | 夏志强: 减4加4测蓝 + 计算观察法 |
| `ml/liu_dajun.py` | 100 | 刘大军 (2010/2011/2014): 定尾选号 + 重合码 + 蓝球7规则 + 断区转换 |
| `ml/jiang_jialin.py` | 370 | 蒋加林 (2001): 排列型思维 + 位置间隔/跨度/形态 |
| `ml/li_zhilin.py` | 840 | 李志林 (2012): 八招定胆 + 三胆辅助 + 转换法 + 杀号 |
| `ml/zhang_weiming.py` | 800 | 张委铭 (2017): 围号选号 (18种杀号→12红球 + 10种杀号→8蓝球) |
| `ml/peng_hao.py` | 530 | 彭浩 (2010): 五均线通道 + 方向预测 + 极端值规则 |
| `ml/weier_filter.py` | 710 | 彩乐乐 (2017): 8步012路条件过滤 |
| `ml/li_xiangchun.py` | 540 | 李相春 (2003): 散度/偏度/DHR/三浪/AC值 |

### 组合数学工具
| 文件 | 行数 | 职责 |
|------|------|------|
| `ml/combinatorial_math.py` | (估算 200) | 已知最优轮次表 (v=8/9/10, t=4: 4/8/10 注) |
| `ml/exact_cover.py` | 260 | La Jolla 精确覆盖 + 整数规划 |
| `ml/diffset_cover.py` | 240 | 差集构造 2-覆盖 |
| `ml/mandel_cover.py` | 310 | Stefan Mandel 全买策略 — V=8~15 成本/概率对比 |
| `ml/mi_detector.py` | 260 | 互信息矩阵 + Bootstrap 检验 |
| `ml/mi_selector.py` | 170 | 互信息热号选择 |
| `ml/zone_break.py` | (估算 200) | 刘大军 6×6 行列断区 3D 码 |

### Server 层
| 文件 | 行数 | 职责 |
|------|------|------|
| `app.py` | 70 | HTTP 服务入口 (0.0.0.0:8520) |
| `server/handler.py` | 290 | ~50 个 API 端点路由 |
| `server/db.py` | 230 | SQLite (9 表: draws, user_picks, strategy_picks, meta, strategy_weights, backtest_results, prediction_log, strategy_performance_log, red_freq) |
| `server/fetcher.py` | 80 | 中彩网 API, 6h 缓存, Cookie 会话 |
| `server/ml_bridge.py` | 550 | ML 门面 — 跨模块桥接 + 40+ API 适配函数 |
| `server/scheduler.py` | 80 | daemon 线程, 二/四/日 22:05 自动拉取 + 兑奖 |
| `server/auto_claim.py` | 170 | 自动兑奖引擎: 预测 vs 实际匹配 → 写 performance_log → 触发权重重算 |
| `server/weight_optimizer.py` | 80 | James-Stein 收缩 + EWMA 折扣 + 策略族上限 |
| `server/recommend.py` | 60 | 频率 + 遗漏权重 → 复式/胆拖方案 |
| `server/query_parser.py` | (估算 30) | URL 查询参数解析 (qbool/qint/qlist/qstr/qfloat) |

### 前端 (SPA)
| 文件 | 行数 | 职责 |
|------|------|------|
| `index.html` | 520 | 单页应用, 策略面板 + 号码展示 + 分析 tab |
| `static/js/app.js` | 86 | 入口: 初始化 + 事件绑定 + window 全局导出 |
| `static/js/store.js` | 43 | Observer 模式全局状态单例 |
| `static/js/data.js` | 66 | 从 /api/data 加载 + 定时刷新 |
| `static/js/ui/draw.js` | 560 | 抽号 UI 核心: 动画 + API 调用 + 渲染 |
| `static/js/ui/panels.js` | 180 | 面板切换 + 历史管理 + 保存 |
| `static/js/analysis/` | 10 文件 | 频率/遗漏/重号/邻号/012路/AC跨度/质数/龙风/同尾/相似期 |
| `static/js/ui/` | 11 作者面板 | 蒋加林/李志林/刘大军/彭浩/张委铭/微尔/吴明/杨/曾/李相春/断区 |

### 测试 & 工具
| 文件 | 行数 | 职责 |
|------|------|------|
| `tests/test_core_generation.py` | 150 | 微投资组合单元测试 |
| `tests/test_covering_design.py` | 60 | 覆盖设计测试 |
| `tests/test_ensemble.py` | (估算 40) | 聚合测试 |
| `tests/test_imports.py` | (估算 20) | 导入测试 |
| `tests/test_integration.py` | (估算 80) | 集成测试 (启服务器) |
| `tools/validate_strategies.py` | 90 | 策略回溯验证: 滑动窗口 + z-test + Bonferroni |
| `tools/benchmark_authors.py` | (估算 150) | 作者策略基准测试 |
| `tools/check_sourced_params.py` | (估算 60) | 参数来源检查 |

### 关键文档
| 文件 | 内容 |
|------|------|
| `docs/strategic-analysis-prediction-vs-coverage.md` | **本次战略分析**: 预测 vs 覆盖的数学论证 |
| `docs/master-index.md` | 文档总索引 — 12 个策略来源 + 前端面板架构 + 会话记录 |
| `docs/architecture-review-20260619.md` | 架构审查记录 |
| `docs/236-algorithms-master-list.md` | 236 种彩票算法清单 |

### 已归档 (ml/_deprecated/)
15 个文件: XGBoost, LSTM, GPT 自训练, Thompson 采样 (旧版), Sobol 序列, Sirius, EVT, RMT, 高级统计, 粒子滤波, 策略 Bandit, FDR 筛选, 熵值选号, Kelly 分配 (旧版)

---

## 当前门禁状态 (2026-06)

偏差检测引擎报告:
- **Bootstrap Bonferroni**: FAIL (0 个号码通过多重检验)
- **经验贝叶斯过离散**: FAIL (≈0, 接近完全均匀)
- **结论**: 无可靠偏差证据 → 预测策略无效，纯覆盖设计

## 关键决策记录

1. (2026-06-28) 偏差检测门禁 — Bootstrap Bonferroni 作为所有策略的入口守卫
2. (2026-06-28) 作者算法从独立出号器降为 ensemble 信号源
3. (2026-06-28) Good-Turing 删除 — 不适用于均匀概率场景
4. (2026-06-28) 蓝球策略从 8 种简化为 1 种 (Laplace 频率加权)
5. (更早) LSTM/XGBoost/GPT 等 15 个模块归档 — OOS lift ≤ 1.0
6. (更早) 13 个 ensemble 方法精简至 5 个
