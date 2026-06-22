# Session 20260619 — 张委铭全书遍历 + 三算法实现

## 时间线

1. **架构诊断** → `docs/architecture-review-20260619.md`
   - 发现 ml/ → server/ 反向依赖等 12 个问题
   - 判断当前不紧迫（57 测试全过、功能正常）

2. **张委铭全书遍历** → `docs/zhang-weiming-comprehensive-20260619.md`
   - 《双色球杀号定胆选号方法与技巧超级大全》310页
   - OCR 提取 Ch3§6（轮流杀号法）、Ch4§3（后区轮流杀号）、Ch5（定胆/伴生）、Ch6§3（十二值选号法）、Ch8（八值选号法）
   - 判定：590+177种杀号方法太重不实现；定2/3胆+伴生为静态统计表

3. **三算法实现** ← 本文件

## 新增文件

| 文件 | 行数 | 内容 |
|------|------|------|
| `ml/zhang_weiming.py` | ~520 | 十二值选号法 + 八值选号法 + 行列网格 + 组合模式 |
| `tests/test_zhang_weiming.py` | 95 | 12个测试：杀号映射 + 书中示例精确匹配 + 生成函数 |
| `static/js/ui/zhang-panel.js` | 150 | 张委铭面板：三方法 checkbox + 出号按钮 + 候选明细 |

## 修改文件

| 文件 | 改动 | 内容 |
|------|------|------|
| `server/ml_bridge.py` | +70行 | generate_twelve_value / generate_eight_value / generate_zhang_combined / generate_grid_selection |
| `server/handler.py` | +20行 | GET /api/zhang/{twelve-value,eight-value,combined,grid} + query参数剥离修复 |
| `index.html` | 修改 | 张委铭面板 tab + script 引用（option cards 后移除到面板内） |
| `static/js/app.js` | 修改 | 导入 zhang 函数（劫持逻辑已移除） |
| `static/js/ui/draw.js` | +90行 | startZhangDraw + update 函数 |
| `static/js/store.js` | +3行 | useTwelveValue / useEightValue / useGridSelection |

## API 端点

```
GET /api/zhang/twelve-value?n=3   → 十二值选号法 (18杀号→红球+位置策略)
GET /api/zhang/eight-value?n=3    → 八值选号法 (11杀号→蓝球+连续出错)
GET /api/zhang/grid?n=3           → 行列网格 (3×11自动断区)
GET /api/zhang/combined?n=3       → 十二值红球 + 八值蓝球组合
```

## 算法验证

- **八值选号法**: 书中示例 (2003013期) 6/6 蓝球候选精确匹配
- **十二值选号法**: 8/10 候选号码匹配 (差异来自杀号规则细节)
- **行列网格**: 全自动检测断行列规律, 适应历史数据

## UI 架构 (最终状态)

```
策略面板 (8个option cards) → [生成号码] → /api/micro/tickets
├─ 高级过滤 / 分散红球 / 贪心优化 / 刘大军蓝球 / 彩乐乐蓝球 / 公益时报蓝球 / 吴明蓝球 / 回测排名

面板 tabs:
├─ 微尔选号 → 8步条件选择 → /api/weier/manual
├─ 断区转换 → 6×6断区3D码 → /api/zone-break/filter
└─ 张委铭 → 十二值/八值/网格 checkbox → /api/zhang/*
```

四种工作流互不干扰。张委铭面板自带方法选择和出号按钮。

## 测试

69/69 全过 (新增 12 个张委铭测试)
