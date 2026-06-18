## ADDED Requirements

### Requirement: 综合权重系数标注来源
`static/js/ui/analysis.js` 中 `renderWeightsAnalysis()` 的红球综合权重融合公式 SHALL 在代码注释中标注每个系数的来源。蓝球权重同理。

#### Scenario: 红球权重系数有来源注释
- **WHEN** 阅读 `analysis.js` 中 `renderWeightsAnalysis()` 函数
- **THEN** 每个权重系数（0.20, 0.15, 0.15, 0.15, 0.10, 0.10）上方有注释说明来源（频率/遗漏/重号/邻号/012路/同尾）

#### Scenario: 权重行为不变
- **WHEN** 在浏览器中打开走势分析的"综合权重"标签
- **THEN** 展示的红球 Top 10 排名和蓝球排名数值与改动前完全一致

### Requirement: 蓝球权重系数标注来源
蓝球综合权重融合公式 `频率(0.30) + 遗漏(0.45) + 平滑(0.005)` SHALL 有来源注释。

#### Scenario: 蓝球权重来源注释
- **WHEN** 阅读 `analysis.js` 蓝球权重计算部分
- **THEN** 注释标注频率权重 0.30 和遗漏权重 0.45 的来源依据
