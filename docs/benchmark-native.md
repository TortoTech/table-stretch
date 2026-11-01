# Native Rust benchmark

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

## All variants

| Method | Completed | P50 (ms) | P95 (ms) |
| --- | ---: | ---: | ---: |
| Pareto DP | 64/64 | 0.009 | 0.051 |
| A* | 64/64 | 0.014 | 0.078 |
| HTML heuristic | 64/64 | 0.001 | 0.002 |
| CP (2011, Pumpkin) | 58/64 | 0.568 | 1000.000 |
| LCG (2011, Pumpkin) | 64/64 | 0.536 | 11.535 |
| LCG (2015 cell-free, Pumpkin) | 64/64 | 0.415 | 8.427 |
| MIP (unary, microlp) | 64/64 | 0.558 | 36.472 |
| MIP (one-hot, microlp) | 62/64 | 0.788 | 277.103 |
| MIP (cell-free, microlp) | 64/64 | 0.607 | 22.635 |

Each percentile uses one median per case. Failures and timeouts are censored at the common limit, including in selection. A case completes only when every measured repetition completes. All returned layouts are checked against the original profiles and the fixed reference optimum.

## Phase medians

Medians over completed cases only; each case uses the median of its repetitions. These component medians need not sum to the total median. Solver teardown is included in search.

| Method | Prepare (ms) | Model (ms) | Search (ms) | Finalize (ms) |
| --- | ---: | ---: | ---: | ---: |
| Pareto DP | 0.0066 | 0.0000 | 0.0008 | 0.0001 |
| A* | 0.0057 | 0.0000 | 0.0065 | 0.0001 |
| HTML heuristic | 0.0004 | 0.0000 | 0.0000 | 0.0001 |
| CP (2011, Pumpkin) | 0.0050 | 0.0920 | 0.2643 | 0.0003 |
| LCG (2011, Pumpkin) | 0.0055 | 0.1028 | 0.3631 | 0.0003 |
| LCG (2015 cell-free, Pumpkin) | 0.0053 | 0.0909 | 0.3109 | 0.0003 |
| MIP (unary, microlp) | 0.0054 | 0.0141 | 0.5384 | 0.0003 |
| MIP (one-hot, microlp) | 0.0051 | 0.0195 | 0.7183 | 0.0003 |
| MIP (cell-free, microlp) | 0.0054 | 0.0178 | 0.5453 | 0.0003 |

## Reproduce

```sh
python3 scripts/benchmark_native.py
python3 scripts/report_native.py
```

One warmup per method/case precedes the measured repetitions. Method order is shuffled with seed 1. Every call creates a fresh solver; there is no reused model or cross-method incumbent. All methods share the full-call wall limit; a watchdog kills and restarts the worker if cooperative termination overruns by two seconds. Raw records preserve errors, actual elapsed times and worker generations. Count limits are disabled for this benchmark.

[Raw measurements](benchmark-native.jsonl) · [Summary](benchmark-native-summary.json) · [Inputs](benchmark-unified-inputs.json) · [Model mappings](native-models.md)

The [external-solver benchmark](benchmark-unified.md) remains a separate process-level reference. Its timings include startup and MiniZinc compilation and must not be mixed with this table.
