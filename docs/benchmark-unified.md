# External solver reference

The primary comparison is now the [native Rust benchmark](benchmark-native.md). The archived results below include process startup and MiniZinc compilation.

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

Exact runs report solver-certified optimality (MIP uses floating-point tolerances). The HTML heuristic matched the optimum in 30/64 cases.

The cases are drawn from 317 tables in 25 ebooks. Quantiles use each case's median runtime. All methods receive identical inputs and share the same end-to-end deadline.

## Reproduce

```sh
python3 scripts/benchmark_unified.py --minizinc /path/to/minizinc
python3 scripts/report_unified.py
```

[All variants and phase timings](benchmark-unified-details.md) · [Raw measurements](benchmark-unified.jsonl) · [Inputs](benchmark-unified-inputs.json) · [Summary](benchmark-unified-summary.json)
