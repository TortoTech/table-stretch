# 已有研究算法的实现与比较口径

这是可运行的研究思路/模型适配，使用当前求解器版本。2026-10-31 的[逐项审计](research-audit.md)发现旧版方法名省略了搜索与模型差异，现已更正并增加四个对照；不能把适配版本耗时当作原论文实验的复现。

| 标识 | 实现 | 来源 |
| --- | --- | --- |
| pareto | Rust，前沿动态规划、界剪枝与末列直接完成 | 本项目，优化证明见[第 9 节](proof.md#9-优化版-pareto终端化界剪枝与路径存储) |
| html | Rust，最小/首选宽度间比例分配 | [W3C 历史 HTML 自动布局](https://www.w3.org/MarkUp/html3-tables/sizing.html) |
| astar2011 | Rust，优先队列、剩余面积下界、列最小性剪枝 | [Gange 等，2011，§3](https://doi.org/10.1145/2034691.2034697) |
| cp2011_gecode | 配置索引与 element，Gecode，列宽搜索 | 旧适配，非 2011 cp-w 的引擎/搜索 |
| lcg2011_chuffed | 同一配置模型，Chuffed，混合搜索 | 旧适配，非 cp-seq，也不固定 VSIDS |
| lcg2015_cellfree | 相邻配置不等式析取，Chuffed，无 RCSV | [2015 cell-free 公式](https://people.eng.unimelb.edu.au/pstuckey/papers/ijor15.pdf)的旧适配 |
| mip2015_unary | 每格前缀布尔变量，HiGHS | 2015 §4 基础 unary 编码，不是 mipcf |
| mip2015_onehot | 每格恰选一个配置，HiGHS | 2015 §4 基础 standard 编码 |
| cp2011_chuffed_seq | Chuffed 关闭学习，按最小单元格配置高度搜索 | 2011 cp-w 的现代适配 |
| lcg2011_chuffed_seq | 同一最小格高搜索，保留 LCG | 2011 cp-seq 的现代适配 |
| lcg2015_rcsv | cell-free＋RCSV 取值域，Chuffed 固定 VSIDS | 2015 cpcf 简单表格适配 |
| mip2015_cellfree | cell-free＋RCSV＋共享行列 unary 变量，HiGHS | 2015 mipcf 简单表格适配 |

2011 作者稿的算法和模型可通过[作者上传稿](https://www.researchgate.net/publication/221353238_Optimal_automatic_table_layout)核验。2015 作者稿直接下载被站点拦截，但搜索索引提供了 cell-free 和 §4 的具体公式；此处依据已核验公式实现，不声称已读取全文全部细节。

## A* 正确性及适配

优先选择高度下界最小的节点，同分优先更深的节点。单元格面积下界 `a_ij` 取所有可用配置中最小的 `width × height`；剩余列宽为 `R`，行高下界为 `max(当前行高, ceil(Σ剩余列 a_ij/R))`。任意可行延伸都满足 `最终行高 × R ≥ Σa_ij`，因此下界可采纳。完整叶子的下界等于真实目标，第一次弹出的完整叶子全局最优。

若已确定列高于硬下限，缩小一个单位却不会增加任何当前行高，则不是列最小布局，可以删除。总存在列最小的最优解；后续列只会增高各行，所以非最小前缀不会变成最小完整布局。

与论文实现的差异：只支持简单单元格；面积来自整数配置而非字形；没有实现可选的启发式初始上界；重新计算当前节点下界，不保留祖先行下界。这些影响性能，但不破坏可采纳性。新增 A* 尚未纳入 Lean 机器证明，已通过独立全整数宽度穷举测试。

只优化本项目要求的总高度，不实现论文的次要“最小总宽度”目标；本项目会统一拉伸填满容器。W3C 方法也相应增加整数舍入、列上限和最终填满步骤。

## CP、LCG、MIP

所有模型使用相同曲线、列上下限、`Σw≤B` 和目标 `min Σh`，余量在求解后拉伸。

2011 配置模型为每格选择 `f_d`，约束 `w_col≥width[f_d]`、`h_row≥height[f_d]`。旧 Gecode 使用从左到右列宽搜索；旧 Chuffed 使用真正的 CP/SAT 学习，但 `-f --vsids` 允许重启时切换搜索。旧源码在 `models/cp2011.mzn`。新增 `cp2011_seq.mzn` 按最小格高搜索，分别在有/无学习的 Chuffed 上执行；两者关闭 VSIDS 和基于冲突的重启。

2015 cell-free 对相邻配置使用 `h_row≥h_k OR w_col≥w_(k+1)`，并保留首宽/末高边界。MIP 分别使用 one-hot 和 unary 前缀变量表达配置选择。新增 RCSV 简单表格版本和共享 unary 的 cell-free MIP；后者复用行列阈值变量表达析取。没有实现论文全部 positional/glue/跨格变体。现代 HiGHS 不是原论文使用的 CPLEX 12.1，MiniZinc 编译也不是原论文建模接口。

实际版本为 MiniZinc 2.10.1、Gecode 6.4.0、Chuffed 0.14.0、HiGHS 1.15.1。工具放置于 `.tools/`，源码不包含其二进制。来源为 [MiniZinc 官方发行包](https://www.minizinc.org/downloads/)。所有外部求解单线程、种子 1；各 Chuffed 配置不同，详见 `scripts/compare_solvers.py`、`examples/unified_worker.rs` 和基准元数据 `external_models_and_flags`。MIP 使用默认数值容差；只有 `OPTIMAL_SOLUTION` 且布局通过整数复核才记作最优。

## 复现

```sh
cargo run --locked --release -- --algorithm astar2011 examples/table.json
cargo run --locked --release -- --algorithm html examples/table.json
python3 scripts/benchmark_corpus.py --output docs/benchmark-rust.jsonl
python3 scripts/benchmark_unified.py --minizinc /path/to/minizinc
python3 scripts/report_unified.py
python3 scripts/check_models.py
```

`check_models.py` 默认读取 `.tools/minizinc-path.txt`。本机使用官方 DMG 中的命令行工具；系统不允许挂载镜像，因而以 7-Zip 解包并保留 Frameworks 依赖，没有修改系统安全设置。

## 计时范围

主比较采用[统一端到端协议](benchmark-unified.md)：同一组 64 个场景、相同曲线 JSON、相同 `unified_worker` 独立进程协议。新增优化前 worker 对照，来自提交 `104c545`，与新版本和研究方法在同一轮交错测量。父进程从启动前计时到退出并收完输出，包含输入读取、验证、公共可行布局兜底、方法自身预处理、外部模型导出和编译、搜索、拉伸和序列化。优化后的 Pareto 在自己的计时准备阶段计算可行上界和面积/行高下界。所有方法共同排除文本尺寸曲线构造。

每次总墙钟限时 1 秒，超时冻结并清理整个存活进程树（包含求解器另建的进程组）。基准 worker 关闭 Rust 专有计数限制，外部求解器不再另享“编译后 1 秒”；库的生产默认限制未变。统一预热 1 次、测量 3 次，单线程、种子 1、随机化方法顺序，串行运行。主报告计入所有场景与超时，并给出 PAR-2 及相同成功子集。

阶段耗时另列用于诊断。Rust 的准备/搜索/拉伸由 `Instant` 计时；外部 `flatTime`、`initTime`、`solveTime` 由各引擎报告，边界和精度不同，不作为跨方法主排名。Chuffed 的搜索统计精度为毫秒，显示 0 不代表零耗时。端到端主表的计时边界已经统一，可以比较当前实现从尺寸曲线到完整布局的实际耗时。

`benchmark_corpus.py` 的库函数计时及 `compare_solvers.py` 的旧外部计时保留在[历史报告](benchmark.md)。它们不含相同范围的启动、输入/输出成本，并采用不同资源限制，不能与统一报告混合计算速度倍数。

## 编译优化回归

独立穷举发现 MiniZinc 2.10.1 默认优化在 `tests/fixtures/minizinc-unary-regression.json` 上消除了必要的 unary 约束：默认设置下返回高度 3，但两个列宽都只能为 1，真实最优高度为 6。生成的 FlatZinc/LP 中缺失必要的链约束；使用 Gecode 和 HiGHS 都能观察到错误，因而不应归因于某一个后端引擎。

所有正式外部模型比较统一使用 **`-O0`** 禁用编译优化。该回归及另外的小型矩形模型通过独立全整数穷举校验，现已扩展为九种外部配置、共 144 个模型/实例组合，包含不可行实例和 RCSV 硬下限适配。关闭编译优化会影响编译时间和传播表现，因此此配置被记录在结果元数据中；不要将报告结果与默认优化的历史运行混合。
