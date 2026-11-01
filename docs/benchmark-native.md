# Native Rust benchmark

Latest run: **2026-11-01**, Apple M6, 16 GiB RAM. **1383 real ebook cases**, single thread, 3 measurements per case, 1-second limit.

All methods run as **Rust library calls in one process**. Times include preparation, model construction, search, and final layout; exclude text measurement, JSON parsing, and process startup.

| Method | Completed | P50 (ms) | P95 (ms) |
| --- | ---: | ---: | ---: |
| HTML heuristic | 1383/1383 | <0.001 | <0.001 |
| **Pareto DP** | 1383/1383 | 0.002 | 0.011 |
| A* | 1383/1383 | 0.003 | 0.017 |
| [LCG](https://doi.org/10.1287/ijoc.2014.0637) (Pumpkin) | 1383/1383 | 0.061 | 0.514 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (microlp) | 1383/1383 | 0.063 | 1.155 |
| [CP](https://doi.org/10.1145/2034691.2034697) (Pumpkin) | 1367/1383 | 0.081 | 2.079 |

One variant per family, selected by completion rate then P95. Rows are sorted by P95 ascending. Unfinished runs count as 1 second in these percentiles. HTML matched the optimum in 733/1383 cases.

[Dataset coverage and extraction](library-coverage.md). The expanded dataset includes complete EPUB tables, rectangular bodies, and visually reviewed PDF tables.

## All variants

| Method | Completed | P50 (ms) | P95 (ms) |
| --- | ---: | ---: | ---: |
| HTML heuristic | 1383/1383 | <0.001 | <0.001 |
| **Pareto DP** | 1383/1383 | 0.002 | 0.011 |
| A* | 1383/1383 | 0.003 | 0.017 |
| [LCG](https://doi.org/10.1287/ijoc.2014.0637) (2015 cell-free, Pumpkin) | 1383/1383 | 0.061 | 0.514 |
| [LCG](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 1383/1383 | 0.088 | 0.831 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (unary, microlp) | 1383/1383 | 0.063 | 1.155 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (cell-free, microlp) | 1383/1383 | 0.059 | 1.164 |
| [CP](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 1367/1383 | 0.081 | 2.079 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (one-hot, microlp) | 1379/1383 | 0.081 | 2.757 |

Each percentile uses one median per case. Failures and timeouts are censored at the common limit, including in selection. A case completes only when every measured repetition completes. All returned layouts are checked against the original profiles and the fixed reference optimum.

## Phase medians

Medians over completed cases only; each case uses the median of its repetitions. These component medians need not sum to the total median. Solver teardown is included in search.

| Method | Prepare (ms) | Model (ms) | Search (ms) | Finalize (ms) |
| --- | ---: | ---: | ---: | ---: |
| HTML heuristic | 0.0002 | 0.0000 | 0.0000 | 0.0000 |
| **Pareto DP** | 0.0017 | 0.0000 | 0.0002 | 0.0000 |
| A* | 0.0013 | 0.0000 | 0.0017 | 0.0001 |
| [LCG](https://doi.org/10.1287/ijoc.2014.0637) (2015 cell-free, Pumpkin) | 0.0016 | 0.0248 | 0.0333 | 0.0001 |
| [LCG](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 0.0017 | 0.0300 | 0.0549 | 0.0001 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (unary, microlp) | 0.0016 | 0.0044 | 0.0563 | 0.0001 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (cell-free, microlp) | 0.0017 | 0.0050 | 0.0508 | 0.0001 |
| [CP](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 0.0016 | 0.0295 | 0.0460 | 0.0001 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (one-hot, microlp) | 0.0016 | 0.0057 | 0.0727 | 0.0001 |

## Reproduce

```sh
python3 scripts/benchmark_native.py
python3 scripts/report_native.py
```

One warmup per method/case precedes the measured repetitions. Method order is shuffled with seed 1. Every call creates a fresh solver; there is no reused model or cross-method incumbent. All methods share the full-call wall limit; a watchdog kills and restarts the worker if cooperative termination overruns by two seconds. Raw records preserve errors, actual elapsed times and worker generations. Count limits are disabled for this benchmark.

[Raw measurements](benchmark-native.jsonl) · [Summary](benchmark-native-summary.json) · [Inputs](benchmark-library-inputs.json) · [Model mappings](native-models.md)

The [external-solver benchmark](benchmark-unified.md) remains a separate process-level reference. Its timings include startup and MiniZinc compilation and must not be mixed with this table.
