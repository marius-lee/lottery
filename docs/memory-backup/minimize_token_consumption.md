---
name: minimize_token_consumption
description: 🚨 铁律：尽可能节省 token 消耗，控制 API 成本
metadata: 
  node_type: memory
  type: feedback
  originSessionId: c699f55a-2a4b-4516-8ec5-d8e3f6c5d7e8
---

🚨 铁律：尽可能节省 token 消耗，控制 API 成本。

**Why:** API 调用按 token 计费，每次对话都有成本。10k token 约 $0.15（按 Claude Opus 计），无节制使用会迅速累积费用。

**How to apply:**
- 写代码优先高效简洁，减少无用注释、无用空格、多余换行
- 输出直接给结论 + 关键数据，不做冗长叙述
- 读文件只读需要的行（offset/limit），不整文件读
- 多操作合并到一个 tool call batch 中
- 不在回复中重复工具返回的已知内容
- 排除无关细节，只输出决策相关信息
- CSS/JS 压缩风格：紧凑格式，合并选择器，减少冗余声明

**Related:** [[iron-rules]] [[hardware_ceiling_no_upgrade]]
