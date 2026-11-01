# Algorithms

All exact methods minimize total row height under a shared width budget and column limits, then stretch the result to fill the container. Inputs are complete cell size curves for rectangular tables without spans.

| Family | Featured implementation | Approach |
| --- | --- | --- |
| Pareto DP | Rust | Column-wise Pareto frontiers, lower/upper bounds, direct final-column completion. |
| A* | Rust | Best-first search with a remaining-area lower bound and column-minimality pruning. |
| HTML | Rust | Proportional width allocation; a fast heuristic. |
| CP | Gecode | Cell configuration indices and element constraints. |
| CP/SAT (LCG) | Chuffed | Cell-height sequential search with lazy clause generation. |
| MIP | HiGHS | Cell-free model with shared unary row/column selectors and RCSV domains. |

The [benchmark](benchmark-unified.md) features the fastest fully solved variant in each family from the latest run. Additional variants remain in `models/` and the [complete results](benchmark-unified-details.md).

## Research

A* and configuration CP follow [Gange et al. (2011)](https://doi.org/10.1145/2034691.2034697). Cell-free, unary, and RCSV models follow [Bilauca et al. (2015)](https://doi.org/10.1287/ijoc.2014.0637). The proportional baseline follows [W3C HTML autolayout](https://www.w3.org/MarkUp/html3-tables/sizing.html).

These are adaptations for this project's input model and current solvers. The [research audit](research-audit.md) records the model and search choices. The [mathematical proof](proof.md) and [Lean development](../proof/Optimality.lean) cover the abstract Pareto algorithm.

## Run and validate

```sh
cargo run --release -- --algorithm astar2011 examples/table.json
cargo run --release -- --algorithm html examples/table.json
python3 scripts/check_models.py
python3 scripts/benchmark_unified.py --minizinc /path/to/minizinc
python3 scripts/report_unified.py
```

The external models use MiniZinc with Gecode, Chuffed, and HiGHS. Exact commands and solver versions are recorded in the benchmark metadata. Nine external configurations pass 144 checks against independent exhaustive integer-width enumeration.

## Compiler regression

MiniZinc 2.10.1 optimization can produce an incorrect result for `tests/fixtures/minizinc-unary-regression.json`: height 3 instead of 6. Benchmarks use `-O0` to preserve correctness; the regression is included in the model checks.
