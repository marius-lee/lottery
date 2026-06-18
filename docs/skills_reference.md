# Skills 参考手册

> 当前环境已安装的所有可用 skill 命令列表（2026-06-11）

---

## 一、superpowers-zh（20 个 skill）

以 `/` 前缀调用，专注中文开发工作流。

| 命令 | 说明 |
|------|------|
| `/brainstorming` | 任何创造性工作前必须使用——先探索意图、需求、设计 |
| `/chinese-code-review` | 中文 Review 话术模板（分级标注、反模式应对） |
| `/chinese-commit-conventions` | Conventional Commits 中文适配 + commitizen/changelog 配置 |
| `/chinese-documentation` | 中文文档排版规范（中英文空格、全半角标点） |
| `/chinese-git-workflow` | 国内 Git 平台配置（Gitee、Coding、极狐 GitLab） |
| `/dispatching-parallel-agents` | 2+ 个独立任务并行分派 |
| `/executing-plans` | 将书面计划在独立会话中执行 |
| `/finishing-a-development-branch` | 实现完成后的收尾（合并/PR/清理） |
| `/mcp-builder` | MCP 服务器构建方法论 |
| `/receiving-code-review` | 收到 Review 反馈后实施建议前使用 |
| `/requesting-code-review` | 完成任务/合并前请求审查 |
| `/subagent-driven-development` | 将实现计划分派给子 agent 执行 |
| `/systematic-debugging` | 遇到 Bug 时的规范化调试流程 |
| `/test-driven-development` | TDD 红-绿-重构循环 |
| `/using-git-worktrees` | 隔离工作区开发 |
| `/using-superpowers` | 开始对话时——确立如何查找和使用技能 |
| `/verification-before-completion` | 声称完成前必须运行验证命令 |
| `/workflow-runner` | 直接在会话中运行 YAML 工作流 |
| `/writing-plans` | 动手写代码前创建书面计划 |
| `/writing-skills` | 创建/编辑/验证技能 |

---

## 二、gstack（50+ 个 skill）

Garry Tan 出品的综合技能库，覆盖开发全流程。

### 开发与代码

| 命令 | 说明 |
|------|------|
| `/code-review` | 审查当前 diff（正确性 + 重构） |
| `/simplify` | 自动简化/优化代码 |
| `/tdd` | TDD 红-绿-重构 |
| `/spec` | 编写技术规格说明 |
| `/pair-agent` | 结对编程 agent |
| `/scaffold-exercises` | 搭建练习目录结构 |
| `/skillify` | 将代码转为 skill |
| `/init` | 初始化 CLAUDE.md |
| `/guard` | 代码守卫 |
| `/careful` | 谨慎模式 |

### 项目管理

| 命令 | 说明 |
|------|------|
| `/to-issues` | 方案→GitHub Issues 拆分 |
| `/to-prd` | 对话→PRD 发布 |
| `/triage` | Issue 分类管理 |
| `/retro` | 回顾会议 |
| `/investigate` | 问题调查 |
| `/learn` | 学习新概念 |
| `/teach` | 技能教学 |

### 设计

| 命令 | 说明 |
|------|------|
| `/design-an-interface` | 多方案接口设计 |
| `/design-consultation` | 设计咨询 |
| `/design-html` | HTML 设计 |
| `/design-review` | 设计审查 |
| `/design-shotgun` | 多角度暴力设计 |
| `/prototype` | 快速原型 |
| `/ubiquitous-language` | 提取 DDD 通用语言词汇表 |

### 审查

| 命令 | 说明 |
|------|------|
| `/review` | PR 审查（gstack 版） |
| `/security-review` | 安全审查 |
| `/devex-review` | 开发者体验审查 |
| `/plan-ceo-review` | CEO 维度审查 |
| `/plan-design-review` | 设计维度审查 |
| `/plan-devex-review` | DevEx 维度审查 |
| `/plan-eng-review` | 工程维度审查 |
| `/plan-tune` | 方案调优 |
| `/autoplan` | 自动方案 |

### 浏览器/自动化（基于 Playwright）

| 命令 | 说明 |
|------|------|
| `/browse` | 浏览网页 |
| `/scrape` | 爬取网页内容 |
| `/connect-chrome` | 连接 Chrome 浏览器 |
| `/open-gstack-browser` | 打开 gstack 浏览器 |
| `/setup-browser-cookies` | 设置浏览器 Cookie |

### 文档与写作

| 命令 | 说明 |
|------|------|
| `/handoff` | 生成交接文档 |
| `/document-generate` | 生成文档 |
| `/document-release` | 发布文档 |
| `/edit-article` | 编辑文章 |
| `/writing-beats` | 逐段写作 |
| `/writing-fragments` | 碎片式思维采集 |
| `/writing-shape` | 将素材打磨成文章 |
| `/make-pdf` | 生成 PDF |

### 质量

| 命令 | 说明 |
|------|------|
| `/qa` | 质量保证全流程 |
| `/qa-only` | 仅 QA 测试 |
| `/diagnose` | Bug 诊断循环 |
| `/canary` | 金丝雀测试 |
| `/benchmark` | 基准测试 |
| `/benchmark-models` | 多模型基准测试 |
| `/verify` | 验证改动是否生效 |

### 基础设施

| 命令 | 说明 |
|------|------|
| `/setup-pre-commit` | 配置 Husky pre-commit hooks |
| `/setup-deploy` | 部署配置 |
| `/setup-gbrain` | gbrain 设置 |
| `/sync-gbrain` | 同步 gbrain |
| `/improve-codebase-architecture` | 代码架构改进 |
| `/request-refactor-plan` | Refactor 计划→GitHub Issue |
| `/migrate-to-shoehorn` | 迁移 Shoehorn 类型断言 |
| `/fewer-permission-prompts` | 减少权限弹窗 |

### 辅助工具

| 命令 | 说明 |
|------|------|
| `/caveman` | 超精简回复模式，省 Token |
| `/grill-me` | 被盘问式方案检验 |
| `/grill-with-docs` | 结合领域文档的方案考验 |
| `/deep-research` | 深度研究（全网搜索+溯源验证） |
| `/find-skills` | 搜索发现技能 |
| `/skills-discovery` | 技能发现与安装 |
| `/obsidian-vault` | Obsidian 笔记管理 |
| `/zoom-out` | 宏观视角 |
| `/context-save` | 上下文保存 |
| `/context-restore` | 上下文恢复 |
| `/freeze` | 冻结 |
| `/unfreeze` | 解冻 |
| `/claude-api` | Claude API 参考 |

### 运维

| 命令 | 说明 |
|------|------|
| `/run` | 启动并驱动项目应用 |
| `/update-config` | 更新 settings.json 配置 |
| `/keybindings-help` | 键盘快捷键自定义 |
| `/loop` | 定时循环执行 |
| `/gstack-upgrade` | 升级 gstack |
| `/office-hours` | Garry Tan 办公时间 |
| `/health` | 系统健康检查 |
| `/land-and-deploy` | 上线部署 |
| `/landing-report` | 上线报告 |

### iOS 相关

| 命令 | 说明 |
|------|------|
| `/ios-clean` | iOS 清理 |
| `/ios-design-review` | iOS 设计审查 |
| `/ios-fix` | iOS 修复 |
| `/ios-qa` | iOS QA |
| `/ios-sync` | iOS 同步 |

### 其他

| 命令 | 说明 |
|------|------|
| `/codex` | Codex 集成 |
| `/ship` | 发布上线 |
| `/cso` | CSO 相关 |

---

## 三、Anthropic 官方

| 命令 | 说明 |
|------|------|
| `/frontend-design` | 前端设计（527.7K 安装量，Anthropic 官方出品） |
| `/ui-ux-pro-max` | UI/UX Pro Max — 全栈 UI/UX 设计（209.7K 安装量，nextlevelbuilder） |
| `/notebooklm` | NotebookLM — 借助 Google NotebookLM 能力进行文档分析/播客生成（5.4K，teng-lin） |

---

## 四、自定义 skill

| 命令 | 说明 |
|------|------|
| `/full-review` | 全量代码审查（走 CLAUDE.md 阶段门禁，lottery 项目专用） |

---

## 四、使用方式

任意 skill 直接输入命令即可：`/browse`、`/handoff`、`/deep-research`、`/full-review`。

系统会自动匹配 Skill 工具并加载对应 skill 的完整指令。
