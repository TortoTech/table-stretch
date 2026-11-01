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

| Method | Completed | P50 (ms) | P95 (ms) | Extra heap P95 (KiB) | RSS P95 (MiB) |
| --- | ---: | ---: | ---: | ---: | ---: |
| HTML heuristic | 1383/1383 | <0.001 | <0.001 | 0.176 | 2.141 |
| **Pareto DP** | 1383/1383 | 0.002 | 0.010 | 9.395 | 2.219 |
| A* | 1383/1383 | 0.003 | 0.016 | 17.512 | 2.219 |
| [LCG](https://doi.org/10.1287/ijoc.2014.0637) (Pumpkin) | 1383/1383 | 0.047 | 0.432 | 265.398 | 3.328 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (microlp) | 1383/1383 | 0.054 | 1.075 | 257.479 | 3.297 |
| [CP](https://doi.org/10.1145/2034691.2034697) (Pumpkin) | 1367/1383 | 0.059 | 1.857 | 553.984 | 3.656 |

One variant per family, selected by completion rate then P95. Rows are sorted by P95 ascending. Unfinished runs count as 1 second in timing percentiles. HTML matched the optimum in 733/1383 cases.

Memory is measured separately in fresh processes: extra live heap during solving and whole-process peak RSS. Includes observed timeout memory; completion counts above are from the timing pass.
<!-- benchmark:end -->

[Library coverage](docs/library-coverage.md) · [Benchmark report and all variants](docs/benchmark-native.md) · [Memory report](docs/benchmark-native-memory.md) · [External solver reference](docs/benchmark-unified.md)

### MiniZinc public benchmark

[MiniZinc table-layout](https://github.com/MiniZinc/minizinc-benchmarks/tree/26bcd0a78433025f7b6896a6fa8caf128795760b/table-layout): all 26 public instances, at their original container widths.

<!-- benchmark-minizinc:start -->
Latest run: **2026-11-01**, Apple M6, 16 GiB RAM. **26 MiniZinc public cases**, single thread, 3 measurements per case, 1-second limit.

Timing uses **Rust library calls in one persistent process**. Times include preparation, model construction, search, and final layout; exclude text measurement, JSON parsing, and process startup.

| Method | Completed | P50 (ms) | P95 (ms) | Extra heap P95 (KiB) | RSS P95 (MiB) |
| --- | ---: | ---: | ---: | ---: | ---: |
| HTML heuristic | 26/26 | 0.003 | 0.006 | 0.570 | 2.250 |
| A* | 26/26 | 0.246 | 0.843 | 640.637 | 2.828 |
| **Pareto DP** | 26/26 | 0.163 | 2.008 | 264.414 | 2.781 |
| [LCG](https://doi.org/10.1145/2034691.2034697) (Pumpkin) | 26/26 | 4.781 | 17.582 | 2420.348 | 6.031 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (microlp) | 26/26 | 4.448 | 26.624 | 760.180 | 4.312 |
| [CP](https://doi.org/10.1145/2034691.2034697) (Pumpkin) | 5/26 | 1000.000 | 1000.000 | 2272.547 | 5.719 |

One variant per family, selected by completion rate then P95. Rows are sorted by P95 ascending. Unfinished runs count as 1 second in timing percentiles. HTML matched the optimum in 0/26 cases.

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

[Algorithms](docs/algorithms.md) · [Mathematical proof](docs/proof.md) · [Lean proof](proof/Optimality.lean) · [Research audit](docs/research-audit.md) · [Memory optimization](docs/memory-optimization.md)

## License

MIT
