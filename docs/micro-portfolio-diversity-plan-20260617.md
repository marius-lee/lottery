# 微投资组合注间多样性优化 — 3层实现方案

## Context

当前 `generate_tickets()` 从有效池随机采样 N 注，无注间相关性控制。两注可能重叠 4 个号，相当于 ¥4 买了 ¥2 的覆盖。需要添加注间分散约束和显式覆盖目标。

## 实现顺序

Tier 1 → Tier 2 → Tier 3，每层独立实现、测试验证后再进下一层。

---

## Tier 1: 贪婪分散 — max_overlap 硬约束

**改动量**: ~30 行 | **文件**: 4 个

### 核心思路
在采样循环中加一条检查：候选注与任意已选注共享红球数 ≤ max_overlap（默认 None = 不启用）。

### 具体改动

**1. `ml/micro_portfolio.py`**
- `generate_tickets(n, soft, luck_mode, max_overlap=None)` — 新参数
- 第 472 行后（`if reds in used_reds: continue`），第 474 行前（`# blend 模式`）插入:
  ```python
  if max_overlap is not None and tickets:
      if any(len(set(reds) & set(t["reds"])) > max_overlap for t in tickets):
          continue
  ```
- `_generate_luck_tickets(n, max_overlap=None)` — 同位置插入（第 306 行后）
- `_generate_fallback_tickets(n, luck_mode, max_overlap=None)` — 同位置插入（第 371 行后）
- 三处 `_generate_luck_tickets()` / `_generate_fallback_tickets()` 调用传入 `max_overlap`

**2. `server/ml_bridge.py`** — `micro_3_tickets()` 加 `max_overlap=None` 参数并转发

**3. `server/handler.py`** — `_handle_micro_get()` 解析 `?max_overlap=N`，用 -1 作 sentinel（允许 max_overlap=0）

**4. 前端** — checkbox "分散红球" → `store.useDiversity` → API 追加 `&max_overlap=2`

### 验证
- 现有 35 测试全绿（默认 max_overlap=None 等于零改动）
- 新测试：max_overlap=0 时所有注对共享红球 = 0；max_overlap=2 时 ≤ 2
- 极端测试：n=10, max_overlap=0 不崩溃

---

## Tier 2: 贪心选注 — 最大化最小 Jaccard 距离

**改动量**: ~70 行 | **文件**: 4 个

### 核心思路
从有效池随机抽 1000 候选 → 贪心选 N 注，每步选与已选集合的 min Jaccard 距离最大的候选。

### 新增函数（`ml/micro_portfolio.py`）

**`_jaccard_distance(a, b)`**: `1 - |a∩b| / (12 - |a∩b|)`
- 6 元素集合，并集 = 12 - 交集
- 返回值：1.0（完全不相交）→ 0.0（完全相同）

**`_build_candidate_pool(pool_size, valid_reds, n_combos, exclude, used_reds, rng)`**:
- 从 `_valid_reds` 随机采样 pool_size 个未排除/未使用的组合
- 返回 `[(idx, reds_tuple), ...]`

**`_greedy_diverse_tickets(n, valid_reds, n_combos, exclude, pool_size, blue_weights, used_blues, rng)`**:
- 构建候选池 → 随机选第 1 注 → 贪心选后续注（max-min Jaccard）
- 分配蓝球 → 返回 `(tickets, used_idx, used_reds, used_blues)`
- 候选不足时返回 None（调用方回退到随机采样）

### 集成方式

`generate_tickets()` 加 `diversity_mode=None` 参数：
- `diversity_mode='greedy'` → 先走 `_greedy_diverse_tickets()`
- 贪心产不足 n 注 → 剩余走正常采样循环
- 默认 None → 完全不变

### 传递链
`handler.py` 解析 `?div=1` → `ml_bridge.py` → `generate_tickets(diversity_mode='greedy')`

### 验证
- 贪心选出的 min Jaccard ≥ 随机选出的 min Jaccard
- 贪心产出的票数与请求一致
- 候选池耗尽时优雅降级

---

## Tier 3: 覆盖设计集成 — Steiner t-wise + 蓝球分配

**改动量**: ~100 行 | **文件**: 4 个

### 核心思路
用 `covering_design.py` 的 SA 引擎做红球覆盖，再分配蓝球。形成独立生成路径（不替换主路径）。

### 新增函数（`ml/micro_portfolio.py`）

**`generate_tickets_covering(n, hot_numbers, t=4, max_overlap=None)`**:
1. 调 `build_covering_tickets(hot_numbers, t, target_tickets=n)` 获取红球覆盖集
2. 可选 max_overlap 过滤
3. `_pick_unique_blue()` 分配蓝球（同主路径）
4. 返回标准格式 + `covering` 元数据（v, t, coverage_pct, guarantee）

### 新增端点

`GET /api/covering-diverse?v=15&t=4&n=6&max_overlap=2`

Bridge: `generate_covering_diverse(v, t, n, max_overlap)` — 从 DB 算热号 → 调 `generate_tickets_covering()`

### 为何独立函数而非 mode 参数
- 覆盖设计输入是热号列表 + t 值，不是 pool 采样
- luck_mode 不适用
- 返回值含 coverage_pct，随机采样没有
- 独立函数/端点隔离清晰

### 验证
- 返回票数 = n，每票 6+1
- 蓝球注间不重复
- hot_numbers < 6 时返回 ok=False
- 集成测试覆盖新端点

---

## 数据流总览

```
用户 → 前端 toggle → query params
  ├─ ?max_overlap=2        → Tier 1: 采样循环内约束检查
  ├─ ?div=1                → Tier 2: 贪心选注
  └─ /api/covering-diverse → Tier 3: 覆盖设计 + 蓝球分配
              ↓
         handler.py → ml_bridge.py → micro_portfolio.py
```

## 要修改的关键文件

| 文件 | Tier 1 | Tier 2 | Tier 3 |
|------|--------|--------|--------|
| `ml/micro_portfolio.py` | 4 处插入 + 3 签名 | 3 新函数 + 1 新路径 | 1 新函数 |
| `server/ml_bridge.py` | 1 参数 | 1 参数 | 1 新函数 |
| `server/handler.py` | 参数解析 | 参数解析 | 1 新路由 |
| `static/js/ui/draw.js` | 1 toggle + query | — | — |
| `tests/test_core_generation.py` | 4 测试 | 2 测试 | — |
| `tests/test_covering_design.py` | — | — | 3 测试 |
| `tests/test_integration.py` | — | — | 1 测试 |

## 验证

每层完成后运行 `python3 -m pytest tests/ -v --tb=short`，确保所有已有测试 + 新测试通过。最终全量 35 + 10 = 45 测试全绿。
