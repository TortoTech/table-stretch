# All benchmark variants

2026-10-31 · Apple M6, 16 GiB RAM · 64 cases · 3 measurements per case.

[Featured results](benchmark-unified.md) select one implementation per family. This report retains every measured variant.

| Method | Completed | Timeout runs | P50 (ms) | P95 (ms) | PAR-2 (ms) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Pareto DP (previous version) | 64/64 | 0/192 | 2.323 | 119.904 | 19.511 |
| Pareto DP (Rust) | 64/64 | 0/192 | 2.185 | 2.492 | 2.213 |
| A* (Rust) | 64/64 | 0/192 | 2.244 | 2.487 | 2.229 |
| HTML proportional (Rust, heuristic) | 64/64 | 0/192 | 2.161 | 2.431 | — |
| CP (Gecode, column-width search) | 64/64 | 0/192 | 77.644 | 94.889 | 80.659 |
| Configuration LCG (Chuffed, mixed search) | 62/64 | 6/192 | 73.512 | 749.939 | 190.852 |
| Cell-free LCG (Chuffed, without RCSV) | 64/64 | 0/192 | 69.157 | 497.154 | 113.379 |
| Unary MIP (HiGHS) | 64/64 | 0/192 | 75.430 | 374.943 | 115.544 |
| One-hot MIP (HiGHS) | 64/64 | 0/192 | 76.843 | 302.367 | 103.067 |
| CP (Chuffed, cell-height search, no learning) | 55/64 | 27/192 | 68.005 | 1000.000 | 347.730 |
| LCG (Chuffed, cell-height search) | 64/64 | 0/192 | 68.555 | 84.008 | 69.672 |
| Cell-free LCG (Chuffed, RCSV) | 64/64 | 0/192 | 69.056 | 299.730 | 104.507 |
| Cell-free MIP (HiGHS, RCSV + unary) | 64/64 | 0/192 | 77.744 | 154.393 | 92.110 |

A completed exact run must certify optimality before the deadline. A completed case requires every measured run to finish. P50/P95 use per-case median times across all 64 cases, with timeouts capped at 1000 ms. PAR-2 averages all runs, charging twice the deadline for a timeout; the HTML heuristic is excluded from that score.

## Phase diagnostics

These medians use the same 53 cases completed by every implementation. Engine clocks and phase boundaries differ; use end-to-end times for comparisons.

Native phases, in microseconds:

| Method | Preparation | Search | Final stretch |
| --- | ---: | ---: | ---: |
| Pareto DP (previous version) | 5.792 | 42.625 | 0.333 |
| Pareto DP (Rust) | 8.708 | 1.333 | 0.125 |
| A* (Rust) | 7.125 | 6.542 | 0.250 |
| HTML proportional (Rust, heuristic) | 0.542 | 0.000 | 0.250 |

External phases, in milliseconds. Chuffed rounds search statistics to milliseconds.

| Method | Export | Compile | Initialize | Solve |
| --- | ---: | ---: | ---: | ---: |
| CP (Gecode, column-width search) | 0.073 | 39.629 | 0.610 | 0.099 |
| Configuration LCG (Chuffed, mixed search) | 0.076 | 39.480 | 1.000 | 1.000 |
| Cell-free LCG (Chuffed, without RCSV) | 0.078 | 39.248 | 0.000 | 1.000 |
| Unary MIP (HiGHS) | 0.076 | 43.881 | — | 2.400 |
| One-hot MIP (HiGHS) | 0.070 | 43.775 | — | 3.200 |
| CP (Chuffed, cell-height search, no learning) | 0.076 | 39.589 | 0.000 | 0.000 |
| LCG (Chuffed, cell-height search) | 0.079 | 39.708 | 1.000 | 0.000 |
| Cell-free LCG (Chuffed, RCSV) | 0.079 | 39.637 | 0.000 | 1.000 |
| Cell-free MIP (HiGHS, RCSV + unary) | 0.070 | 44.759 | — | 1.100 |

## Protocol

- One warmup, then serial measurements with shuffled method order, one thread, and seed 1.
- Fresh worker processes read identical curve JSON. Timing includes validation, a common feasible fallback, method-specific preparation, model compilation, solving, stretching, and output. Font shaping and curve construction are excluded.
- A parent watchdog enforces the total deadline and cleans up the entire live process tree, including solver processes in separate groups. Only output received before the deadline is accepted.
- Every layout is checked against the input curves. Certified optima are checked against reference heights. Timed-out runs retain any received feasible layout without claiming optimality.
- MiniZinc uses `-O0` because of a known [compiler regression](algorithms.md#compiler-regression). The metadata records solver versions, flags, input hashes, source hashes, and worker identity.

The current measurements replace earlier runs affected by incomplete timeout cleanup. These are project implementations on ebook-derived curves; model correspondence is documented in the [research audit](research-audit.md).

## Reproduce

```sh
python3 scripts/check_models.py
python3 scripts/benchmark_unified.py --minizinc /path/to/minizinc
python3 scripts/report_unified.py
```

To include the previous Pareto version in the same run:

```sh
git worktree add --detach .tools/pareto-before-source 104c545
cargo build --locked --release --manifest-path .tools/pareto-before-source/Cargo.toml --example unified_worker
python3 scripts/benchmark_unified.py --minizinc /path/to/minizinc --baseline-worker .tools/pareto-before-source/target/release/examples/unified_worker
python3 scripts/report_unified.py
```

The benchmark runner currently targets macOS. The committed input manifest requires no access to the local ebook library.

[Raw measurements](benchmark-unified.jsonl) · [Inputs](benchmark-unified-inputs.json) · [Statistics](benchmark-unified-summary.json) · [Algorithms](algorithms.md)
