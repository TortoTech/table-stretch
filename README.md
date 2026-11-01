# table-stretch

用 Rust 实现的**精确最小高度表格自动拉伸算法**。给定容器宽度和单元格的宽度—高度曲线，求使表格总高度最小的列宽，再在列宽上限内填满容器。

采用换行断点离散化 + Pareto 动态规划，加入末列直接求解、上下界剪枝和父节点路径存储。提供 Rust 库、JSON 命令行、数学证明、Lean 4 抽象算法证明，以及从 torto 本地 EPUB 书库提取的真实表格回归样本。

现已加入 [已有研究算法](docs/algorithms.md)：Rust A*（2011）与 W3C 比例法，以及实际 Gecode CP、Chuffed CP/SAT＋LCG（2011/2015 两种模型）、HiGHS MIP（2015 unary/one-hot 两种编码）。扩大到 25 本书的 317 个表格，统一计时、超时与结果质量见 [最新对比报告](docs/benchmark-unified.md)。

## 当前 benchmark

实测日期：2026-10-31（US/Pacific）。Apple M6、16 GiB 内存、macOS-27.0-arm64-arm-64bit、Rust 1.99.1，release 构建、单线程。

**8 种方法及 1 个优化前对照使用统一标准重测**：同一组 64 个复杂/多样场景、同一份曲线 JSON、相同的 Rust worker 协议；每次从启动进程前到进程退出及输出收完计时。输入读取、验证、方法自身预处理、模型编译、搜索、最终拉伸与输出全部计入；每次总墙钟限时 **1 秒**。Rust 搜索次数限制在本次基准中关闭，生产库默认值不变。每场景/方法预热 1 次、测量 3 次，各方法按固定种子打乱顺序，串行运行。

场景沿用此前外部测试的选择，来自 25 本书、317 个真实表格的 2332 个宽度场景，包含此前全部 8 个 Pareto 搜索超限案例。这是复杂场景子集，不是全书库的随机抽样。

| 方法 | 完成场景 | 超时运行 | 端到端 P50（ms） | P95（ms） | PAR-2（ms） |
| --- | ---: | ---: | ---: | ---: | ---: |
| Pareto DP（优化前对照） | 64/64 | 0/192 | 2.294 | 120.201 | 19.409 |
| **Pareto DP（优化后，当前默认）** | 64/64 | 0/192 | 2.171 | 2.508 | 2.165 |
| A* 2011（Rust） | 64/64 | 0/192 | 2.208 | 2.430 | 2.204 |
| W3C 比例法（启发式） | 64/64 | 0/192 | 2.131 | 2.373 | — |
| 2011 CP / Gecode | 64/64 | 0/192 | 77.722 | 95.919 | 80.764 |
| 2011 CP/SAT＋LCG / Chuffed | 62/64 | 6/192 | 72.897 | 751.154 | 191.108 |
| 2015 cell-free＋LCG / Chuffed | 64/64 | 0/192 | 69.473 | 499.339 | 113.429 |
| 2015 MIP unary / HiGHS | 64/64 | 0/192 | 75.733 | 375.587 | 115.634 |
| 2015 MIP one-hot / HiGHS | 64/64 | 0/192 | 77.065 | 302.618 | 103.151 |

“完成场景”要求 3 次均在时限内完成；精确方法须证明最优，W3C 仅要求返回可行解。P50/P95 在**全部 64 个场景**上统计：先取每场景 3 次耗时的中位数，再取跨场景分位数；超时按 1000 ms 截断。PAR-2 对全部 192 次运行取平均：成功用实际耗时，超时罚为 2000 ms，越小越好；启发式不参与该精确求解评分。不能把截断耗时当作超时任务真正完成所需时间。

优化前后在**同一轮交错测量**：Pareto 端到端 P95 从 **120.201 ms** 降至 **2.508 ms**；原生求解阶段（准备＋搜索＋拉伸）P95 从 **118.075 ms** 降至 **0.040 ms**。这些是各自分位数，不是逐场景加速比。优化前 worker 来自提交 `104c545`，源码与二进制身份保存在元数据中。

当前默认 Pareto 完成 **64/64** 个场景，A* 完成 **64/64**；所有已证明最优的结果均与参考最优高度一致。W3C 比例法在 34/64 个场景未达到最优高度。Rust 三种方法的端到端 P50 为 2.131–2.208 ms，其中已计入进程及输入输出成本；搜索差异另见阶段诊断。耗时表示当前实现的部署成本，不能据此推断原论文历史实现的速度。

所有方法都从预先构造的相同尺寸曲线开始，因此共同排除文本曲线构造、字体 shaping、EPUB 解压和绘制。超时保留截止时刻前收到的最佳可行布局，不标记为最优。MiniZinc 统一使用 `-O0`，相关编译器回归见[算法说明](docs/algorithms.md#编译优化回归)。

详情与复现：[统一报告](docs/benchmark-unified.md) · [原始记录](docs/benchmark-unified.jsonl) · [相同输入及哈希](docs/benchmark-unified-inputs.json) · [汇总](docs/benchmark-unified-summary.json)。[旧报告](docs/benchmark.md)保留历史库函数计时，不再作为跨方法的主对比。

## 运行

```sh
cargo run --locked --release -- examples/table.json
cargo run --locked --release -- --algorithm astar2011 examples/table.json
cargo run --locked --release -- --algorithm html examples/table.json
cargo test --locked
cargo clippy --locked --all-targets -- -D warnings
cargo run --locked --release --example ebook_corpus
```

优化版默认算法的示例输出列宽 `[6, 4]`、行高 `[2, 1]`，总高度 `3`。列宽总和 `10` 加固定横向空间 `2`，恰好填满容器 `12`。旧版的 `[7, 3]` 也是同高最优解；相同输入若等宽分配为 `[5, 5]`，总高度为 `7`。

CLI 接受文件路径或 `-`（标准输入），成功时输出 JSON；非法输入、不可行约束或搜索超限以非零状态退出。`--help` 查看用法。

默认使用 `pareto`；`astar2011` 也是精确算法，`html` 为启发式，返回 `optimal: false`。Lean 检查 Pareto 抽象搜索，并加入末列单调端点、有效界剪枝和加强覆盖不变量的定理；不自动涵盖 A*、外部求解器或 Rust 源码的端到端验证。优化版的证明边界见[第 9 节](docs/proof.md#9-优化版-pareto终端化界剪枝与路径存储)。

## 数据与接入

`Table` 按列存放 `Column.cells`，各列必须有相同且非零的行数。尺寸为 `u32` 整数布局单位，可以采用 1/64 像素等定点单位；总高度为 `u64`。

```rust
use table_stretch::{Column, Limits, Profile, Table, solve};

// 已测量的不可分割词宽度；词间距 1，行高 16。
let cell = Profile::from_tokens(&[4, 3, 8, 5], 1, 16)?;
let table = Table {
    width: 30,
    reserved_width: 2,
    columns: vec![Column { min_width: 8, max_width: 40, cells: vec![cell] }],
};
let layout = solve(&table, Limits::default())?;
# Ok::<(), table_stretch::Error>(())
```

也可以直接提供 `Profile.steps = [{width, height}, ...]`。`width` 必须严格递增，`height` 必须非增。低于第一个宽度表示内容放不下；最后一个断点之后高度保持不变。曲线必须包含所有影响高度的断点，不能把稀疏采样误当作真实曲线。

`min_width` / `max_width` 是列宽硬约束。`reserved_width` 是边框、列间距等固定横向空间的总和。影响单元格排版的 padding 应计入曲线；固定纵向边框/间距可在返回高度上另加常数，不改变最优列宽。

接入 torto 时，应由实际字体 shaping、断行和 CSS 处理产生曲线；求解器只依赖这些尺寸，不依赖字体库。当前项目没有修改 torto，也没有接入其渲染流程。

## 最优性与范围

保证在**输入曲线所定义的模型内**，所有内容可容纳、列宽满足上下限、表格填满指定宽度，且总高度全局最小。同高解不保证视觉均衡最优；余量按可用容量均摊，余数按列顺序分配。

第一版不支持 `rowspan` / `colspan`、嵌套表格、跨页目标、百分比布局依赖或非单调高度曲线。`from_tokens` 支持固定词宽、固定词间距、固定行高，不处理连字、断字、强制换行与复杂文字塑形。

这是精确组合优化，最坏时间和空间可随列数指数增长。默认限制为 100 万次候选扩展、2000 万次支配比较、1 万个前沿状态；库调用可配置。达到限制返回 `Error::Limit`，不会输出带“最优”标记的近似结果。限制约束搜索计数，不是严格的墙钟时间或整个输入的内存限额。

## 证明和研究

- [已有研究与设计选择](docs/research.md)：W3C、2011/2015 年精确布局研究、公开 MIP 模型。
- [模型与完整数学证明](docs/proof.md)：断点完备性、剪枝安全性、全局最优性、拉伸保持最优。
- [Lean 4 证明](proof/Optimality.lean)：机器检查抽象 Pareto 搜索的覆盖性、可行性和最优性。
- [真实 EPUB 测试报告](docs/validation.md) 与 [原始结果](docs/corpus-results.json)。
- [全部方法统一端到端耗时对比](docs/benchmark-unified.md)；[实现范围与计时口径](docs/algorithms.md)。

Lean 证明**不是 Rust 源码的端到端验证**。输入曲线完备性、Rust 与数学模型的对应、断点构造、整数实现及余量分配仍依靠文档论证和差分测试。没有把有限测试当作所有输入上的形式化证明。

```sh
# 使用 Lean 4.19.0，无需 mathlib。若安装了 elan，在 proof/ 下运行会读取固定版本。
cd proof
lean Optimality.lean
```

本地下载的隔离工具链可用 `../.tools/lean-4.19.0-darwin_aarch64/bin/lean Optimality.lean`。`scripts/check.sh` 一次执行 Rust 和 Lean 检查；`LEAN_BIN` 可指定 Lean 路径。

## 重新提取书库样本

```sh
python3 scripts/extract_epub_tables.py \
  --library "$HOME/Library/Application Support/com.Rebook.Rebook/library"
cargo run --locked --release --example ebook_corpus > docs/corpus-results.json
```

脚本只读 EPUB，输出书名、源文件哈希、章节/表格位置和数字化词宽，不复制书籍正文。测试夹具已包含在项目里，运行测试不需要访问本地书库。提取会将段落/空白规范化，使用简化字符宽度；这是源自真实内容的算法测试，不是原书 CSS/字体渲染保真测试。

扩大样本与基准：

```sh
python3 scripts/extract_epub_tables.py --tables 0 --per-book 0 \
  --max-columns 64 --max-rows 1000 --max-tokens 5000 \
  --output tests/fixtures/ebooks-expanded.json
python3 scripts/benchmark_corpus.py --output docs/benchmark-rust.jsonl
# 主对比使用已提交的同一组 64 个场景，不需要重新访问书库。
python3 scripts/benchmark_unified.py --minizinc /path/to/minizinc
python3 scripts/report_unified.py
```

CP/LCG/MIP 由 MiniZinc 及实际外部求解器执行，全部方法使用同一个 Rust worker，Python 负责统一计时和进程组超时终止。安装官方 MiniZinc 包后可指定 CLI 路径；本机隔离安装路径记录在 `.tools/minizinc-path.txt`。外部模型独立穷举检查使用 `python3 scripts/check_models.py`。旧脚本 `compare_solvers.py` / `report_benchmarks.py` 仅用于复现历史报告；`benchmark_corpus.py` 保留全语料库函数诊断，不作为跨引擎主对比。
