# 自训练引擎设计文档

> 版本: v1 | 日期: 2026-06-06 | 状态: 实施中

---

## 一、架构总览

```
┌── 后台: 永不停止的训练循环 ──────────────────────────────────┐
│                                                               │
│  每个模型维护两份权重:                                        │
│    current.keras   当前训练中的权重 (不断更新, 有波动)         │
│    best.keras      历史最高命中记录时的权重 (只升不降)         │
│                                                               │
│  训练循环: 永久运行, 不收敛, 持续探索                         │
│  best文件: 只在突破历史记录时覆盖                              │
│                                                               │
│  数据库: training_log 记录每轮训练指标                         │
│                                                               │
└───────────────────────────────────────────────────────────────┘
                         │
                         │ 用户点击时读取 best.* 文件
                         ↓
┌── 前台: 瞬时响应 ────────────────────────────────────────────┐
│                                                               │
│  GET /api/generate                                            │
│    → 读 5个 best.* 预测文件           (< 1ms)                 │
│    → 加权投票 → 最优3注               (< 10ms)                │
│    → 返回结果                         (总 < 10ms)             │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

### 核心原则

| 原则 | 说明 |
|------|------|
| 后台永不停止 | 训练循环 forever, 每轮完立即下一轮 |
| 前台瞬时响应 | 不触发训练, 只读已算好的最优结果 |
| best只升不降 | 只在命中数突破历史时才覆盖 best 文件 |
| current持续探索 | 允许波动, 允许退步, 允许随机扰动 |
| 新一期热启动 | 锚点前移, 用上一轮 best 权重继续 |

---

## 二、数据结构

### 2.1 SQLite: training_log 表

```sql
CREATE TABLE IF NOT EXISTS training_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    model           TEXT NOT NULL,         -- gpt / xgb / lstm / thompson / lasso
    round_number    INTEGER NOT NULL,      -- 第几轮全局训练编号
    phase           TEXT NOT NULL,         -- train / validate
    target_period   INTEGER,              -- 验证目标期号 (最新一期)
    context_start   INTEGER,              -- 训练数据起始期号
    context_end     INTEGER,              -- 训练数据结束期号
    red_hits        INTEGER,              -- 预测命中红球数 (验证时)
    blue_hit        INTEGER,              -- 预测命中蓝球 (0/1)
    loss            REAL,                 -- 训练损失
    window_size     INTEGER,              -- 本轮窗口大小
    learning_rate   REAL,                 -- 本轮学习率
    dropout         REAL,                 -- 本轮dropout
    duration_sec    REAL,                 -- 耗时(秒)
    best_so_far     INTEGER DEFAULT 0,    -- 1=本轮命中突破历史记录
    notes           TEXT,                 -- 备注
    created_at      TEXT DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_tlog_model ON training_log(model);
CREATE INDEX IF NOT EXISTS idx_tlog_target ON training_log(target_period);
```

### 2.2 预测快照文件

文件路径: `.cache/predictions/{model}_prediction.json`

```json
{
  "model": "gpt",
  "reds": [3, 8, 14, 19, 25, 31],
  "blue": 9,
  "target_period": 2026062,
  "red_hits": 3,
  "best_so_far": true,
  "round_number": 487,
  "updated_at": "2026-06-06 22:14:31"
}
```

### 2.3 最终出号缓存

文件路径: `.cache/predictions/final_3_tickets.json`

```json
{
  "tickets": [
    {"reds": [3, 8, 14, 19, 25, 31], "blue": 9},
    {"reds": [2, 7, 13, 18, 24, 30], "blue": 14},
    {"reds": [1, 6, 12, 22, 27, 33], "blue": 5}
  ],
  "target_period": 2026062,
  "updated_at": "2026-06-06 22:14:31"
}
```

---

## 三、训练循环详细设计

### 3.1 GPT 自训练循环

```
输入: 全部历史数据 (2013021 ~ target_period-1)
锚点: target_period (最新一期)
权重: current.keras, best.keras

每轮:
  1. 从训练数据随机抽取窗口参数
     window_size = random.choice([8, 10, 12, 15])
     lr = random.choice([1e-4, 3e-4, 5e-4, 1e-3])
     dropout = random.choice([0.1, 0.15, 0.2])

  2. 滑动窗口遍历训练数据
     for i = window_size to len(train_data):
       上下文 = train_data[i-window_size : i]
       真值   = train_data[i]
       前向 → loss → 反传 → 更新 current.keras

  3. 验证: 用 current 权重预测 target_period
     red_hits = len(pred ∩ actual)
     写入 training_log

  4. if red_hits > best记录的命中数:
       覆盖 best.keras / best.json
       更新 final_3_tickets.json

  5. 超参数轮换 (防止过拟合):
     每轮使用不同的 window/lr/dropout 组合

  6. 立刻进入下一轮 (不停)
```

### 3.2 XGBoost 自训练循环

```
每N分钟执行一次 (默认10分钟):

  1. 全量重训49个模型
  2. 预测 target_period
  3. 记录命中
  4. 如果突破 best → 覆盖 best.pkl / best.json
```

### 3.3 LSTM 自训练循环

```
每N分钟执行一次 (默认5分钟):

  1. 全量重训 (30s)
  2. 预测 target_period
  3. 记录命中
  4. 如果突破 best → 覆盖 best.keras / best.json
```

### 3.4 Thompson Sampling 自训练循环

```
实时 (每次 < 1ms):

  1. 用全部历史数据更新 Beta 后验
  2. 采样预测
  3. 如果突破 best → 覆盖 best.json
```

### 3.5 LASSO 自训练循环

```
实时 (每次 < 1ms):

  1. 重算偏差
  2. 选 top-6 热号 + 蓝球
  3. 如果突破 best → 覆盖 best.json
```

---

## 四、超参数策略

### 4.1 轮换机制 (防过拟合)

```
每轮从以下池中随机抽取:
  window_size: [8, 10, 12, 15]
  learning_rate: [1e-4, 3e-4, 5e-4, 1e-3]
  dropout: [0.1, 0.15, 0.2]

目的: 模型被迫从不同"视角"学习同一批数据
     无法死记硬背 → 被迫学习底层规律
```

### 4.2 学习率调度

```
初期 (前50轮):    高学习率 (5e-4 ~ 1e-3)    快速探索
中期 (50-200轮):  中学习率 (3e-4)            精细调整
后期 (200+轮):    低学习率 (1e-4 ~ 5e-4)    稳定优化 + 随机扰动打破平台

如果连续20轮 best 未更新: 临时提升学习率到 1e-3 (增强探索)
如果连续5轮 best 下降:    回退到 best.keras (保护最优)
```

---

## 五、资源消耗

### 5.1 单轮训练资源 (GPT)

| 指标 | 数值 |
|------|:---:|
| 训练窗口数 | ~1990 个 |
| 每窗口耗时 | ~0.05s |
| 单轮耗时 | ~90s |
| 内存峰值 | ~400 MB |
| CPU | 单核 100% |

### 5.2 24小时资源消耗 (所有模型合计)

| 模型 | 频率 | 单次 | 24h CPU时间 |
|------|------|:---:|:-----------:|
| GPT | 连续 (90s/轮) | 90s | ~960轮, 高负荷 |
| XGBoost | 10min/次 | 10min | 低负荷 |
| LSTM | 5min/次 | 30s | 中负荷 |
| Thompson | 实时 | <1ms | 近零 |
| LASSO | 实时 | <1ms | 近零 |

总内存峰值: ~500 MB (GPT dominant)
M1 8GB: 足够有余 (系统 + 浏览器 + 训练 ≈ 6-7GB)

### 5.3 温度/功耗

连续训练会让 M1 发热。建议:
- GPT 循环加 sleep(5) 在每轮之间, 降低 CPU 温度
- 或限制 GPT 训练频率为 2min/轮 (24h ≈ 720轮, 完全够用)

---

## 六、新一期开出后的处理

```
新一期 2026063 开出:

1. 自动拉取最新数据 (调用中彩网 API)
2. 数据库新增一行 (2026063)
3. 对比上一期预测 vs 实际开奖
4. 更新 target_period = 2026063
5. 训练数据扩展 (多了一期)
6. 用 best.keras 热启动, 开始新一轮循环
7. best 重置 → 新的锚点, 新的探索
```

---

## 七、API 设计

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/generate` | GET | 返回 final_3_tickets.json 中的 3注 |
| `/api/training/status` | GET | 各模型当前训练状态 |
| `/api/training/log?model=gpt&limit=50` | GET | 最近N条训练日志 |
| `/api/training/best` | GET | 每个模型的最佳命中记录 |
| `/api/training/start` | POST | 手动启动/重启训练循环 |
| `/api/training/stop` | POST | 暂停训练 (保留进度) |

---

## 八、文件清单

| 文件 | 用途 |
|------|------|
| `ml/self_trainer.py` | 自训练引擎主模块 |
| `.cache/predictions/{model}_prediction.json` | 模型预测快照 |
| `.cache/predictions/final_3_tickets.json` | 最终3注出号缓存 |
| `.cache/models/{model}_best.*` | 最佳权重检查点 |
| `.cache/checkpoints/ckpt_round_{n}.json` | 轮次检查点 (崩溃恢复) |

---

## 九、实现步骤

1. 创建 training_log 表 (DB migration)
2. 实现 self_trainer.py 核心引擎
3. 实现 GPT 循环训练
4. 实现 XGBoost/LSTM/Thompson/LASSO 循环
5. 实现 /api/generate 端点 (读缓存)
6. 实现 /api/training/* 管理端点
7. 集成到启动脚本 start.sh
8. 前端显示训练状态
