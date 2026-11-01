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
Latest run: **2026-11-01**, Apple M6, 16 GiB RAM. **1383 real ebook cases**, single thread, 3 measurements per case, 1-second limit.

Timing uses **Rust library calls in one persistent process**. Times include preparation, model construction, search, and final layout; exclude text measurement, JSON parsing, and process startup.

![Benchmark results; Pareto DP outlined in blue, minimum values in green. Full data below.](docs/assets/benchmark-native.svg?v=3dfa7254d786)

<details>
<summary>Table data and paper links</summary>

| Metric | **Pareto DP** | A* | [LCG](https://doi.org/10.1287/ijoc.2014.0637) | [MIP](https://doi.org/10.1287/ijoc.2014.0637) | [CP](https://doi.org/10.1145/2034691.2034697) |
| --- | ---: | ---: | ---: | ---: | ---: |
| P50 (ms) | $\color{green}{0.002}$ | 0.002 | 0.018 | 0.016 | 0.028 |
| P95 (ms) | $\color{green}{0.010}$ | 0.011 | 0.140 | 0.362 | 0.909 |
| Extra heap P95 (KiB) | 9.39 | $\color{green}{9.32}$ | 204.22 | 218.88 | 513.26 |
| RSS P95 (KiB) | $\color{green}{2224.00}$ | $\color{green}{2224.00}$ | 3168.00 | 3184.00 | 3600.00 |
| Completed | 1383/1383 | 1383/1383 | 1383/1383 | 1383/1383 | 1375/1383 |

</details>

One variant per exact-method family, selected by completion rate then P95. Timing percentiles reaching the timeout limit are shown as **> 1000.00 ms**.

Memory is measured separately in fresh processes: extra live heap during solving and whole-process peak RSS. Includes observed timeout memory; completion counts above are from the timing pass.
<!-- benchmark:end -->

[Library coverage](docs/library-coverage.md) · [Benchmark report and all variants](docs/benchmark-native.md) · [Memory report](docs/benchmark-native-memory.md) · [External solver reference](docs/benchmark-unified.md)

### MiniZinc public benchmark

[MiniZinc table-layout](https://github.com/MiniZinc/minizinc-benchmarks/tree/26bcd0a78433025f7b6896a6fa8caf128795760b/table-layout): all 26 public instances, at their original container widths.

<!-- benchmark-minizinc:start -->
Latest run: **2026-11-01**, Apple M6, 16 GiB RAM. **26 MiniZinc public cases**, single thread, 3 measurements per case, 1-second limit.

Timing uses **Rust library calls in one persistent process**. Times include preparation, model construction, search, and final layout; exclude text measurement, JSON parsing, and process startup.

![Benchmark results; Pareto DP outlined in blue, minimum values in green. Full data below.](docs/assets/benchmark-minizinc.svg?v=d95fc6de7555)

<details>
<summary>Table data and paper links</summary>

| Metric | **Pareto DP** | A* | [LCG](https://doi.org/10.1145/2034691.2034697) | [MIP](https://doi.org/10.1287/ijoc.2014.0637) | [CP](https://doi.org/10.1145/2034691.2034697) |
| --- | ---: | ---: | ---: | ---: | ---: |
| P50 (ms) | $\color{green}{0.160}$ | 0.162 | 3.884 | 1.960 | > 1000.00 |
| P95 (ms) | 1.987 | $\color{green}{0.770}$ | 10.744 | 24.733 | > 1000.00 |
| Extra heap P95 (KiB) | 264.41 | $\color{green}{162.27}$ | 2375.33 | 707.65 | 2120.96 |
| RSS P95 (KiB) | 2752.00 | $\color{green}{2512.00}$ | 6016.00 | 4256.00 | 5664.00 |
| Completed | 26/26 | 26/26 | 26/26 | 26/26 | 5/26 |

</details>

One variant per exact-method family, selected by completion rate then P95. Timing percentiles reaching the timeout limit are shown as **> 1000.00 ms**.

Memory is measured separately in fresh processes: extra live heap during solving and whole-process peak RSS. Includes observed timeout memory; completion counts above are from the timing pass.
<!-- benchmark-minizinc:end -->

[Benchmark report and all variants](docs/benchmark-minizinc.md) · [Memory report](docs/benchmark-minizinc-memory.md) · [Source and validation](docs/minizinc-corpus.md)

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
