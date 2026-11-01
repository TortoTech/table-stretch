# MiniZinc public benchmark

Latest run: **2026-11-01**, Apple M6, 16 GiB RAM. **26 MiniZinc public cases**, single thread, 3 measurements per case, 1-second limit.

Timing uses **Rust library calls in one persistent process**. Times include preparation, model construction, search, and final layout; exclude text measurement, JSON parsing, and process startup.

![Benchmark results; Pareto DP outlined in blue, minimum values in green. Full data below.](assets/benchmark-minizinc.svg?v=a7583ed1dfcc)

<details>
<summary>Table data and paper links</summary>

| Metric | **Pareto DP** | A* | [LCG](https://doi.org/10.1145/2034691.2034697) | [MIP](https://doi.org/10.1287/ijoc.2014.0637) | [CP](https://doi.org/10.1145/2034691.2034697) |
| --- | ---: | ---: | ---: | ---: | ---: |
| P50 (ms) | $\color{green}{0.163}$ | 0.246 | 4.781 | 4.448 | > 1000.00 |
| P95 (ms) | 2.008 | $\color{green}{0.843}$ | 17.582 | 26.624 | > 1000.00 |
| Extra heap P95 (KiB) | $\color{green}{264.41}$ | 640.64 | 2420.35 | 760.18 | 2272.55 |
| RSS P95 (KiB) | $\color{green}{2848.00}$ | 2896.00 | 6176.00 | 4416.00 | 5856.00 |
| Completed | 26/26 | 26/26 | 26/26 | 26/26 | 5/26 |

</details>

One variant per exact-method family, selected by completion rate then P95. Timing percentiles reaching the timeout limit are shown as **> 1000.00 ms**.

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
| [LCG](https://doi.org/10.1287/ijoc.2014.0637) (2015 cell-free, Pumpkin) | 18/26 | 3.910 | > 1000.00 |
| [CP](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 5/26 | > 1000.00 | > 1000.00 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (unary, microlp) | 1/26 | > 1000.00 | > 1000.00 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (one-hot, microlp) | 0/26 | > 1000.00 | > 1000.00 |

HTML matched the optimum in 0/26 cases.

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
