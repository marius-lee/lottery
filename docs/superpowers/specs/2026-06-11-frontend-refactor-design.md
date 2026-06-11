# 前端重构：死代码清理 + Observer 收尾

## 背景

2026-05 的前端拆分（index.html → ES Modules）完成了大部分模块化工作，遗留了两个问题：
1. 旧策略系统的死代码（`static/js/deprecated/`）一直未清理
2. Observer 模式不完整——`panels.js` 仍直接 import 并手动调用各面板的 render 函数

本次重构在 Phase 2（前端 JS 模块化）基础上做清理收尾。

## Phase A：死代码清理

### 范围

| 文件/目录 | 行数 | 处理 |
|-----------|------|------|
| `static/js/deprecated/` (backtest.js / consensus.js / generator.js / weights.js / filter/ / strategy/) | ~560 + 19 策略文件 | 归档 → 删除 |
| `static/js/constants.js` (游戏规则 / 权重 / 过滤 / 混沌 / ML 融合等常量) | 143 行 | 删除 |
| `static/js/utils.js` 中 pickOne / pickBalls / normDict | 36 行 | 删除 |
| `static/css/style.css` 中 12 个死类 | 26 行 | 删除 |

### 验证

- 无活跃模块 import 已删除的文件
- 34/35 测试通过（1 失败为预先存在的 `test_weighted_blue_choice` 问题）
- 服务启动正常

### 归档

`docs/deprecated-js-backup/`（116K）

## Phase B：Observer 收尾

### 问题

重构前 `panels.js` 是面板切换的中枢，需 import 各面板模块并手动调用其渲染函数：

```
panels.js → import { renderOmission } → togglePanel('omission') → renderOmission()
panels.js → import { renderAdvancedAnalysis, switchAnalysisTab } → togglePanel('analysis')
```

问题：新增面板需改 panels.js，模块间隐含耦合。

### 方案

各面板模块自管理生命周期——`panels.js` 只做 DOM 切换，面板模块独立订阅 `panel-shown` 和 `data-changed` 事件。

**panels.js 重构为纯 DOM 操作：**

```
togglePanel(name) → panel.classList.toggle('show')
                 → panel.dispatchEvent(new CustomEvent('panel-shown'))
```

**各面板模块独立注册监听：**

```
omission.js:
  omissionPanel.addEventListener('panel-shown', renderOmission)
  subscribe('data-changed', () => { if visible → renderOmission })

analysis.js:
  analysisPanel.addEventListener('panel-shown', renderAdvancedAnalysis)
  subscribe('data-changed', () => { if visible → renderAdvancedAnalysis })

recommend.js:
  recommendPanel.addEventListener('panel-shown', refreshRecommend)
  subscribe('data-changed', () => { if visible → refreshRecommend })

review.js:
  reviewPanel.addEventListener('panel-shown', refreshReviewPanel)
  subscribe('data-changed', () => { if visible → refreshReviewPanel })
```

compare.js 保持不变——它依赖用户明确点击「对比最新开奖」，不跟随数据自动刷新。

### 架构图

```
用户点击面板标签 → panels.js: togglePanel()
                    ↓
                  panel.dispatchEvent('panel-shown')
                    ↓
                  [omission|analysis|recommend|review].js → 渲染

用户点「更新数据」 → store.updateData()
                    ↓
                  notify('data-changed')
                    ↓
                  app.js: renderPlaceholders() + resetHistoryPanels()
                  omission.js: if 面板可见 → renderOmission()
                  analysis.js:  if 面板可见 → renderAdvancedAnalysis()
                  recommend.js: if 面板可见 → refreshRecommend()
                  review.js:    if 面板可见 → refreshReviewPanel()
```

### 变更文件

| 文件 | 操作 |
|------|------|
| `static/js/ui/panels.js` | 重构：移除 import renderOmission/analysis；export { switchAnalysisTab } 移除；新增 panel.dispatchEvent |
| `static/js/ui/omission.js` | 新增：panel-shown 事件监听 |
| `static/js/ui/analysis.js` | 新增：panel-shown 事件监听 |
| `static/js/ui/recommend.js` | 新增：panel-shown + data-changed 监听；import store, subscribe |
| `static/js/ui/review.js` | 新增：panel-shown + data-changed 监听；import store, subscribe |
| `static/js/app.js` | 精简：移除 4 条未用 import；新增 import './ui/omission.js' 副作用导入 |

## 验收

- 34/35 测试通过
- JS 文件数 23 个，总计 ~1396 行
- CSS 从 235 行精简到 207 行
- 无活跃代码引用已删除的文件
