---
name: ten-minute-stop-rule
description: Hard stop after 10 minutes of debugging without result — search for solutions instead
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e4234c4c-6834-4636-903e-30f86502da40
---

**铁律：任何 bug 修复或问题排查，10 分钟内没出结果，立即停止当前操作，上网搜索方案。**

执行机制：
1. 动手前先看表/记时间
2. 10 分钟一到，无论进展如何，立即停
3. 用 WebSearch 搜索：症状关键词 + 平台名，时间跨度覆盖 2016-2026（涵盖量化平台成熟期的完整积累）
4. 对比至少 2 个来源的方案后再动手
5. 禁止继续加日志盲调、禁止反复重启等待

**Why:** 5分钟对需要跑管线复现的排查偏紧（如数据同步、模型训练等天然耗时操作），延长到10分钟给足排查空间。但10分钟无结果意味着方向不对，必须切换策略。搜索时间范围扩大到十年，因为量化系统架构设计、因子模型等核心知识十年间变化不大，很多最佳实践来自 2016-2019 的 Quantopian/Zipline/WorldQuant 时代。

**How to apply:** 把这条当代码的 `assert` 语句——到点就触发，无例外。
