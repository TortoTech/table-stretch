# 表格自动拉伸：研究调研

检索日期：2026-10-31。目标为固定总宽度、内容完整显示时的最小表格高度；“审美最好”不属于可直接证明的目标。

## 主要来源

| 来源 | 结论与本项目关系 |
| --- | --- |
| [W3C HTML Autolayout Table Sizing](https://www.w3.org/MarkUp/html3-tables/sizing.html) | 历史算法根据最小/最大内容宽度，按伸缩区间比例分配余量。适合作为基线，不保证总高度最小。 |
| [W3C CSS 2.2 §17.5.2](https://www.w3.org/TR/CSS22/tables.html#width-layout) | 明确不规定唯一的“最优”布局；自动布局约束与全局高度优化是不同问题。 |
| [CSS Tables Level 3](https://www.w3.org/TR/2025/WD-css-tables-3-20251216/) | 本次核验为 2025-12-16 Working Draft。描述内在尺寸、宽度分配和兼容行为；不是高度最小化的数学保证。不能把工作草案当成已完成标准。 |
| [Gange, Marriott, Moulder, Stuckey, *Optimal Automatic Table Layout*, DocEng 2011](https://doi.org/10.1145/2034691.2034697) | 讨论 A*、CP、lazy clause generation 精确求解；其公开作者稿说明最坏情形的组合复杂性。[作者论文索引](https://research.monash.edu/en/publications/optimal-automatic-table-layout/)、[作者稿镜像](https://citeseerx.ist.psu.edu/document?doi=ab865b7c9ec1e977e6f7b8e3135da965eb70b9d9&repid=rep1&type=pdf)。 |
| [Marriott, Moulder, Hurst, *HTML automatic table layout*, ACM TWEB 2013](https://doi.org/10.1145/2435215.2435219) | 与自动布局启发式相关的后续工作；本次通过[大学元数据](https://research.monash.edu/en/publications/html-automatic-table-layout/)核验书目信息，没有据此声称复现了论文全部实验。 |
| [Bilauca et al., *Automatic Minimal-Height Table Layout*, INFORMS JOC 2015](https://pubsonline.informs.org/doi/abs/10.1287/ijoc.2014.0637) | 将离散单元格配置建模为精确组合优化，评估 MIP 与采用 lazy clause generation 的 CP。为“最小高度”目标提供直接研究依据。 |
| [GAMS tablelayout 模型](https://www.gams.com/latest/gamslib_ml/libhtml/gamslib_tablelayout.html) | 公开的宽高配置模型：列宽容纳各单元格，行高取相应需求，总行高为目标。引用 Bilauca/Healy 2010 模型。[原论文 DOI](https://doi.org/10.1145/1860559.1860594)。 |

2011 年作者稿的搜索索引可读取摘要和部分正文，但直接 PDF 抓取返回 403；2015 年本次直接读取的是出版方摘要。算法实现与证明是本项目自行构建，未声称逐行复现这些论文的求解器或完整复现实验。

## 技术选择

单元格高度随宽度增大通常呈非增阶梯状。总高度为各行最大单元格高度之和，存在跨列耦合。一般文本布局的最小高度问题具有 NP-hard 难度；不能承诺一个对任意大表格都快速、又保证全局最优的简单比例算法。上述 2011 年作者稿明确讨论完整搜索的最坏非多项式复杂度。

本项目选择：

1. 输入完整的单元格阶梯曲线，使用断点而非逐像素枚举。
2. 逐列动态规划，保存已用宽度和每一行的高度，而非单一总高度。
3. 只有在宽度和每行高度都不更优时才删除状态（Pareto 支配）。
4. 最后选择最小总行高，再在列上限内拉伸到精确宽度。

这一选择便于独立实现和论证，不需要外部 MIP/CP 求解器。它是已有精确组合优化思想的工程实现，不主张理论首创，也不主张性能优于论文中的 A*/CP/MIP。性能比较必须在相同字体度量、约束和样本上另外开展。

后续已加入这些方法的可运行适配版本，并在相同简化尺寸模型上开展比较：[实现范围](algorithms.md)、[扩大书库实测](benchmark.md)。比较包含实际 Gecode、Chuffed 与 HiGHS；不是重现原论文的硬件、完整模型变体和历史求解器版本。

## 为什么不能只用贪心或连续近似

比例分配可作为候选初解，但可能错过某个关键换行阈值。连续面积近似 `height ≈ area / width` 丢失离散换行结构；证明近似问题最优不等于证明原问题最优。只保留当前总高度最低的部分布局同样不安全，后续列会改变不同行的最大值。

项目的 `[5,5] → [7,3]` 例子展示阈值效应；`row_vectors_are_necessary` 测试展示仅按总高度剪枝的错误。这些是本项目构造的反例，不是引用论文中的实验结果。
