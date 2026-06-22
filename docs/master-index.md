# 彩票预测项目 — 文档总索引

## 已实现策略来源

| # | 作者/书名 | 出版 | 算法 | 分析文档 | 代码位置 |
|---|----------|------|------|---------|---------|
| 1 | 刘大军《蓝球中奖绝技》 | 2011 | 五期断蓝/三斜连/三效应/竹节/冷热/遗漏/矩阵杀蓝 (7规则) | `liu-dajun-blue-ball-algorithms-20260618.md` | `micro_portfolio.py:_liu_dajun_blue()` |
| 2 | 刘大军《蓝球中奖绝技》补遗 | 2011 | 三斜连/竹节详细数值 + 32公式杀蓝 | `liu-dajun-supplement-ch3-ch4-20260618.md` | 同上 |
| 3 | 刘大军《终极战法》第2版 | 2014 | 6×6行列分布+断区3D码转换 | `liu-dajun-ultimate-2014-20260619.md` | `zone_break.py` |
| 4 | 蒋加林《抓住500万》 | 2001 | 回测排名(全量枚举) + 奇偶/和值过滤 | `jiang-jialin-lottery-algorithms-20260618.md` | `micro_portfolio.py:_backtest_rank_tickets()` + `_check_soft()` |
| 5 | 彩乐乐《微尔算法》 | 2017 | 8步012路条件过滤(手动模式) | `weier-algorithm-comprehensive-20260618.md` | `weier_filter.py` |
| 6 | 彩乐乐《中彩好帮手》 | 2017 | 形态统计(奇偶/大小max)+尾数驱码 | `blue-ball-statistics-2017-20260619.md` | `micro_portfolio.py:_cailele_blue()` |
| 7 | 公益时报《玩转双色球》 | 2010 | 期次转换(012路码型)+代码对称(除5余数) | `play-ssq-2010-20260619.md` | `micro_portfolio.py:_gongyi_blue()` |
| 8 | 吴明《蓝球大法》 | 2006 | 背离率+大小/4区间/除4余数极值 | `wu-ming-blue-ball-2006-20260619.md` | `micro_portfolio.py:_wuming_blue()` |
| 9 | 张委铭《杀号定胆选号》 | 2015 | 十二值选号法+八值选号法+行列网格 | `zhang-weiming-comprehensive-20260619.md` | `zhang_weiming.py` |
| — | 数学(Stömmer/La Jolla) | 2024 | Mandel/Steiner覆盖设计 | `micro-portfolio-diversity-plan-20260617.md` | `covering_design.py` |
| — | 数学(Jaccard) | — | 贪心最大化min-Jaccard选注 | `micro-portfolio-diversity-plan-20260617.md` | `micro_portfolio.py:_greedy_diverse_tickets()` |

## 前端面板架构

```
策略面板 option cards (8个) → [生成号码] → /api/micro/tickets
面板 tabs:
├─ 遗漏分析 / 走势分析 / 推荐方案 / 开奖对比 / 复盘跟踪
├─ 断区转换 (刘大军 6×6 手动) → /api/zone-break/*
├─ 微尔选号 (彩乐乐 8步 手动) → /api/weier/*
└─ 张委铭 (十二值/八值/网格 自动) → /api/zhang/*
```

## 后端 API (15个活跃)

| 端点 | 用途 | 来源 |
|------|------|------|
| `/api/micro/tickets` | 核心: 池采样+所有option card策略 | 综合 |
| `/api/covering/generate` | Mandel覆盖设计 | 数学 |
| `/api/weier/manual` | 微尔8步手动条件过滤 | 彩乐乐2017 |
| `/api/zone-break/filter` | 6×6断区3D码过滤 | 刘大军2014 |
| `/api/zhang/twelve-value` | 十二值红球选号 | 张委铭2015 |
| `/api/zhang/eight-value` | 八值蓝球选号 | 张委铭2015 |
| `/api/zhang/grid` | 3×11行列自动断区 | 张委铭2015 |
| `/api/zhang/combined` | 十二值+八值组合 | 张委铭2015 |

## 会话记录

| 日期 | 文档 | 内容 |
|------|------|------|
| 6/11 | `refactor_plan.md` + memory | 前后端死代码大清理 + Observer重构 |
| 6/17 | `micro-portfolio-diversity-plan-20260617.md` | 三层注间多样性方案 |
| 6/18 | `liu-dajun-*.md` + `jiang-jialin-*.md` + `weier-*.md` | 刘大军/蒋加林/微尔算法提取 |
| 6/19 AM | `wu-ming-*.md` + `play-ssq-*.md` + `liu-dajun-ultimate-*.md` | 吴明/公益时报/刘大军终极战法 |
| 6/19 PM | `zhang-weiming-*.md` + `architecture-review-*.md` + `session-20260619-zhang-weiming-implementation.md` | 张委铭全书+三算法实现+架构诊断 |

## 测试

69/69 passed (含 15 集成测试)
