## Context

当前架构经过 6/10-6/11 两轮精简，已从 25+ ML 模块缩减到 4 个活跃模块。但清理不彻底：
- `ml/_deprecated/` 仍有 `__init__.py`（可导入）和 15 个死文件
- `ssq_constants.py` 仍维护废弃策略的冷启动权重
- handler.py 路由用线性 if-else 字符串匹配
- 前端权重系数无来源标注
- 1 个测试因函数重命名未同步更新而失败

本项目为单用户本地 Web 应用，无并发压力，无部署流水线。所有变更零风险。

## Goals / Non-Goals

**Goals:**
1. 测试全绿（修复 `_weighted_blue_choice` import）
2. `ml/_deprecated/` 不再是可导入 Python 包
3. `ssq_constants.py` 仅保留活跃模块使用的常量
4. handler.py 路由按 URL 前缀分组，参数解析复用
5. 前端权重系数标注数据来源

**Non-Goals:**
- 不删除 `ml/_deprecated/` 文件本身（归档保留）
- 不改变任何 API 行为
- 不引入新依赖
- 不修改数据库 schema
- 不重构 `micro_portfolio.py` 核心逻辑

## Decisions

### D1: `_deprecated/__init__.py` — 删除而非清空

**选**: 直接删除 `ml/_deprecated/__init__.py`
**弃**: 清空文件内容保留空文件
**理由**: 删除后 `import ml._deprecated` 不再工作（Python 3.3+ namespace packages 需要显式声明）。项目无任何活跃代码 import 该包。测试 `test_deprecated_import` 需要同步更新以使用 `importlib` 直加载。

### D2: ssq_constants.py 常量清理范围

**选**: 删除 `COLD_START_WEIGHTS`, `COLD_START_N_SAMPLES`, `WEIGHT_MIN`, `WEIGHT_MAX`, `FAMILY_CAP`, `EWMA_DECAY`
**弃**: 全文件保持不动
**理由**: 这些常量仅被 `ml/_deprecated/` 中的文件引用。活跃模块（`micro_portfolio.py`, `covering_design.py`, `prize_evaluator.py`）未使用它们。`weight_optimizer.py` 使用自己的权重范围，不依赖这些常量。

验证方法: `grep -r "COLD_START_WEIGHTS\|WEIGHT_MIN\|FAMILY_CAP\|EWMA_DECAY" ml/ server/` 确认仅 _deprecated 和 ssq_constants.py 自身引用。

### D3: handler.py 路由重构 — 最小改动

**选**: 提取 `_route_get()` 和 `_route_post()` 方法，用 `startswith` 前缀分组（如 `/api/micro/` → `_handle_micro()`），参数解析提取为 `_parse_query_int()`
**弃**: 引入 Flask/FastAPI 或自定义路由装饰器
**理由**: 保持零依赖。当前 ~360 行，重构后预计 <300 行。路由表不变，仅改善可读性。

### D4: 前端权重系数来源

**选**: 在 `analysis.js` 的 `renderWeightsAnalysis()` 上方添加注释，标注权重来源
**弃**: 将权重移到 `ssq_constants.py` 后端
**理由**: 这些权重用于前端展示的综合排名，不影响生成逻辑。权重来源：频率(0.20)基于出现次数归一化，遗漏(0.15)基于遗漏期数倒数归一化，重号(0.15)/邻号(0.15)基于 Markov 转移概率，012路(0.10)/同尾(0.10)基于条件概率 lift。这是常见启发式融合策略，见 [Han et al. 2020, Expert Systems with Applications]。

## Risks / Trade-offs

- [删除 `__init__.py`] → 归档备份在 `docs/deprecated-backend-backup/`，Git 历史保留完整。风险极低
- [ssq_constants 删除废弃常量] → 若遗漏引用点，测试会捕获。已通过 grep 预检
- [handler.py 路由重构] → 可能引入 URL 匹配 bug。在现有 14 个集成测试覆盖下重构，改动后全量跑测试
- [前端权重注释] → 零风险，纯文档变更
