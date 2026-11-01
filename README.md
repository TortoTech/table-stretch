# table-stretch

Exact minimum-height table layout in Rust. Given a container width and cell size curves, find optimal column widths, then stretch the table to fill the container.

- Pareto dynamic programming with bound pruning and direct final-column completion.
- Rust library and JSON CLI, with A*, CP, LCG, and MIP implementations for comparison.
- Mathematical proofs, a Lean-checked abstract optimality proof, and tests from 468 real table samples across 31 books.

## Quick start

```sh
cargo run --release -- examples/table.json
```

The CLI reads a JSON file or `-` for standard input and returns column widths, row heights, and total height. Pareto DP is the default; select `--algorithm astar2011`, `html`, `cp2011`, `lcg2011`, `lcg2015`, `mip2015_unary`, `mip2015_onehot`, or `mip2015_cellfree` for alternatives. All run in Rust, without MiniZinc or external solver processes.

```rust
use table_stretch::{Column, Limits, Profile, Table, solve};

fn main() -> Result<(), table_stretch::Error> {
    let cell = Profile::from_tokens(&[4, 3, 8, 5], 1, 16)?;
    let table = Table {
        width: 30,
        reserved_width: 2,
        columns: vec![Column {
            min_width: 8,
            max_width: 40,
            cells: vec![cell],
        }],
    };
    let layout = solve(&table, Limits::default())?;
    println!("{:?}", layout.column_widths);
    Ok(())
}
```

## Benchmark

<!-- benchmark:start -->
Latest controlled run: **2026-11-01**, Apple M6, 16 GiB RAM. **1102 cases from 21 evaluation books**, single thread, 3 measurements, 1-second limit.

Algorithms are fixed using 10 validation books. This is a **retrospective grouped evaluation**: both corpora were used in earlier development. Timing includes preparation, model/search and final layout; excludes text measurement, JSON and startup.

![Benchmark results; Pareto DP outlined in blue, minima in green.](docs/assets/ablation-ebooks.svg?v=d7f449464353)

<details>
<summary>Table data and paper links</summary>

| Metric | **Pareto DP** | A* | [LCG](https://doi.org/10.1287/ijoc.2014.0637) | [MIP](https://doi.org/10.1287/ijoc.2014.0637) | [CP](https://doi.org/10.1145/2034691.2034697) |
| --- | ---: | ---: | ---: | ---: | ---: |
| P50 (ms) | $\color{green}{0.002}$ | 0.002 | 0.018 | 0.016 | 0.030 |
| P95 (ms) | $\color{green}{0.010}$ | 0.011 | 0.141 | 0.407 | 1.074 |
| Extra heap P95 (KiB) | $\color{green}{10.67}$ | 10.99 | 213.60 | 227.77 | 566.94 |
| RSS P95 (KiB) | $\color{green}{2288.00}$ | $\color{green}{2288.00}$ | 3232.00 | 3248.00 | 3728.00 |
| Completed | 1102/1102 | 1102/1102 | 1102/1102 | 1102/1102 | 1095/1102 |

</details>

Memory is measured separately in fresh processes, including observed timeout peaks. Timeout percentiles are shown as **> 1000.00 ms**. [Protocol, all ablations and performance profiles](docs/ablation-report.md).
<!-- benchmark:end -->

[Library coverage](docs/library-coverage.md) · [Controlled evaluation and ablations](docs/ablation-report.md) · [Earlier full-corpus comparison](docs/benchmark-native.md) · [External solver reference](docs/benchmark-unified.md)

### MiniZinc public benchmark

[MiniZinc table-layout](https://github.com/MiniZinc/minizinc-benchmarks/tree/26bcd0a78433025f7b6896a6fa8caf128795760b/table-layout): all 26 public instances, at their original container widths.

<!-- benchmark-minizinc:start -->
Latest controlled run: **2026-11-01**, Apple M6, 16 GiB RAM. **26 MiniZinc public cases**, single thread, 3 measurements, 1-second limit.

Algorithms are fixed using 10 validation books. This is a **retrospective grouped evaluation**: both corpora were used in earlier development. Timing includes preparation, model/search and final layout; excludes text measurement, JSON and startup.

![Benchmark results; Pareto DP outlined in blue, minima in green.](docs/assets/ablation-minizinc.svg?v=2ef594d5eeaa)

<details>
<summary>Table data and paper links</summary>

| Metric | **Pareto DP** | A* | [LCG](https://doi.org/10.1287/ijoc.2014.0637) | [MIP](https://doi.org/10.1287/ijoc.2014.0637) | [CP](https://doi.org/10.1145/2034691.2034697) |
| --- | ---: | ---: | ---: | ---: | ---: |
| P50 (ms) | 0.162 | $\color{green}{0.159}$ | 1.137 | 1.920 | > 1000.00 |
| P95 (ms) | 2.000 | $\color{green}{0.780}$ | 2.765 | 24.529 | > 1000.00 |
| Extra heap P95 (KiB) | 263.73 | $\color{green}{162.06}$ | 754.02 | 707.65 | 2120.96 |
| RSS P95 (KiB) | 2848.00 | $\color{green}{2560.00}$ | 4240.00 | 4256.00 | 5680.00 |
| Completed | 26/26 | 26/26 | 25/26 | 26/26 | 5/26 |

</details>

Memory is measured separately in fresh processes, including observed timeout peaks. Timeout percentiles are shown as **> 1000.00 ms**. [Protocol, all ablations and performance profiles](docs/ablation-report.md).
<!-- benchmark-minizinc:end -->

[Controlled evaluation and ablations](docs/ablation-report.md) · [Earlier comparison](docs/benchmark-minizinc.md) · [Source and validation](docs/minizinc-corpus.md)

## Input and guarantees

Tables are column-major, with integer layout units and complete, non-increasing cell height curves. Supply measured curves directly or build them with `Profile::from_tokens`. `reserved_width` accounts for borders and gaps.

Exact methods minimize total height within the supplied curves and column limits. MIP uses floating-point solver tolerances; the Lean proof covers the abstract Pareto algorithm. Row/column spans are not supported. Search limits return an error rather than an unproven optimum.

## Development

```sh
cargo test --locked --all-targets
bash scripts/check.sh  # Rust checks and Lean 4.19.0 proofs
```

[Algorithms](docs/algorithms.md) · [Mathematical proof](docs/proof.md) · [Lean proof](proof/Optimality.lean) · [Research audit](docs/research-audit.md) · [Memory optimization](docs/memory-optimization.md) · [Shared-bound optimization](docs/bound-optimization.md)

## License

MIT
