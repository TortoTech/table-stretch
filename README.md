# table-stretch

Exact minimum-height table layout in Rust. Given a container width and cell size curves, find optimal column widths, then stretch the table to fill the container.

- Pareto dynamic programming with bound pruning and direct final-column completion.
- Rust library and JSON CLI, with A*, CP, LCG, and MIP implementations for comparison.
- Mathematical proofs, a Lean-checked abstract optimality proof, and tests from 317 real ebook tables.

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
Latest run: **2026-10-31**, Apple M6, 16 GiB RAM. **64 real ebook cases**, single thread, 3 measurements per case, 1-second limit.

All methods run as **Rust library calls in one process**. Times include preparation, model construction, search, and final layout; exclude text measurement, JSON parsing, and process startup.

| Method | Completed | P50 (ms) | P95 (ms) |
| --- | ---: | ---: | ---: |
| Pareto DP | 64/64 | 0.009 | 0.051 |
| A* | 64/64 | 0.014 | 0.078 |
| HTML heuristic | 64/64 | 0.001 | 0.002 |
| CP (Pumpkin) | 58/64 | 0.568 | 1000.000 |
| LCG (Pumpkin) | 64/64 | 0.415 | 8.427 |
| MIP (microlp) | 64/64 | 0.607 | 22.635 |

Fastest variant per family, ranked by completion rate then P95. Unfinished runs count as 1 second in these percentiles. HTML matched the optimum in 30/64 cases.
<!-- benchmark:end -->

[Benchmark report and all variants](docs/benchmark-native.md) · [External solver reference](docs/benchmark-unified.md)

## Input and guarantees

Tables are column-major, with integer layout units and complete, non-increasing cell height curves. Supply measured curves directly or build them with `Profile::from_tokens`. `reserved_width` accounts for borders and gaps.

Exact methods minimize total height within the supplied curves and column limits. MIP uses floating-point solver tolerances; the Lean proof covers the abstract Pareto algorithm. Row/column spans are not supported. Search limits return an error rather than an unproven optimum.

## Development

```sh
cargo test --locked --all-targets
bash scripts/check.sh  # Rust checks and Lean 4.19.0 proofs
```

[Algorithms](docs/algorithms.md) · [Mathematical proof](docs/proof.md) · [Lean proof](proof/Optimality.lean) · [Research audit](docs/research-audit.md)

## License

MIT
