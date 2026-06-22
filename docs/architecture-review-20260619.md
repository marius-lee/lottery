# 架构诊断报告 2026-06-19

## 核心问题: ml/ 层反向依赖 server/

`ml/` 以"纯算法模块"自称，但三个活跃模块都直接导入 `server/db`：

| 文件 | import server.db 次数 |
|------|---------------------|
| `ml/micro_portfolio.py` | 12处 |
| `ml/weier_filter.py` | 2处 |
| `ml/zone_break.py` | 1处 |

**后果**: 算法模块无法脱离数据库独立测试；`zone_break.py`/`weier_filter.py` 被迫访问 `mp._valid_reds` 私有状态。

## 🔴 致命

1. **ml/ → server/ 反向依赖** — `ml/` 函数应接收 data 参数，由 `ml_bridge.py` 负责从 db 取数
2. **跨模块私有状态访问** — `zone_break.py` 和 `weier_filter.py` 直接访问 `mp._valid_reds`, `mp._build_pool()`, `mp._past_count`, `mp._blue_freq_weights()`, `mp._pick_unique_blue()`

## 🟠 高

3. **五期断蓝双重施加** — 当 `liu_blue=True` 时 `_five_period_boost()` 和 `_liu_dajun_blue()` 各施加一次 0.01 mask，结果 0.0001
4. **池构建/验证逻辑重复三份** — `micro_portfolio.py`, `zone_break.py`, `weier_filter.py` 各自包含相同的 try/except/build 代码块
5. **非模块脚本污染全局** — `weier-panel.js` 和 `zone-break.js` 非 module，无法 tree-shaking，预加载数据

## 🟡 中

6. **路由不精确** — `/api/weier/generate` 无显式路由，依赖 `/api/weier/conditions` 的提前检查
7. **`_pattern_blue_boost()` 冗余** — 与独立 author flag 路径功能等价但走不同代码路径
8. **`handler.py` 业务逻辑过长** — `_handle_compare_post` 含 ~100 行在 handler 层

## 🔵 低

9. `weier-panel.js` 页面初始化即预加载 conditions（用户可能从不打开微尔面板）
10. `_propagate_constraints` 就地修改 dict
11. `server/recommend.py` 每次请求重新计算，无缓存
12. 测试覆盖: 未覆盖 weier 手动模式

## 测试状态

全部 57 个测试通过 (含 15 个集成测试)。

## 最小修正方案

1. `micro_portfolio.py` 增公开函数 `get_valid_pool(data)` → 统一入口
2. `zone_break.py` / `weier_filter.py` 消去 `from ml.micro_portfolio import _*`
3. `ml/` 层不再 import `server.db`，数据全部通过参数传入
