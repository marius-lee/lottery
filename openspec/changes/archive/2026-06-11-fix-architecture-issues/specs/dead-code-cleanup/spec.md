## ADDED Requirements

### Requirement: _deprecated 包不可导入
`ml/_deprecated/` 目录 SHALL 不再作为 Python 包可被 `import ml._deprecated` 导入。其 `__init__.py` 文件 SHALL 被删除。

#### Scenario: import ml._deprecated 失败
- **WHEN** 执行 `from ml._deprecated import any_module`
- **THEN** Python 抛出 `ModuleNotFoundError: No module named 'ml._deprecated'`

#### Scenario: 测试更新为直接路径加载
- **WHEN** `test_deprecated_import` 需要验证废弃模块仍存在
- **THEN** 测试使用 `importlib.util` 直接按文件路径加载 `.py` 文件，而非包导入

### Requirement: ssq_constants.py 零废弃常量
`ml/ssq_constants.py` SHALL 仅包含被活跃模块（`micro_portfolio.py`, `covering_design.py`, `prize_evaluator.py`）引用的常量。废弃策略常量 SHALL 被移除。

#### Scenario: COLD_START_WEIGHTS 已移除
- **WHEN** 检查 `ml/ssq_constants.py` 内容
- **THEN** 文件中不含 `COLD_START_WEIGHTS`, `COLD_START_N_SAMPLES`, `WEIGHT_MIN`, `WEIGHT_MAX`, `FAMILY_CAP`, `EWMA_DECAY`

#### Scenario: 活跃常量保留
- **WHEN** `micro_portfolio.py` import `TICKET_PRICE, RANDOM_SINGLE_EV` from `ssq_constants`
- **THEN** import 成功，值不变

### Requirement: 无活跃代码引用废弃常量
所有活跃模块（`ml/`, `server/`）SHALL 不 import 废弃常量。

#### Scenario: grep 确认零引用
- **WHEN** 在 `ml/`（排除 `_deprecated/`）和 `server/` 目录中 grep `COLD_START_WEIGHTS|WEIGHT_MIN|FAMILY_CAP|EWMA_DECAY`
- **THEN** 没有任何匹配结果
