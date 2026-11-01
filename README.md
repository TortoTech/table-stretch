# table-stretch

用 Rust 实现的**精确最小高度表格自动拉伸算法**。给定容器宽度和单元格的宽度—高度曲线，求使表格总高度最小的列宽，再在列宽上限内填满容器。

采用换行断点离散化 + Pareto 动态规划。提供 Rust 库、JSON 命令行、数学证明、Lean 4 抽象算法证明，以及从 torto 本地 EPUB 书库提取的真实表格回归样本。

现已加入 [已有研究算法](docs/algorithms.md)：Rust A*（2011）与 W3C 比例法，以及实际 Gecode CP、Chuffed CP/SAT＋LCG（2011/2015 两种模型）、HiGHS MIP（2015 unary/one-hot 两种编码）。扩大到 25 本书的 317 个表格，耗时和失败案例见 [最新对比报告](docs/benchmark.md)。

## 当前 benchmark

实测日期：2026-10-31（US/Pacific）。环境：Apple M6、16 GiB 内存、macOS 27.0、Rust 1.99.1，release 构建、单线程。

从本地书库的 **25 本 EPUB 提取 317 个真实表格**，最多 10 列、150 行，包含中文长文本；测试 **2332 个表格/宽度场景**。以下为每场景预热 1 次、测量 5 次后取中位数，再在成功场景间统计的分位数，单位均为 **ms**。

| Rust 方法 | 成功完成 | 搜索超限 | 中位耗时 | P95 | P99 | 最慢成功 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| **Pareto DP（当前默认）** | 2324/2332 | 8 | 0.005000 | 0.183167 | 1.294375 | 20.387333 |
| A* 2011（精确） | 2332/2332 | 0 | 0.002625 | 0.010166 | 0.024917 | 0.109667 |
| W3C 比例法（启发式） | 2332/2332 | 0 | 0.000167 | 0.000375 | 0.000708 | 0.001250 |

两个精确算法在共同成功的场景中最优高度一致。**这批样本中，A* 的耗时和成功率优于当前 Pareto 实现。** Pareto 的 8 个失败场景触发了 2000 万次比较上限，不是不可行，也未返回伪最优结果。比例法仅保证可行，在 **887/2332** 个场景中高度严格高于最优值。

Rust 求解耗时包含输入验证、候选预处理、搜索和最终拉伸，**不含文本尺寸曲线构造**。单表曲线构造单独测量：中位数 0.001708 ms，P95 0.039958 ms，最大 1.096625 ms。

另外选取 **同一组 64 个复杂/多样场景**，包含全部 Pareto 超限案例，对比实际外部求解器。预热 1 次、测量 3 次，单线程、搜索限时 1 秒；“最优完成”要求三次都证明最优。

| 研究模型 / 求解器 | 最优完成 | 成功场景端到端中位耗时（ms） | 引擎 solveTime 中位数（ms） |
| --- | ---: | ---: | ---: |
| 2011 CP / Gecode | 64/64 | 85.707 | 0.239 |
| 2011 CP/SAT＋LCG / Chuffed | 60/64 | 86.555 | 4.000 |
| 2015 cell-free＋LCG / Chuffed | 64/64 | 87.366 | 4.000 |
| 2015 MIP unary / HiGHS | 64/64 | 81.977 | 3.750 |
| 2015 MIP one-hot / HiGHS | 64/64 | 82.231 | 5.750 |

外部端到端耗时包括进程启动、MiniZinc 编译和求解，**不能直接与 Rust 库函数耗时解释为相同范围的算法速度**。引擎时间也不包含 Rust 求解器承担的全部预处理；Chuffed 统计精度为毫秒。各方法资源限制和成功子集不同，全部精确方法共同成功的 54 个场景另有同子集统计。外部模型统一使用 `-O0`，避开独立穷举发现的 MiniZinc 编译优化回归。

这些是**真实内容、简化词宽/CJK 字符宽模型**下的实测，不包含真实字体 shaping、CSS、EPUB 解压或 torto 绘制；不支持的合并单元格未纳入计时。不能由这批样本推断任意规模表格的实时性能。

详情与复现：[完整报告](docs/benchmark.md) · [汇总数据](docs/benchmark-summary.json) · [Rust 原始计时](docs/benchmark-rust.jsonl) · [外部求解器原始计时](docs/benchmark-external.jsonl) · [算法范围与复现命令](docs/algorithms.md)。

## 运行

```sh
cargo run --locked --release -- examples/table.json
cargo run --locked --release -- --algorithm astar2011 examples/table.json
cargo run --locked --release -- --algorithm html examples/table.json
cargo test --locked
cargo clippy --locked --all-targets -- -D warnings
cargo run --locked --release --example ebook_corpus
```

示例输出列宽 `[7, 3]`、行高 `[2, 1]`，总高度 `3`。列宽总和 `10` 加固定横向空间 `2`，恰好填满容器 `12`。相同输入若等宽分配为 `[5, 5]`，总高度为 `7`。

CLI 接受文件路径或 `-`（标准输入），成功时输出 JSON；非法输入、不可行约束或搜索超限以非零状态退出。`--help` 查看用法。

默认使用 `pareto`；`astar2011` 也是精确算法，`html` 为启发式，返回 `optimal: false`。原 Lean 证明针对 Pareto 抽象搜索，不自动涵盖新增 A* 或外部求解器。

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
- [扩大书库及全部方法耗时对比](docs/benchmark.md)；[实现范围与计时口径](docs/algorithms.md)。

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
python3 scripts/compare_solvers.py --minizinc /path/to/minizinc
python3 scripts/report_benchmarks.py
```

CP/LCG/MIP 由 MiniZinc 及实际外部求解器执行，Rust 负责统一尺寸模型导出，Python 负责实验编排。安装官方 MiniZinc 包后可指定 CLI 路径；本机隔离安装路径记录在 `.tools/minizinc-path.txt`。外部模型独立穷举检查使用 `python3 scripts/check_models.py`。
