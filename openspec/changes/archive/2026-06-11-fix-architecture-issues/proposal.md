## Why

架构审计发现 5 类问题：1 个测试因重构后遗留 import 而失败；`ml/_deprecated/` 内 ~200KB 死代码仍可 import；`ssq_constants.py` 含废弃策略常量；`handler.py` URL 路由用 if-else 字符串匹配；前端分析权重为无来源魔法数字。这些问题不阻塞功能，但增加维护成本和认知负载，违反零冗余铁律。

## What Changes

- 修复 `test_weighted_blue_choice`：将 import `_weighted_blue_choice` 改为 `_weighted_choice`，匹配当前 API
- 清理 `ml/_deprecated/` 中的 `__init__.py`，使其不再是可导入包
- 从 `ssq_constants.py` 移除废弃策略常量（COLD_START_WEIGHTS、WEIGHT_MIN/MAX、FAMILY_CAP、EWMA_DECAY 等）
- 前端 `analysis.js` 综合权重系数改为可溯源常量（标注来源：频率/遗漏/重号/邻号/012路/同尾的权重分配依据）
- handler.py 路由重构：URL 前缀分组 + 共享参数解析提取

## Capabilities

### New Capabilities
- `dead-code-cleanup`: 清理 ml/_deprecated/ 可导入性 + ssq_constants.py 废弃常量
- `test-fix-blue-choice`: 修复 _weighted_blue_choice → _weighted_choice 测试 import
- `frontend-weight-sourcing`: 前端 analysis.js 权重系数标注来源
- `handler-route-refactor`: handler.py URL 路由分组重构

### Modified Capabilities
<!-- 无现有 spec 需要修改 -->

## Impact

- `tests/test_core_generation.py`: import 修复
- `ml/_deprecated/__init__.py`: 删除或清空
- `ml/ssq_constants.py`: 移除 4 组废弃常量
- `static/js/ui/analysis.js`: 权重系数标注来源
- `server/handler.py`: 路由分组重构（不改变 API 行为）
