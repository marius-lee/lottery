---
name: no-made-up-numbers
description: 🚨 最高铁律：代码中出现的任何数值，必须能说出来源依据。随口写的立即修正。
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7aee4c77-e21e-4c27-961a-5d582b09d7f9
---

## 铁律

看到代码中任何数值（系数、阈值、窗口、延迟、参数、epochs、split比例），立即自问：

**"这个数字从哪来的？有什么依据？"**

只有4种合法来源:
1. 数学恒等式 (e.g., 1/16, 6×6/33)
2. 文献/标准 (e.g., RiskMetrics 0.94, Feigenbaum 3.5699)
3. 数据校准 (e.g., 2000期95%CI = [59,141])
4. 用户明确确认

没有以上4种来源 → 承认是随手写的 → 立即查找真实依据修改。

**不是"建一张表"然后忘掉。是每次碰到数字都要问。这是行为规则，不是文档。**

Why: 2026-06-05 审计发现代码中65+个随手写数值。参数注册表建了没用——因为规则本身没进脑子。

How to apply: 每次 Edit/Write 前检查改动中是否有数字。有 → 先说依据 → 再改代码。没有依据 → 先说"这个数字随手写的，需要查证" → 查完再改。

链接: [[stop_code_first]] [[think_before_coding]] [[parameter_registry_enforcement]]
