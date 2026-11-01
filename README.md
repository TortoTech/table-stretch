# table-stretch

Exact minimum-height table layout in Rust. Given a container width and cell size curves, find optimal column widths, then stretch the table to fill the container.

- Pareto dynamic programming with bound pruning and direct final-column completion.
- Rust library and JSON CLI, with A*, CP, LCG, and MIP implementations for comparison.
- Mathematical proofs, a Lean-checked abstract optimality proof, and tests from 317 real ebook tables.

## Quick start

```sh
cargo run --release -- examples/table.json
```

The CLI reads a JSON file or `-` for standard input and returns column widths, row heights, and total height. Pareto DP is the default; select `--algorithm astar2011` or `--algorithm html` for alternatives.

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

One variant per family, selected by completion rate, then lowest P95. Times cover the full process from precomputed size curves to layout, including startup and model compilation.

| Method | Completed | P50 (ms) | P95 (ms) |
| --- | ---: | ---: | ---: |
| Pareto DP (Rust) | 64/64 | 2.185 | 2.492 |
| A* (Rust) | 64/64 | 2.244 | 2.487 |
| HTML heuristic (Rust) | 64/64 | 2.161 | 2.431 |
| CP (Gecode) | 64/64 | 77.644 | 94.889 |
| LCG (Chuffed) | 64/64 | 68.555 | 84.008 |
| MIP (HiGHS) | 64/64 | 77.744 | 154.393 |

Exact methods certify the minimum height. The HTML heuristic matched the optimum in 30/64 cases.
<!-- benchmark:end -->

[Benchmark report](docs/benchmark-unified.md) · [All variants and measurements](docs/benchmark-unified-details.md)

## Input and guarantees

Tables are column-major, with integer layout units and complete, non-increasing cell height curves. Supply measured curves directly or build them with `Profile::from_tokens`. `reserved_width` accounts for borders and gaps.

Exact solvers minimize total height within the supplied curves and column limits. Row/column spans are not supported. Search limits return an error rather than an unproven optimum.

## Development

```sh
cargo test --locked --all-targets
bash scripts/check.sh  # Rust checks and Lean 4.19.0 proofs
```

[Algorithms](docs/algorithms.md) · [Mathematical proof](docs/proof.md) · [Lean proof](proof/Optimality.lean) · [Research audit](docs/research-audit.md)

## License

MIT
