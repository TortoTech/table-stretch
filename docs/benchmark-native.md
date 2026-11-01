# Native Rust benchmark

Latest run: **2026-10-31**, Apple M6, 16 GiB RAM. **64 real ebook cases**, single thread, 3 measurements per case, 1-second limit.

All methods run as **Rust library calls in one process**. Times include preparation, model construction, search, and final layout; exclude text measurement, JSON parsing, and process startup.

| Method | Completed | P50 (ms) | P95 (ms) |
| --- | ---: | ---: | ---: |
| Pareto DP | 64/64 | 0.009 | 0.040 |
| A* | 64/64 | 0.012 | 0.074 |
| HTML heuristic | 64/64 | 0.001 | 0.002 |
| CP (Pumpkin) | 58/64 | 0.559 | 1000.000 |
| LCG (Pumpkin) | 64/64 | 0.416 | 8.344 |
| MIP (microlp) | 64/64 | 0.591 | 22.387 |

Fastest variant per family, ranked by completion rate then P95. Unfinished runs count as 1 second in these percentiles. HTML matched the optimum in 30/64 cases.

## All variants

| Method | Completed | P50 (ms) | P95 (ms) |
| --- | ---: | ---: | ---: |
| Pareto DP | 64/64 | 0.009 | 0.040 |
| A* | 64/64 | 0.012 | 0.074 |
| HTML heuristic | 64/64 | 0.001 | 0.002 |
| CP (2011, Pumpkin) | 58/64 | 0.559 | 1000.000 |
| LCG (2011, Pumpkin) | 64/64 | 0.527 | 11.543 |
| LCG (2015 cell-free, Pumpkin) | 64/64 | 0.416 | 8.344 |
| MIP (unary, microlp) | 64/64 | 0.545 | 36.464 |
| MIP (one-hot, microlp) | 62/64 | 0.802 | 276.990 |
| MIP (cell-free, microlp) | 64/64 | 0.591 | 22.387 |

Each percentile uses one median per case. Failures and timeouts are censored at the common limit, including in selection. A case completes only when every measured repetition completes. All returned layouts are checked against the original profiles and the fixed reference optimum.

## Phase medians

Medians over completed cases only; each case uses the median of its repetitions. These component medians need not sum to the total median. Solver teardown is included in search.

| Method | Prepare (ms) | Model (ms) | Search (ms) | Finalize (ms) |
| --- | ---: | ---: | ---: | ---: |
| Pareto DP | 0.0064 | 0.0000 | 0.0010 | 0.0001 |
| A* | 0.0053 | 0.0000 | 0.0060 | 0.0001 |
| HTML heuristic | 0.0005 | 0.0000 | 0.0000 | 0.0001 |
| CP (2011, Pumpkin) | 0.0050 | 0.0877 | 0.2605 | 0.0002 |
| LCG (2011, Pumpkin) | 0.0055 | 0.1007 | 0.3610 | 0.0003 |
| LCG (2015 cell-free, Pumpkin) | 0.0056 | 0.0912 | 0.3034 | 0.0003 |
| MIP (unary, microlp) | 0.0054 | 0.0143 | 0.5257 | 0.0003 |
| MIP (one-hot, microlp) | 0.0051 | 0.0196 | 0.7143 | 0.0003 |
| MIP (cell-free, microlp) | 0.0052 | 0.0179 | 0.5417 | 0.0003 |

## Reproduce

```sh
python3 scripts/benchmark_native.py
python3 scripts/report_native.py
```

One warmup per method/case precedes the measured repetitions. Method order is shuffled with seed 1. Every call creates a fresh solver; there is no reused model or cross-method incumbent. All methods share the full-call wall limit; a watchdog kills and restarts the worker if cooperative termination overruns by two seconds. Raw records preserve errors, actual elapsed times and worker generations. Count limits are disabled for this benchmark.

[Raw measurements](benchmark-native.jsonl) · [Summary](benchmark-native-summary.json) · [Inputs](benchmark-unified-inputs.json) · [Model mappings](native-models.md)

The [external-solver benchmark](benchmark-unified.md) remains a separate process-level reference. Its timings include startup and MiniZinc compilation and must not be mixed with this table.
