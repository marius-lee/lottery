---
name: confirm-vs-implement
description: 🚨 铁律：「确认」≠「立刻写代码」。确认后必须先出详细方案，等「实现」指令再动手
metadata: 
  node_type: memory
  type: feedback
  priority: highest
  originSessionId: 6604f2f4-f454-49c0-9b38-aee63fc9d473
---

🚨 铁律：用户说「确认」≠ 立刻开始写代码。

## 正确流程

```
用户提需求 → AI出方案 → 用户「确认」→ AI出详细方案(算法/API/预期) → 讨论 → 用户说「实现」/「开始写」→ AI写代码
```

## 错误示范（今天屡犯）

```
用户说「确认」→ AI立刻Edit/Write → 跳过了方案讨论环节 → 改完又改 → 浪费时间
```

## 详细方案应包含

1. 具体算法设计（函数名、输入输出）
2. 数据流（前后端如何交互）
3. 预期效果（什么情况下算成功）
4. 对目标（中一等奖）的贡献预估

## 违反处置

用户指出 → 立即停止 → 复述方案 → 等用户明确说「实现」再动手

## 为什么

2026-06-08 session: 用户说「确认」8次，AI 8次直接写代码。用户需纠正：确认≠实现。确认是认可方向，需进一步讨论方案细节后才能动手。

链接: [[stop_code_first]] [[think_before_coding]] [[pre-action-checklist]]
