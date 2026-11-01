# Algorithms

All exact methods minimize total row height under a shared width budget and column limits, then stretch the result to fill the container. Inputs are complete cell size curves for rectangular tables without spans.

| Family | Featured implementation | Approach |
| --- | --- | --- |
| Pareto DP | Rust | Column-wise Pareto frontiers, lower/upper bounds, direct final-column completion. |
| A* | Rust | Best-first search with a feasible incumbent, area/floor bounds, column-minimality pruning, direct final-column completion and parent links. |
| HTML | Rust | Proportional width allocation; a fast heuristic. |
| CP | Rust / Pumpkin | Cell configuration indices and element constraints, learning disabled. |
| CP/SAT (LCG) | Rust / Pumpkin | Configuration and cell-free models with lazy clause generation. |
| MIP | Rust / microlp | Unary, one-hot, and shared cell-free encodings; LP and branch-and-bound. |

The [native benchmark](benchmark-native.md) compares all methods as Rust library calls and features one variant per family, ranked by completion rate then P95. See [native model mappings and correctness](native-models.md). External MiniZinc implementations remain in `models/` and the separate [process-level reference](benchmark-unified.md).

## Bounds shared with other exact methods

Pareto DP and A* use the same suffix area/floor bound implementation. Both initialize an upper bound from the proportional heuristic, clip column options against other columns' mandatory widths, and prune any prefix whose lower bound reaches that upper bound. A* retains best-first order and the original column-minimality rule; it does not add a Pareto frontier. Queue entries store parent links instead of complete width vectors.

Completing the final column at its maximum feasible width is optimal for that prefix because cell heights are non-increasing. In A* this completion only updates the incumbent: the solver continues until OPEN is empty or its minimum lower bound cannot improve the incumbent. Finding the first complete layout is not sufficient. Bounds that stop accumulating at the incumbent are used only to reject a node; every queued node retains its full lower bound.

Worst-case search remains exponential. Parent links remove per-node width-vector copying, but the path arena retains accepted ancestors until the search ends; this does not guarantee a lower peak on every input. Bounds and domain reductions can also change propagation order and search traces. Runtime, memory and completion are therefore measured independently.

CP, LCG and MIP use an independently computed root area/floor bound and the same proportional feasible solution. They restrict the model to heights no worse than that solution, and can certify it immediately when the bounds meet. Otherwise their original engines, encodings and branching rules remain in use. Preparation, including the heuristic and any direct certificate, is timed for every method. These implementations are enhanced adaptations, not unmodified historical algorithms. [Model reductions and correctness](native-models.md#objective-bounds).

The existing abstract Lean bound and terminal-column lemmas justify the individual reductions. A* queue/path handling and solver model construction are validated against independent exhaustive and fixed corpus optima; they are not end-to-end Lean-verified implementations.

## Research

A* and configuration CP follow [Gange et al. (2011)](https://doi.org/10.1145/2034691.2034697). Cell-free, unary, and RCSV models follow [Bilauca et al. (2015)](https://doi.org/10.1287/ijoc.2014.0637). The proportional baseline follows [W3C HTML autolayout](https://www.w3.org/MarkUp/html3-tables/sizing.html).

These are adaptations for this project's input model and current solvers. The [research audit](research-audit.md) records the model and search choices. The [mathematical proof](proof.md) and [Lean development](../proof/Optimality.lean) cover the abstract Pareto algorithm.

## Run and validate

```sh
cargo run --release -- --algorithm astar2011 examples/table.json
cargo run --release -- --algorithm lcg2015 examples/table.json
python3 scripts/benchmark_native.py
python3 scripts/report_native.py
python3 scripts/check_models.py
python3 scripts/benchmark_unified.py --minizinc /path/to/minizinc
python3 scripts/report_unified.py
```

The external models use MiniZinc with Gecode, Chuffed, and HiGHS. Exact commands and solver versions are recorded in the benchmark metadata. Nine external configurations pass 144 checks against independent exhaustive integer-width enumeration.

## Compiler regression

MiniZinc 2.10.1 optimization can produce an incorrect result for `tests/fixtures/minizinc-unary-regression.json`: height 3 instead of 6. Benchmarks use `-O0` to preserve correctness; the regression is included in the model checks.
