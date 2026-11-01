# Native Rust benchmark

Latest run: **2026-11-01**, Apple M6, 16 GiB RAM. **1383 real ebook cases**, single thread, 3 measurements per case, 1-second limit.

Timing uses **Rust library calls in one persistent process**. Times include preparation, model construction, search, and final layout; exclude text measurement, JSON parsing, and process startup.

![Benchmark results; Pareto DP outlined in blue, minimum values in green. Full data below.](assets/benchmark-native.svg?v=3dfa7254d786)

<details>
<summary>Table data and paper links</summary>

| Metric | **Pareto DP** | A* | [LCG](https://doi.org/10.1287/ijoc.2014.0637) | [MIP](https://doi.org/10.1287/ijoc.2014.0637) | [CP](https://doi.org/10.1145/2034691.2034697) |
| --- | ---: | ---: | ---: | ---: | ---: |
| P50 (ms) | $\color{green}{0.002}$ | 0.002 | 0.018 | 0.016 | 0.028 |
| P95 (ms) | $\color{green}{0.010}$ | 0.011 | 0.140 | 0.362 | 0.909 |
| Extra heap P95 (KiB) | 9.39 | $\color{green}{9.32}$ | 204.22 | 218.88 | 513.26 |
| RSS P95 (KiB) | $\color{green}{2224.00}$ | $\color{green}{2224.00}$ | 3168.00 | 3184.00 | 3600.00 |
| Completed | 1383/1383 | 1383/1383 | 1383/1383 | 1383/1383 | 1375/1383 |

</details>

One variant per exact-method family, selected by completion rate then P95. Timing percentiles reaching the timeout limit are shown as **> 1000.00 ms**.

Memory is measured separately in fresh processes: extra live heap during solving and whole-process peak RSS. Includes observed timeout memory; completion counts above are from the timing pass.

[Memory measurement details and completion counts](benchmark-native-memory.md).

[Dataset coverage and extraction](library-coverage.md). The expanded dataset includes complete EPUB tables, rectangular bodies, and visually reviewed PDF tables.

## All variants

| Method | Completed | P50 (ms) | P95 (ms) |
| --- | ---: | ---: | ---: |
| HTML heuristic | 1383/1383 | <0.001 | <0.001 |
| **Pareto DP** | 1383/1383 | 0.002 | 0.010 |
| A* | 1383/1383 | 0.002 | 0.011 |
| [LCG](https://doi.org/10.1287/ijoc.2014.0637) (2015 cell-free, Pumpkin) | 1383/1383 | 0.018 | 0.140 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (cell-free, microlp) | 1383/1383 | 0.016 | 0.362 |
| [LCG](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 1383/1383 | 0.030 | 0.383 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (unary, microlp) | 1383/1383 | 0.025 | 0.791 |
| [CP](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 1375/1383 | 0.028 | 0.909 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (one-hot, microlp) | 1383/1383 | 0.031 | 1.462 |

HTML matched the optimum in 733/1383 cases.

Each percentile uses one median per case. Failures and timeouts are censored at the common limit, including in selection. A case completes only when every measured repetition completes. All returned layouts are checked against the original profiles and the fixed reference optimum.

## Phase medians

Medians over completed cases only; each case uses the median of its repetitions. These component medians need not sum to the total median. Solver teardown is included in search.

| Method | Prepare (ms) | Model (ms) | Search (ms) | Finalize (ms) |
| --- | ---: | ---: | ---: | ---: |
| HTML heuristic | 0.0002 | 0.0000 | 0.0000 | 0.0000 |
| **Pareto DP** | 0.0015 | 0.0000 | 0.0002 | 0.0000 |
| A* | 0.0016 | 0.0000 | 0.0002 | 0.0000 |
| [LCG](https://doi.org/10.1287/ijoc.2014.0637) (2015 cell-free, Pumpkin) | 0.0019 | 0.0080 | 0.0077 | 0.0001 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (cell-free, microlp) | 0.0019 | 0.0019 | 0.0122 | 0.0001 |
| [LCG](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 0.0019 | 0.0105 | 0.0173 | 0.0001 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (unary, microlp) | 0.0019 | 0.0018 | 0.0207 | 0.0001 |
| [CP](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 0.0019 | 0.0103 | 0.0153 | 0.0001 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (one-hot, microlp) | 0.0019 | 0.0020 | 0.0272 | 0.0001 |

## Reproduce

```sh
python3 scripts/benchmark_native.py
python3 scripts/report_native.py --without-memory
python3 scripts/benchmark_memory.py --suite ebooks
python3 scripts/report_memory.py --suite ebooks
python3 scripts/report_native.py --suite ebooks
```

One warmup per method/case precedes the measured repetitions. Method order is shuffled with seed 1. Each call prepares its input independently and creates a fresh solver when needed; there is no reused model or cross-method incumbent. Shared bounds can certify an optimum before a backend is built, and this preparation is timed. All methods share the full-call wall limit; a watchdog kills and restarts the worker if cooperative termination overruns by two seconds. Raw records preserve errors, actual elapsed times and worker generations. Count limits are disabled for this benchmark.

[Raw measurements](benchmark-native.jsonl) · [Summary](benchmark-native-summary.json) · [Inputs](benchmark-library-inputs.json) · [Model mappings](native-models.md)

The [external-solver benchmark](benchmark-unified.md) remains a separate process-level reference. Its timings include startup and MiniZinc compilation and must not be mixed with this table.
