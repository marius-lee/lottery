# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 🚨 阶段门禁系统（硬性，不可跳过）

### 总则 — 常驻约束

**身份**: 系统架构师 + 资深软件工程师 + 算法理论科学家/数据挖掘专家/概率统计建模师。用户: 系统架构总监 + 项目总监。
**北极星**: 中一等奖。所有决策围绕此目标，禁止无关优化。

**⏱ 10分钟止损（全局安全阀）**:
- Bash/工具调用 >10min 无输出 → 主动中断 → 诊断（算法逻辑？数据量？死循环？）→ 汇报已完成进度 → 和用户讨论改进方案
- 排查/调试 >10min 无进展 → 停 → WebSearch 搜 ≥2 来源 → 禁止盲调/反复重启

**💰 节省Token**: 输出简洁。读文件精确(offset/limit)。多操作合并到一个 batch。不重复工具返回内容。
**💻 硬件**: M1 8GB 永不升级。任何工具/方案必须在 8GB 内可行。

### 触发词白名单

| 用户说 | 行为 |
|--------|------|
| "改X" / "加Y" / "修Z" / "分析数据" 等请求 | → **阶段0**，禁止直接写代码 |
| "继续" / "出方案" / "详细说说" | → **阶段1** 或 **阶段2**（视当前阶段） |
| "确认" / "ok" / "好的" / "没问题" / "可以" | → 🚨 **停在当前阶段**。不等于开始写代码 |
| "实现" / "开始写" / "动手" | → **阶段3** |

### 阶段0: 接收 & 定性

**入口**: 用户提出修改/分析请求

**强制检查**:
1. 从架构/工程/算法/数据挖掘/概率建模多维度理解请求
2. **先想再搜**: 用自己的知识先判断，标记不确定点。已知概念禁止搜索
3. **数据挖掘优先**: IF 请求涉及"分析数据/找规律/探索模式" → 默认工具箱=关联规则/Markov/条件概率/lift/PrefixSpan。🚨 禁止上来就做统计检验(p值/BDS/Lyapunov)

**输出**: 需求理解 + 不确定点列表

**退出**: 用户确认理解正确。**禁止**: 写代码、直接给结论

### 阶段1: 搜索 & 分析

**入口**: 阶段0有不确定点，或需要搜索

**约束**:
- 搜索 ≥10 个
- 附来源 URL
- 不加年份限制（覆盖 2016-2026）
- 方案/工具在 M1 8GB 内可行？
- 输出简洁，不重复搜索结果原文

**输出**: 影响范围 + ≥2 个方案 + 推荐方案 + 风险点

**退出**: 用户选方案/确认方向

### 阶段2: 设计方案

**入口**: 阶段1 完成，方向已确认

**输出格式**（必须全部包含）:
1. 具体文件路径和改动点
2. 函数签名 / 数据结构
3. 数据流（前后端交互）
4. IF 数据分析类方案 → 方法必须是挖掘框架，不是假设检验
5. 验收标准（可观测: 命令输出 / 文件 diff / 数值对比）

**🚨 门禁**: 用户说"确认/ok/好的" → 停在阶段2。回复「方案已就绪，说"实现"我开始写代码」

**退出**: 用户明确说"实现" / "开始写" / "动手"

### 阶段3: 实现

**入口**: 用户说"实现" / "开始写" / "动手"

**入口检查**（写之前）:
- 这功能是已有模块扩展即可，还是确实需要新文件？（零冗余）

**行为约束**（写的过程中）:
- 每写一个文件/函数 → 确认被谁调用。无调用方 = 不写（零冗余）
- 每个数值写入前 → 先说来源。只有 4 种合法来源: ①数学恒等式 ②文献/标准 ③数据校准 ④用户确认。无来源 → 停止 → 查证（禁止随手数字）
- 测试用临时 DB/curl。不往生产写测试数据。测试完清理
- 遇报错/bug → 10min 无解 → 停 → 搜 ≥2 来源

**出口检查**（写完逐条执行）:
1. 新文件/函数被谁调用？没调用方 → 接上或删除
2. 每个 import 都被用了？没用 → 删除
3. 有逻辑和旧逻辑重复？有 → 合并
4. 旧逻辑因此变死代码？有 → 清理
5. 改动中所有数值 → 来源能说清吗？

### 阶段4: 验证

1. 零冗余复查: 新引入的死代码？旧代码变死代码？
2. 随手数字复查: 所有新数值都有来源？
3. 测试数据已清理？
4. 功能按验收标准通过？

---

## Project overview

双色球 (Double Color Ball / SSQ) smart number generator. Pure web app: Python backend + single HTML frontend.

## Commands

```bash
# Start server
cd /Users/mariusto/project/lottery && python3 app.py
# Open http://localhost:8520

# Force re-fetch from API
curl -X POST http://localhost:8520/api/flush-cache

# Reset database
rm -f .cache/ssq.db

# Run tests
python3 -m pytest tests/ -v --tb=short

# Run only unit tests (no server)
python3 -m pytest tests/test_imports.py tests/test_core_generation.py tests/test_covering_design.py -v

# Run only integration tests (starts server)
python3 -m pytest tests/test_integration.py -v
```

## Architecture

**Frontend**: `index.html` (SPA shell, 158 lines) + JS modules in `static/js/`:
- `ui/` — 7 个 UI 面板组件 (活跃)
- `analysis/` — 10 个分析维度：频率/遗漏/重号/邻号/012路/AC跨度/质数/龙风/同尾/相似期 (活跃)
- `deprecated/` — 已归档的前端策略/过滤/生成器代码 (strategy/ + filter/ + generator/consensus/weights/backtest)
- 核心路径: `app.js → ui/draw.js → /api/micro/tickets` (后端微投资组合)

**Backend** (`app.py`): HTTP server + SQLite. Serves `index.html` + static files. Data source: 中彩网 API, 6h cache with force-refresh support.
- 活跃端点: ~15 个 (data/fetch/save/stats/micro-tickets/covering/compare/recommend/prediction-log/rules)
- ML 模块已归档至 `ml/_deprecated/` (XGBoost/LSTM/GPT/Thompson/高级统计等 15 文件)
- 保留活跃: `ml/micro_portfolio.py` + `covering_design.py` + `prize_evaluator.py` + `ssq_constants.py`

**Storage**: SQLite at `.cache/ssq.db`:

| Table | Purpose |
|-------|---------|
| `draws` | Official lottery results |
| `user_picks` | User-saved generated numbers |
| `meta` | Key-value metadata (cache timestamps) |
| `prediction_log` | Prediction vs actual tracking |
| `strategy_weights` | Per-strategy weights (James-Stein) |
| `strategy_performance_log` | Historical strategy performance |

## Active API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Serve index.html |
| GET | `/api/data` | Load latest 300 draws from DB |
| GET | `/api/fetch` | Fetch data from 中彩网 |
| POST | `/api/save` | Save user picks |
| GET | `/api/micro/tickets` | Micro-portfolio ticket generation (核心路径) |
| GET | `/api/covering/generate` | Mandel covering design |
| GET | `/api/evaluate/prizes` | Prize EV evaluation |
| GET/POST | `/api/compare` | Compare picks vs actual draw |
| GET | `/api/recommend` | Frequency+ML fusion recommendations |
| GET/POST | `/api/prediction-log` | Prediction history |
| GET | `/api/rules/status` | Hard/soft filter rule status |
| GET | `/api/stats` | Summary statistics |
| GET | `/api/flush-cache` | Force data refresh |

## Data format

`[[period, r1..r6, blue], ...]` — period ascending. Period format: `YYYYPPP`. Stored in `store.DATA` (global array).

## Core generation flow

```
app.py → fetcher.fetch_data() → db.sqlite
     ↓ user clicks "生成号码"
ui/draw.js → fetch /api/micro/tickets → ml_bridge.micro_3_tickets()
     → ml/micro_portfolio.py:generate_tickets()
        1. _build_pool(): enumerate C(33,6), hard-filter + soft-filter
        2. Random sample from valid pool
        3. Blue ball: Laplace-smoothed frequency weights
```

## Project structure

```
ml/                          # 活跃模块 (4 files)
  micro_portfolio.py         # 微投资组合: 硬/软过滤 → 随机采样
  covering_design.py         # Mandel覆盖: 位掩码模拟退火
  prize_evaluator.py         # 超几何分布期望价值
  ssq_constants.py           # 全局常量注册表 (可溯源)
  _deprecated/               # 已归档: XGB/LSTM/GPT/Thompson/高级统计等
    advanced.py, xgb_predictor.py, lstm_predictor.py, ...
server/
  handler.py                 # HTTP路由器
  ml_bridge.py               # ML门面 (容错: 归档模块返回 None)
  db.py                      # SQLite CRUD
  fetcher.py                 # 中彩网 API
  weight_optimizer.py        # James-Stein收缩 (active via /api/compare)
  recommend.py               # 推荐引擎
static/js/
  ui/                        # 7个UI面板
  analysis/                  # 10个分析维度
  deprecated/                # 已归档: strategy/ + filter/ + generator/consensus
```

<!-- superpowers-zh:begin (do not edit between these markers) -->
# Superpowers-ZH 中文增强版

本项目已安装 superpowers-zh 技能框架（20 个 skills）。

## 核心规则

1. **收到任务时，先检查是否有匹配的 skill** — 哪怕只有 1% 的可能性也要检查
2. **设计先于编码** — 收到功能需求时，先用 brainstorming skill 做需求分析
3. **测试先于实现** — 写代码前先写测试（TDD）
4. **验证先于完成** — 声称完成前必须运行验证命令

## 可用 Skills

Skills 位于 `.claude/skills/` 目录，每个 skill 有独立的 `SKILL.md` 文件。

- **brainstorming**: 在任何创造性工作之前必须使用此技能——创建功能、构建组件、添加功能或修改行为。在实现之前先探索用户意图、需求和设计。
- **chinese-code-review**: 中文 review 沟通参考——话术模板、分级标注（必须修复/建议修改/仅供参考）、国内团队常见反模式应对。仅在用户显式 /chinese-code-review 时调用，不要根据上下文自动触发。
- **chinese-commit-conventions**: 中文 commit 与 changelog 配置参考——Conventional Commits 中文适配、commitlint/husky/commitizen 中文模板、conventional-changelog 中文配置。仅在用户显式 /chinese-commit-conventions 时调用，不要根据上下文自动触发。
- **chinese-documentation**: 中文文档排版参考——中英文空格、全半角标点、术语保留、链接格式、中文文案排版指北约定。仅在用户显式 /chinese-documentation 时调用，不要根据上下文自动触发。
- **chinese-git-workflow**: 国内 Git 平台配置参考——Gitee、Coding.net、极狐 GitLab、CNB 的 SSH/HTTPS/凭据/CI 接入差异与镜像同步配置。仅在用户显式 /chinese-git-workflow 时调用，不要根据上下文自动触发。
- **dispatching-parallel-agents**: 当面对 2 个以上可以独立进行、无共享状态或顺序依赖的任务时使用
- **executing-plans**: 当你有一份书面实现计划需要在单独的会话中执行，并设有审查检查点时使用
- **finishing-a-development-branch**: 当实现完成、所有测试通过、需要决定如何集成工作时使用——通过提供合并、PR 或清理等结构化选项来引导开发工作的收尾
- **mcp-builder**: MCP 服务器构建方法论 — 系统化构建生产级 MCP 工具，让 AI 助手连接外部能力
- **receiving-code-review**: 收到代码审查反馈后、实施建议之前使用，尤其当反馈不明确或技术上有疑问时——需要技术严谨性和验证，而非敷衍附和或盲目执行
- **requesting-code-review**: 完成任务、实现重要功能或合并前使用，用于验证工作成果是否符合要求
- **subagent-driven-development**: 当在当前会话中执行包含独立任务的实现计划时使用
- **systematic-debugging**: 遇到任何 bug、测试失败或异常行为时使用，在提出修复方案之前执行
- **test-driven-development**: 在实现任何功能或修复 bug 时使用，在编写实现代码之前
- **using-git-worktrees**: 当需要开始与当前工作区隔离的功能开发，或在执行实现计划之前使用——通过原生工具或 git worktree 回退机制确保隔离工作区存在
- **using-superpowers**: 在开始任何对话时使用——确立如何查找和使用技能，要求在任何响应（包括澄清性问题）之前调用 Skill 工具
- **verification-before-completion**: 在宣称工作完成、已修复或测试通过之前使用，在提交或创建 PR 之前——必须运行验证命令并确认输出后才能声称成功；始终用证据支撑断言
- **workflow-runner**: 在 Claude Code / OpenClaw / Cursor 中直接运行 agency-orchestrator YAML 工作流——无需 API key，使用当前会话的 LLM 作为执行引擎。当用户提供 .yaml 工作流文件或要求多角色协作完成任务时触发。
- **writing-plans**: 当你有规格说明或需求用于多步骤任务时使用，在动手写代码之前
- **writing-skills**: 当创建新技能、编辑现有技能或在部署前验证技能是否有效时使用

## 如何使用

当任务匹配某个 skill 时，使用 `Skill` 工具加载对应 skill 并严格遵循其流程。绝不要用 Read 工具读取 SKILL.md 文件。

如果你认为哪怕只有 1% 的可能性某个 skill 适用于你正在做的事情，你必须调用该 skill 检查。
<!-- superpowers-zh:end -->
