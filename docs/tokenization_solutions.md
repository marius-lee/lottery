# 彩票预测 Token 设计方案调研

> 搜索日期: 2026-06-07 | 搜索来源: GitHub / arXiv / ACL / 微信技术文章

---

## 方案 1: kyr0/lotto-ai — 德国 6/49 Attention LSTM

- **来源**: https://github.com/kyr0/lotto-ai
- **作者**: Aron Homberg, 2023
- **语言/框架**: JavaScript / TensorFlow.js
- **目标**: 德国乐透 6/49

### 完整业务流程

```
① 数据加载: lotto.csv → lotto.json
  每行: [期号, n1, n2, n3, n4, n5, n6, superzahl]

② 编码: One-Hot
  49个普通号 + 1个超级号 = 50维向量
  每个号码 → 50维向量 (对应位置=1, 其余=0)
  每期 → 7 × 50 = 350维

③ 窗口构造: 5期滑动窗口
  X = 前5期的编码 (5×350 矩阵)
  Y = 第6期的编码

④ 模型: Attention LSTM
  输入 → LSTM(128) → Attention → Dense → Sigmoid
  损失: Binary Cross-Entropy
  优化: Adam
  正则: Dropout + L2

⑤ 预测解码:
  decodeBestBet() → 最高概率的6个号 (去重)
  decodePredictionsTemp(T) → 温度采样 (多样性)
  hasDuplicates() → 去重校验

⑥ 训练/验证: 80%/20% 分割
```

### 算法特点
- One-hot 编码: 稀疏、可解释、无信息损失
- 单个模型预测全部号码 (不分离红蓝)
- 无分隔符
- 窗口固定 5 期

---

## 方案 2: KittenCN/predict_Lottery_ticket — 双色球/大乐透 LSTM+Transformer

- **来源**: https://github.com/KittenCN/predict_Lottery_ticket
- **语言/框架**: TensorFlow / PyTorch
- **目标**: 双色球 (SSQ) / 大乐透 (DLT)

### 完整业务流程

```
① 数据获取: 爬虫抓取 500.com / 中彩网

② 编码: Embedding
  每个号码 → 可学习的 64 维稠密向量
  红球: 33类 → Embedding(33, 64)
  蓝球: 16类 → Embedding(16, 32)

③ 模型架构:
  ┌─ 红球模型 ────────────────────┐
  │ Embedding(33→64)              │
  │ Permute → Per-Ball LSTM(128)  │
  │ Global LSTM(64)               │
  │ Dense(33) → Softmax × 6位置   │
  └──────────────────────────────┘

  ┌─ 蓝球模型 ────────────────────┐
  │ Embedding(16→32)              │
  │ LSTM(64) → LSTM(32)           │
  │ Dense(16) → Softmax           │
  └──────────────────────────────┘

④ 损失: SparseCategoricalCrossentropy
⑤ 优化: Adam(lr=1e-4, clipnorm=5.0)
⑥ 早停: patience=10, restore_best=True

⑦ 输出: 每位置概率 → 求和聚合 → top-6红 + top-1蓝
```

### 算法特点
- **红蓝完全分离**: 两个独立模型，分别训练
- **位置感知**: 6个红球位置各自建模 (Per-Ball LSTM)
- **概率聚合**: 位置概率求和后选 top-6 (丢失位置信息)
- 无分隔符
- Embedding 可学习

### 与我们的关系
我们当前的 LSTM 模块直接源自 KittenCN 架构。

---

## 方案 3: 微信技术文章 — 神经网络彩票预测综述

- **来源**: https://mp.weixin.qq.com/s?__biz=MzAwNDU1NzczMg==&mid=2247503317&idx=1&sn=343df5359a6f6ec1bfd65807722877ba
- **作者**: 郑敦庄 (基于 TensorFlow+Keras 深度学习算法原理与编程实战)

### 三种问题形式化

**方案 3a: 位置独立多分类**
```
红球: 6 个独立的 33 类分类器
蓝球: 1 个独立的 16 类分类器
输入: One-hot 编码的历史数据
输出: 7 个 Softmax (互不干扰)
损失: 各位置 CrossEntropy 之和
```

**方案 3b: 序列生成 (Seq2Seq)**
```
编码器: LSTM/GRU 处理历史数据 → 固定长度上下文向量
解码器: 自回归生成 6 红 + 1 蓝
Teacher Forcing: 训练时用真实号码, 推理时用上一步输出
```

**方案 3c: 整体概率分布**
```
整个 49 号球 → 49维 0/1 向量 (出现=1, 不出现=0)
输入: 历史 N 期的 49 维向量拼接
输出: 下一期的 49 维概率向量 → 选 top-6 红 + top-1 蓝
损失: Binary CrossEntropy
```

### 算法特点
- 三种范式, 从简单到复杂
- One-hot 编码是基础方案
- 位置独立分类 = 我们 XGBoost 49 分类器的思路

---

## 方案 4: EMNLP 2020 — Contextualized Number Prediction

- **来源**: https://aclanthology.org/2020.emnlp-main.385/
- **作者**: Berg-Kirkpatrick & Spokoyny (UC San Diego)
- **发表**: EMNLP 2020, pp. 4754-4764

### 完整业务逻辑

```
问题: NLP 中数字的表示和预测
  传统: 子词分词把 "3,141,592" 切成 ["3", ",", "141", ",", "592"]
  问题: 丢失了数字的大小信息

核心发现: 离散潜变量 (DExp) 显著优于其他方案

方法:
  ┌─ 数字检测 ──→ 识别文本中的数字 token
  └─ 数字编码 ──→ log 尺度分桶 (10^0, 10^1, 10^2, 10^3, 10^4)
                 每个桶对应一个离散潜变量
                 模型预测: P(bucket) × P(mantissa | bucket)

输出分布:
  DExp:   离散指数分布 (最优)
  Flow:   归一化流 (次优)
  GMM:    高斯混合模型
  Reg:    直接回归 (最差)
```

### 可借鉴的点

- **log 尺度分桶**: 双色球号码范围 1-33/1-16, 可以用类似思路分层
- **离散潜变量**: 先预测"区域"(1-11/12-22/23-33), 再预测区域内具体号码
- **混合分布**: 红球(不放回)和蓝球(独立)应该用不同的输出分布

---

## 方案 5: arXiv:2403.08081 — 自注意力下一token预测理论

- **来源**: https://arxiv.org/abs/2403.08081
- **作者**: University of Michigan & Google Research, 2024
- **标题**: "Mechanics of Next Token Prediction with Self-Attention"

### 核心理论

```
Token-Priority Graph (TPG):
  训练数据建模为有向图
  节点 = token
  边 = token A → token B 的转移概率

  SCC (强连通分量):
    组内 token 互相可达 (如 热门号集群)
    组间有优先级顺序 (罕见号→常见号)

  自注意力学习过程:
    阶段1 (Hard Retrieval): 精确选择与当前token相关的高优先级历史token
    阶段2 (Soft Composition): 在这些token上做凸组合, 采样下一个token

  注意力权重收敛: W_GD ≈ C·W_hard + W_soft
```

### 对双色球的启发

- **Token 之间确实存在可学习的转移关系** (如某些号经常一起出现)
- SEP 分隔符可能是必要的——它作为一个"锚点 token"帮助模型定位每期的边界
- 去重后处理破坏了 token 之间的依赖关系——应该让模型自己学会不放回抽样
- 位置编码的顺序(正向/反向/随机)会影响 TPG 的构建

---

## 方案对比总表

| 维度 | kyr0/lotto-ai | KittenCN | 微信综述 | EMNLP 2020 | arXiv TPG | **我们当前** |
|------|:--:|:--:|:--:|:--:|:--:|:--:|
| 编码 | One-hot | Embedding | One-hot | 离散潜变量 | 理论 | Embedding(50) |
| 红蓝分离 | 否 | **是** | 3种变体 | 不适用 | 不适用 | 否 |
| 分隔符 | 无 | 无 | 无 | 不适用 | **需要** | SEP=0 |
| 每期token | 7 | 7 | 7 | — | — | **8** (浪费1个) |
| 输出约束 | 后处理去重 | 位置概率求和 | 位置独立分类 | log分桶 | 未涉及 | 后处理去重 |
| 窗口大小 | 固定5期 | 固定5期 | 可配 | 可变 | 可变 | 可变(8/10/12/15) |
| 模型 | LSTM+Attn | LSTM+Transformer | MLP/RNN/Transformer | BERT/GPT | 理论 | **GPT(4层)** |
| 损失 | BCE | CE | CE | NLL | — | CE |
| 多注生成 | 温度采样 | 无 | 无 | 潜变量采样 | — | 3温度采样 |
