# 已有研究算法的实现与比较口径

这是可运行的研究模型实现，使用当前求解器版本，不声称逐行复现历史实现或重现论文的性能数字。

| 标识 | 实现 | 来源 |
| --- | --- | --- |
| pareto | Rust，原有前沿动态规划 | 本项目 |
| html | Rust，最小/首选宽度间比例分配 | [W3C 历史 HTML 自动布局](https://www.w3.org/MarkUp/html3-tables/sizing.html) |
| astar2011 | Rust，优先队列、剩余面积下界、列最小性剪枝 | [Gange 等，2011，§3](https://doi.org/10.1145/2034691.2034697) |
| cp2011_gecode | 配置索引与 element 约束，Gecode | 2011 §4.1 CP 模型的简单单元格版本 |
| lcg2011_chuffed | 同一配置模型，Chuffed，VSIDS/free search | 2011 CP/SAT＋LCG |
| lcg2015_cellfree | 相邻配置不等式析取，Chuffed | [2015 cell-free 编码](https://people.eng.unimelb.edu.au/pstuckey/papers/ijor15.pdf) |
| mip2015_unary | 前缀布尔选择变量，HiGHS | 2015 §4 unary MIP 编码 |
| mip2015_onehot | 每格恰选一个配置，HiGHS | 2015 §4 standard MIP 编码 |

2011 作者稿的算法和模型可通过[作者上传稿](https://www.researchgate.net/publication/221353238_Optimal_automatic_table_layout)核验。2015 作者稿直接下载被站点拦截，但搜索索引提供了 cell-free 和 §4 的具体公式；此处依据已核验公式实现，不声称已读取全文全部细节。

## A* 正确性及适配

优先选择高度下界最小的节点，同分优先更深的节点。单元格面积下界 `a_ij` 取所有可用配置中最小的 `width × height`；剩余列宽为 `R`，行高下界为 `max(当前行高, ceil(Σ剩余列 a_ij/R))`。任意可行延伸都满足 `最终行高 × R ≥ Σa_ij`，因此下界可采纳。完整叶子的下界等于真实目标，第一次弹出的完整叶子全局最优。

若已确定列高于硬下限，缩小一个单位却不会增加任何当前行高，则不是列最小布局，可以删除。总存在列最小的最优解；后续列只会增高各行，所以非最小前缀不会变成最小完整布局。

与论文实现的差异：只支持简单单元格；面积来自整数配置而非字形；没有实现可选的启发式初始上界；重新计算当前节点下界，不保留祖先行下界。这些影响性能，但不破坏可采纳性。新增 A* 尚未纳入 Lean 机器证明，已通过独立全整数宽度穷举测试。

只优化本项目要求的总高度，不实现论文的次要“最小总宽度”目标；本项目会统一拉伸填满容器。W3C 方法也相应增加整数舍入、列上限和最终填满步骤。

## CP、LCG、MIP

所有模型使用相同曲线、列上下限、`Σw≤B` 和目标 `min Σh`，余量在求解后拉伸。

2011 配置模型为每格选择 `f_d`，约束 `w_col≥width[f_d]`、`h_row≥height[f_d]`。Gecode 使用从左到右列宽搜索；Chuffed 使用真正的 CP/SAT 学习与 VSIDS。源码在 `models/cp2011.mzn`。

2015 cell-free 对相邻配置使用 `h_row≥h_k OR w_col≥w_(k+1)`，并保留首宽/末高边界。MIP 分别使用 one-hot 和 unary 前缀变量表达配置选择。没有实现论文全部 extent/glue/RCSV/跨格变体，也没有把现代 HiGHS 称作原论文使用的 CPLEX。

实际版本为 MiniZinc 2.10.1、Gecode 6.4.0、Chuffed 0.14.0、HiGHS 1.15.1。工具放置于 `.tools/`，源码不包含其二进制。来源为 [MiniZinc 官方发行包](https://www.minizinc.org/downloads/)。所有外部求解单线程、种子 1；Chuffed 显式使用 `-f --vsids`。MIP 使用默认数值容差；只有 `OPTIMAL_SOLUTION` 且布局通过整数复核才记作最优。

## 复现

```sh
cargo run --locked --release -- --algorithm astar2011 examples/table.json
cargo run --locked --release -- --algorithm html examples/table.json
python3 scripts/benchmark_corpus.py --output docs/benchmark-rust.jsonl
python3 scripts/compare_solvers.py --minizinc /path/to/minizinc
python3 scripts/check_models.py
```

`check_models.py` 默认读取 `.tools/minizinc-path.txt`。本机使用官方 DMG 中的命令行工具；系统不允许挂载镜像，因而以 7-Zip 解包并保留 Frameworks 依赖，没有修改系统安全设置。

## 计时范围

Rust `solve` 包括验证、候选预处理、搜索和拉伸；不包括文字曲线构造，后者单独测量。

外部端到端耗时包括进程启动、MiniZinc 编译、求解及输出进程结束，不包括 JSON 文件准备和布局复核。`solveTime` 是引擎自身报告的搜索时间，与 Rust `solve` 并非完全相同的范围。Chuffed 统计精度为毫秒，显示 0 不代表零耗时。

Rust 默认计数限制与外部 1 秒搜索限制不是相同预算。报告保留成功率、超限及共同成功子集，不仅比较不同成功子集的平均值。实验保留版本、哈希、每次计时和状态。外部求解时间限制不包含模型编译；另设进程级兜底超时。

## 编译优化回归

独立穷举发现 MiniZinc 2.10.1 默认优化在 `tests/fixtures/minizinc-unary-regression.json` 上消除了必要的 unary 约束：默认设置下返回高度 3，但两个列宽都只能为 1，真实最优高度为 6。生成的 FlatZinc/LP 中缺失必要的链约束；使用 Gecode 和 HiGHS 都能观察到错误，因而不应归因于某一个后端引擎。

所有正式外部模型比较统一使用 **`-O0`** 禁用编译优化。该回归及另外的小型矩形模型通过独立全整数穷举校验，共 70 个模型/实例组合，包含不可行实例。关闭编译优化会影响编译时间和传播表现，因此此配置被记录在结果元数据中；不要将报告结果与默认优化的历史运行混合。
