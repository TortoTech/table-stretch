# MiniZinc public benchmark

Latest run: **2026-11-01**, Apple M6, 16 GiB RAM. **26 MiniZinc public cases**, single thread, 3 measurements per case, 1-second limit.

Timing uses **Rust library calls in one persistent process**. Times include preparation, model construction, search, and final layout; exclude text measurement, JSON parsing, and process startup.

| Method | Completed | P50 (ms) | P95 (ms) | Extra heap P95 (KiB) | RSS P95 (MiB) |
| --- | ---: | ---: | ---: | ---: | ---: |
| HTML heuristic | 26/26 | 0.003 | 0.006 | 0.570 | 2.250 |
| A* | 26/26 | 0.246 | 0.843 | 640.637 | 2.828 |
| **Pareto DP** | 26/26 | 0.163 | 2.008 | 264.414 | 2.781 |
| [LCG](https://doi.org/10.1145/2034691.2034697) (Pumpkin) | 26/26 | 4.781 | 17.582 | 2420.348 | 6.031 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (microlp) | 26/26 | 4.448 | 26.624 | 760.180 | 4.312 |
| [CP](https://doi.org/10.1145/2034691.2034697) (Pumpkin) | 5/26 | 1000.000 | 1000.000 | 2272.547 | 5.719 |

One variant per family, selected by completion rate then P95. Rows are sorted by P95 ascending. Unfinished runs count as 1 second in timing percentiles. HTML matched the optimum in 0/26 cases.

Memory is measured separately in fresh processes: extra live heap during solving and whole-process peak RSS. Includes observed timeout memory; completion counts above are from the timing pass.

[Memory measurement details and completion counts](benchmark-minizinc-memory.md).

[Source, conversion, and validation](minizinc-corpus.md). All 26 upstream table-layout instances are included at their original widths.

## All variants

| Method | Completed | P50 (ms) | P95 (ms) |
| --- | ---: | ---: | ---: |
| HTML heuristic | 26/26 | 0.003 | 0.006 |
| A* | 26/26 | 0.246 | 0.843 |
| **Pareto DP** | 26/26 | 0.163 | 2.008 |
| [LCG](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 26/26 | 4.781 | 17.582 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (cell-free, microlp) | 26/26 | 4.448 | 26.624 |
| [LCG](https://doi.org/10.1287/ijoc.2014.0637) (2015 cell-free, Pumpkin) | 18/26 | 3.910 | 1000.000 |
| [CP](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 5/26 | 1000.000 | 1000.000 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (unary, microlp) | 1/26 | 1000.000 | 1000.000 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (one-hot, microlp) | 0/26 | 1000.000 | 1000.000 |

Each percentile uses one median per case. Failures and timeouts are censored at the common limit, including in selection. A case completes only when every measured repetition completes. All returned layouts are checked against the original profiles and the fixed reference optimum.

## Phase medians

Medians over completed cases only; each case uses the median of its repetitions. These component medians need not sum to the total median. Solver teardown is included in search.

| Method | Prepare (ms) | Model (ms) | Search (ms) | Finalize (ms) |
| --- | ---: | ---: | ---: | ---: |
| HTML heuristic | 0.0019 | 0.0000 | 0.0000 | 0.0009 |
| A* | 0.0171 | 0.0000 | 0.2152 | 0.0006 |
| **Pareto DP** | 0.0200 | 0.0000 | 0.1415 | 0.0005 |
| [LCG](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 0.0221 | 0.2350 | 4.5487 | 0.0019 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (cell-free, microlp) | 0.0198 | 0.0256 | 4.3920 | 0.0018 |
| [LCG](https://doi.org/10.1287/ijoc.2014.0637) (2015 cell-free, Pumpkin) | 0.0202 | 0.1397 | 2.3461 | 0.0016 |
| [CP](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 0.0165 | 0.1683 | 219.4429 | 0.0017 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (unary, microlp) | 0.0222 | 0.0229 | 643.7144 | 0.0020 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (one-hot, microlp) | — | — | — | — |

## Reproduce

```sh
python3 scripts/build_minizinc_inputs.py
python3 scripts/benchmark_native.py --inputs docs/benchmark-minizinc-inputs.json --output docs/benchmark-minizinc.jsonl
python3 scripts/report_native.py --suite minizinc --without-memory
python3 scripts/benchmark_memory.py --suite minizinc
python3 scripts/report_memory.py --suite minizinc
python3 scripts/report_native.py --suite minizinc
```

One warmup per method/case precedes the measured repetitions. Method order is shuffled with seed 1. Every call creates a fresh solver; there is no reused model or cross-method incumbent. All methods share the full-call wall limit; a watchdog kills and restarts the worker if cooperative termination overruns by two seconds. Raw records preserve errors, actual elapsed times and worker generations. Count limits are disabled for this benchmark.

[Raw measurements](benchmark-minizinc.jsonl) · [Summary](benchmark-minizinc-summary.json) · [Inputs](benchmark-minizinc-inputs.json) · [Model mappings](native-models.md)

The [external-solver benchmark](benchmark-unified.md) remains a separate process-level reference. Its timings include startup and MiniZinc compilation and must not be mixed with this table.
