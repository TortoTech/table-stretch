# MiniZinc public benchmark

Latest run: **2026-11-01**, Apple M6, 16 GiB RAM. **26 MiniZinc public cases**, single thread, 3 measurements per case, 1-second limit.

Timing uses **Rust library calls in one persistent process**. Times include preparation, model construction, search, and final layout; exclude text measurement, JSON parsing, and process startup.

| Method | Completed | P50 (ms) | P95 (ms) | Extra heap P95 (KiB) | RSS P95 (MiB) |
| --- | ---: | ---: | ---: | ---: | ---: |
| HTML heuristic | 26/26 | 0.003 | 0.007 | 0.570 | 2.250 |
| A* | 26/26 | 0.260 | 0.875 | 640.637 | 2.828 |
| **Pareto DP** | 26/26 | 0.159 | 1.991 | 264.414 | 2.734 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (microlp) | 26/26 | 4.293 | 26.629 | 792.184 | 4.266 |
| [LCG](https://doi.org/10.1145/2034691.2034697) (Pumpkin) | 26/26 | 14.525 | 37.895 | 12943.137 | 16.172 |
| [CP](https://doi.org/10.1145/2034691.2034697) (Pumpkin) | 5/26 | 1000.000 | 1000.000 | 9217.203 | 14.469 |

One variant per family, selected by completion rate then P95. Rows are sorted by P95 ascending. Unfinished runs count as 1 second in timing percentiles. HTML matched the optimum in 0/26 cases.

Memory is measured separately in fresh processes: extra live heap during solving and whole-process peak RSS. Includes observed timeout memory; completion counts above are from the timing pass.

[Memory measurement details and completion counts](benchmark-minizinc-memory.md).

[Source, conversion, and validation](minizinc-corpus.md). All 26 upstream table-layout instances are included at their original widths.

## All variants

| Method | Completed | P50 (ms) | P95 (ms) |
| --- | ---: | ---: | ---: |
| HTML heuristic | 26/26 | 0.003 | 0.007 |
| A* | 26/26 | 0.260 | 0.875 |
| **Pareto DP** | 26/26 | 0.159 | 1.991 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (cell-free, microlp) | 26/26 | 4.293 | 26.629 |
| [LCG](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 26/26 | 14.525 | 37.895 |
| [LCG](https://doi.org/10.1287/ijoc.2014.0637) (2015 cell-free, Pumpkin) | 22/26 | 9.868 | 1000.000 |
| [CP](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 5/26 | 1000.000 | 1000.000 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (unary, microlp) | 1/26 | 1000.000 | 1000.000 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (one-hot, microlp) | 0/26 | 1000.000 | 1000.000 |

Each percentile uses one median per case. Failures and timeouts are censored at the common limit, including in selection. A case completes only when every measured repetition completes. All returned layouts are checked against the original profiles and the fixed reference optimum.

## Phase medians

Medians over completed cases only; each case uses the median of its repetitions. These component medians need not sum to the total median. Solver teardown is included in search.

| Method | Prepare (ms) | Model (ms) | Search (ms) | Finalize (ms) |
| --- | ---: | ---: | ---: | ---: |
| HTML heuristic | 0.0020 | 0.0000 | 0.0000 | 0.0008 |
| A* | 0.0166 | 0.0000 | 0.2272 | 0.0006 |
| **Pareto DP** | 0.0201 | 0.0000 | 0.1402 | 0.0005 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (cell-free, microlp) | 0.0191 | 0.0299 | 4.2346 | 0.0018 |
| [LCG](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 0.0211 | 0.4447 | 14.0241 | 0.0019 |
| [LCG](https://doi.org/10.1287/ijoc.2014.0637) (2015 cell-free, Pumpkin) | 0.0201 | 0.4009 | 7.3867 | 0.0018 |
| [CP](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 0.0165 | 0.4081 | 252.7725 | 0.0018 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (unary, microlp) | 0.0177 | 0.0300 | 953.6810 | 0.0018 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (one-hot, microlp) | — | — | — | — |

## Reproduce

```sh
python3 scripts/build_minizinc_inputs.py
python3 scripts/benchmark_native.py --inputs docs/benchmark-minizinc-inputs.json --output docs/benchmark-minizinc.jsonl
python3 scripts/report_native.py --suite minizinc
```

One warmup per method/case precedes the measured repetitions. Method order is shuffled with seed 1. Every call creates a fresh solver; there is no reused model or cross-method incumbent. All methods share the full-call wall limit; a watchdog kills and restarts the worker if cooperative termination overruns by two seconds. Raw records preserve errors, actual elapsed times and worker generations. Count limits are disabled for this benchmark.

[Raw measurements](benchmark-minizinc.jsonl) · [Summary](benchmark-minizinc-summary.json) · [Inputs](benchmark-minizinc-inputs.json) · [Model mappings](native-models.md)

The [external-solver benchmark](benchmark-unified.md) remains a separate process-level reference. Its timings include startup and MiniZinc compilation and must not be mixed with this table.
