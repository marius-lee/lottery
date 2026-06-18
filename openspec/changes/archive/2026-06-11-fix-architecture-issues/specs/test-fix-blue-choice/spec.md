## ADDED Requirements

### Requirement: test_weighted_blue_choice 使用 _weighted_choice
`tests/test_core_generation.py` 中的 `test_weighted_blue_choice` SHALL 使用 `_weighted_choice` 函数（含三个参数：weights, candidates, rng）替代不存在的 `_weighted_blue_choice`。

#### Scenario: 测试通过
- **WHEN** 执行 `python3 -m pytest tests/test_core_generation.py::TestBlueWeights::test_weighted_blue_choice -v`
- **THEN** 测试通过，无 ImportError

#### Scenario: 全量测试仅此一处修复
- **WHEN** 执行 `python3 -m pytest tests/ -v --tb=short`
- **THEN** 35 passed, 0 failed

### Requirement: 蓝球选择逻辑一致
`_weighted_choice(weights, candidates)` 的蓝球候选列表 SHALL 为 `list(range(1, 17))`（全部 16 个蓝球），rng SHALL 使用默认 `random` 模块。行为与原 `_weighted_blue_choice(weights)` 等价。

#### Scenario: 蓝球范围校验
- **WHEN** 连续调用 `_weighted_choice(weights, list(range(1, 17)), random)` 50 次
- **THEN** 每次返回值为 1-16 范围内的整数
