# Native Rust benchmark

Latest run: **2026-11-01**, Apple M6, 16 GiB RAM. **1383 real ebook cases**, single thread, 3 measurements per case, 1-second limit.

Timing uses **Rust library calls in one persistent process**. Times include preparation, model construction, search, and final layout; exclude text measurement, JSON parsing, and process startup.

| Method | Completed | P50 (ms) | P95 (ms) | Extra heap P95 (KiB) | RSS P95 (KiB) |
| --- | ---: | ---: | ---: | ---: | ---: |
| **Pareto DP** | 1383/1383 | 0.002 | 0.010 | 9.39 | 2272.00 |
| A* | 1383/1383 | 0.003 | 0.016 | 17.51 | 2272.00 |
| [LCG](https://doi.org/10.1287/ijoc.2014.0637) (Pumpkin) | 1383/1383 | 0.047 | 0.432 | 265.40 | 3408.00 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (microlp) | 1383/1383 | 0.054 | 1.075 | 257.48 | 3376.00 |
| [CP](https://doi.org/10.1145/2034691.2034697) (Pumpkin) | 1367/1383 | 0.059 | 1.857 | 553.98 | 3744.00 |

One variant per exact-method family, selected by completion rate then P95. Rows are sorted by P95 time ascending. Unfinished runs count as 1 second in timing percentiles.

Memory is measured separately in fresh processes: extra live heap during solving and whole-process peak RSS. Includes observed timeout memory; completion counts above are from the timing pass.

[Memory measurement details and completion counts](benchmark-native-memory.md).

[Dataset coverage and extraction](library-coverage.md). The expanded dataset includes complete EPUB tables, rectangular bodies, and visually reviewed PDF tables.

## All variants

| Method | Completed | P50 (ms) | P95 (ms) |
| --- | ---: | ---: | ---: |
| HTML heuristic | 1383/1383 | <0.001 | <0.001 |
| **Pareto DP** | 1383/1383 | 0.002 | 0.010 |
| A* | 1383/1383 | 0.003 | 0.016 |
| [LCG](https://doi.org/10.1287/ijoc.2014.0637) (2015 cell-free, Pumpkin) | 1383/1383 | 0.047 | 0.432 |
| [LCG](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 1383/1383 | 0.065 | 0.659 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (unary, microlp) | 1383/1383 | 0.054 | 1.075 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (cell-free, microlp) | 1383/1383 | 0.055 | 1.171 |
| [CP](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 1367/1383 | 0.059 | 1.857 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (one-hot, microlp) | 1382/1383 | 0.068 | 2.403 |

HTML matched the optimum in 733/1383 cases.

Each percentile uses one median per case. Failures and timeouts are censored at the common limit, including in selection. A case completes only when every measured repetition completes. All returned layouts are checked against the original profiles and the fixed reference optimum.

## Phase medians

Medians over completed cases only; each case uses the median of its repetitions. These component medians need not sum to the total median. Solver teardown is included in search.

| Method | Prepare (ms) | Model (ms) | Search (ms) | Finalize (ms) |
| --- | ---: | ---: | ---: | ---: |
| HTML heuristic | 0.0002 | 0.0000 | 0.0000 | 0.0000 |
| **Pareto DP** | 0.0016 | 0.0000 | 0.0002 | 0.0000 |
| A* | 0.0012 | 0.0000 | 0.0016 | 0.0001 |
| [LCG](https://doi.org/10.1287/ijoc.2014.0637) (2015 cell-free, Pumpkin) | 0.0016 | 0.0172 | 0.0272 | 0.0001 |
| [LCG](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 0.0016 | 0.0199 | 0.0369 | 0.0001 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (unary, microlp) | 0.0016 | 0.0033 | 0.0485 | 0.0001 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (cell-free, microlp) | 0.0016 | 0.0038 | 0.0482 | 0.0001 |
| [CP](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 0.0016 | 0.0194 | 0.0318 | 0.0001 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (one-hot, microlp) | 0.0016 | 0.0036 | 0.0622 | 0.0001 |

## Reproduce

```sh
python3 scripts/benchmark_native.py
python3 scripts/report_native.py --without-memory
python3 scripts/benchmark_memory.py --suite ebooks
python3 scripts/report_memory.py --suite ebooks
python3 scripts/report_native.py --suite ebooks
```

One warmup per method/case precedes the measured repetitions. Method order is shuffled with seed 1. Every call creates a fresh solver; there is no reused model or cross-method incumbent. All methods share the full-call wall limit; a watchdog kills and restarts the worker if cooperative termination overruns by two seconds. Raw records preserve errors, actual elapsed times and worker generations. Count limits are disabled for this benchmark.

[Raw measurements](benchmark-native.jsonl) · [Summary](benchmark-native-summary.json) · [Inputs](benchmark-library-inputs.json) · [Model mappings](native-models.md)

The [external-solver benchmark](benchmark-unified.md) remains a separate process-level reference. Its timings include startup and MiniZinc compilation and must not be mixed with this table.
