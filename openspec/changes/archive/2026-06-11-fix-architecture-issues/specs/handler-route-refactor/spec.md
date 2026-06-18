## ADDED Requirements

### Requirement: URL 前缀分组路由
`server/handler.py` 的 `do_GET` 方法 SHALL 按 URL 前缀将请求分发到独立处理方法。前缀分组 SHALL 为：`/api/micro/` → 微投资组合方法，`/api/covering/` → 覆盖设计方法，`/api/evaluate/` → EV 评估方法，`/api/compare/` → 对比方法，`/api/prediction-log` → 预测日志方法，其余 API 端点各自独立处理。

#### Scenario: 现有端点行为不变
- **WHEN** 执行 `python3 -m pytest tests/test_integration.py -v --tb=short`
- **THEN** 所有 14 个集成测试通过，响应内容与重构前完全一致

#### Scenario: 404 行为不变
- **WHEN** 请求不存在的路径如 `/api/nonexistent`
- **THEN** 返回 404 状态码

### Requirement: 共享参数解析
URL 查询参数解析 SHALL 提取为复用方法 `_parse_query_int(key, default)`，避免每个端点重复 `urllib.parse` + `int()` 转换逻辑。

#### Scenario: n 参数解析
- **WHEN** 端点需要解析 `?n=5` 参数
- **THEN** 调用 `_parse_query_int("n", 3)` 返回 `5`

#### Scenario: 缺失参数使用默认值
- **WHEN** 端点无对应查询参数
- **THEN** `_parse_query_int("n", 3)` 返回默认值 `3`

### Requirement: handler.py 行数减少
重构后 `handler.py` 总行数 SHALL 不超过 320 行（原 362 行）。

#### Scenario: 行数检查
- **WHEN** 执行 `wc -l server/handler.py`
- **THEN** 输出 ≤ 320
