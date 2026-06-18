# 双色球项目重构方案

## 当前问题

| 问题 | 详情 |
|------|------|
| 单文件巨型 | `index.html` 3010行，CSS+HTML+JS 全混在一个文件 |
| 不可测试 | 策略函数无法独立测试，依赖全局DATA |
| 难以扩展 | 加一个策略需要改巨型文件 |
| app.py臃肿 | 1267行，路由/DB/抓取/推荐全耦合 |
| 无模块边界 | 任何函数能访问任何全局变量 |

## 目标架构

```
lottery/
├── index.html                    # HTML shell (~100行)
├── app.py                        # 入口 (~30行)
├── server/
│   ├── __init__.py
│   ├── db.py                     # 数据库层 (Repository Pattern)
│   ├── fetcher.py                # 中彩网抓取 (Facade)
│   ├── handler.py                # HTTP路由分发
│   ├── recommend.py              # 推荐引擎
│   └── ml_bridge.py              # ML门面 (Facade Pattern)
├── static/
│   ├── css/
│   │   └── style.css             # 全部样式
│   └── js/
│       ├── app.js                # 入口+事件绑定 (Observer)
│       ├── data.js               # 数据加载+缓存 (Singleton)
│       ├── analysis/             # 统计分析模块 (14个纯函数)
│       │   ├── frequency.js
│       │   ├── omission.js
│       │   ├── repeat.js
│       │   ├── neighbor.js
│       │   ├── route012.js
│       │   ├── ac_span.js
│       │   ├── primes.js
│       │   ├── dragon_phoenix.js
│       │   ├── same_tail.js
│       │   └── similar.js
│       ├── weights.js            # 增强权重系统
│       ├── filter/               # 过滤器链 (Chain of Responsibility)
│       │   ├── hard.js           # 11条硬规则
│       │   ├── soft.js           # 软评分
│       │   └── index.js          # 组合过滤器
│       ├── strategy/             # 策略模式 (Strategy Pattern)
│       │   ├── base.js           # 抽象基类 (Template Method)
│       │   ├── registry.js       # 策略注册表 (Factory)
│       │   ├── freq.js
│       │   ├── omission.js
│       │   ├── trend.js
│       │   ├── uniform.js
│       │   ├── interval.js
│       │   ├── golden_ratio.js
│       │   ├── same_tail.js
│       │   ├── similar_period.js
│       │   ├── position.js
│       │   ├── cooccur.js
│       │   ├── markov_blue.js
│       │   ├── temperature.js
│       │   ├── chaos.js
│       │   ├── exponential.js
│       │   └── ml_ensemble.js
│       ├── consensus.js          # 加权投票共识
│       ├── backtest.js           # 滚动回测
│       ├── generator.js          # 增强生成器
│       ├── ui/                   # UI渲染 (Observer)
│       │   ├── draw.js
│       │   ├── panels.js
│       │   ├── analysis.js
│       │   ├── omission.js
│       │   ├── compare.js
│       │   ├── recommend.js
│       │   └── review.js
│       ├── chart.js              # Canvas走势图
│       └── audio.js              # 音效
└── ml/                           # (已有，不动)
    ├── xgb_predictor.py
    └── lstm_predictor.py
```

## 应用的7种设计模式

### 1. Strategy Pattern（策略模式）— 核心
```
Strategy (base.js)
├── FreqStrategy
├── OmissionStrategy
├── TrendStrategy
├── UniformStrategy
├── IntervalStrategy
├── GoldenRatioStrategy
├── SameTailStrategy
├── SimilarPeriodStrategy
├── PositionStrategy
├── CooccurStrategy
├── MarkovBlueStrategy
├── TemperatureStrategy
├── ChaosStrategy
├── ExponentialStrategy
└── MLEnsembleStrategy

每个策略实现: predict() → { reds: [], blue: number, name: string }
```

### 2. Template Method（模板方法）
```js
class Strategy {
  predict() {
    const redW = this.buildRedWeights();  // 子类实现
    const reds = this.pickReds(redW);      // 基类实现
    const blueW = this.buildBlueWeights(); // 子类实现
    const blue = this.pickBlue(blueW);     // 基类实现
    return { name: this.name, reds, blue };
  }
  // 基类提供 pickReds(), pickBlue(), weightedPick()
  // 子类只需实现 buildRedWeights(), buildBlueWeights()
}
```

### 3. Factory Method（工厂模式）
```js
// registry.js
class StrategyRegistry {
  static register(name, StrategyClass) { ... }
  static create(name) { ... }
  static runAll() { ... }  // 返回所有策略实例的预测结果
}
```

### 4. Chain of Responsibility（责任链）— 过滤器
```js
hardFilter(reds, blue) → softFilter(reds, blue) → enhancedFilter(reds, blue)
每层可独立拒绝，下游只处理通过上游的号码
```

### 5. Observer Pattern（观察者）— 数据→UI
```js
class DataStore {
  subscribe(fn) { this.listeners.push(fn); }
  notify() { this.listeners.forEach(fn => fn()); }
  updateData(newData) { this.data = newData; this.notify(); }
}
// UI组件订阅: store.subscribe(renderOmission)
// 数据更新时所有面板自动刷新
```

### 6. Facade Pattern（外观）— ML子系统
```js
// ml_bridge.py
class MLFacade:
    def predict_ensemble(self, data):
        xgb = self.get_xgb()
        lstm = self.get_lstm()
        return blend(xgb.predict(data), lstm.predict(data))
    # 客户端只需调用 predict_ensemble()，不关心内部实现
```

### 7. Repository Pattern（仓库）— 数据访问
```py
# db.py — 所有SQL操作封装在Repository类中
class DrawRepository:
    def upsert(self, rows): ...
    def load_all(self, limit): ...
    def count(self): ...
```

## 实施步骤（分3阶段，每阶段可独立交付）

### 阶段1: Python后端拆分（低风险，不影响前端）
```
app.py → server/db.py + server/fetcher.py + server/handler.py + server/recommend.py + server/ml_bridge.py
```
- 提取DB函数到 `db.py`
- 提取抓取逻辑到 `fetcher.py`  
- Handler保持功能不变，调用各模块
- 把 `/api/recommend` 逻辑提取到 `recommend.py`

### 阶段2: 前端JS模块化（ES Modules）
```
index.html → static/js/* (20+个ES模块)
```
- CSS提取到 `style.css`
- JS按功能拆成ES模块
- `index.html` 用 `<script type="module" src="app.js">`
- 14个策略各一个文件，继承 `StrategyBase`

### 阶段3: Observer重构UI刷新
- DataStore集中管理状态
- UI组件订阅数据变化
- 消除手动调用 `renderXxx()` 的散落代码

## 关键决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 模块系统 | ES Modules (`import`/`export`) | 浏览器原生支持，无需打包工具 |
| 策略接口 | 类继承 (StrategyBase) | Template Method 天然适合 |
| 全局状态 | DataStore单例 | Observer的数据源 |
| CSS方案 | 单文件 `style.css` | 简洁够用，不需要CSS-in-JS |
| 兼容性 | Chrome 80+ / Safari 14+ | 支持ES Modules的最低版本 |
| 构建步骤 | 无 | 零构建，直接serve |

## 不做什么

- ❌ 不引入 webpack/vite/TypeScript — 增加复杂度但不提升中奖概率
- ❌ 不拆分CSS — 一个style.css够用
- ❌ 不引入React/Vue — 纯Vanilla JS已满足需求
- ❌ 不强套23种模式 — 只选7个真正有用的
- ❌ 不动ML模块 — xgb/lstm已独立，完美

## 预期收益

- 策略迭代速度: 1个文件 vs 改3010行巨型文件
- 可测试性: 纯函数可单独测试
- 代码导航: 按文件名定位，不用grep
- 新增策略: 继承StrategyBase，实现2个方法即可
- 文件大小: 最大单文件 < 200行
