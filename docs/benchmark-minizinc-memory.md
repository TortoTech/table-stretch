# MiniZinc memory benchmark

26 cases, 3 fresh processes per method/case, 1-second solve limit. Apple M6, 16 GiB RAM. Recorded at 2026-11-01T08:34:54.322081+00:00.

The six implementations are fixed to those selected by the corresponding timing benchmark. Rows retain its P95 time order. Completion counts below belong to this separate instrumented memory pass.

| Method | Completed | Measured | Extra heap P50 (KiB) | Extra heap P95 (KiB) | Extra heap max (KiB) | RSS P95 (MiB) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| HTML heuristic | 26/26 | 26/26 | 0.266 | 0.570 | 0.812 | 2.250 |
| A* | 26/26 | 26/26 | 228.922 | 640.637 | 916.078 | 2.828 |
| **Pareto DP** | 26/26 | 26/26 | 65.924 | 264.414 | 367.035 | 2.781 |
| [LCG](https://doi.org/10.1145/2034691.2034697) (Pumpkin) | 26/26 | 26/26 | 1367.275 | 2420.348 | 3438.680 | 6.031 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (microlp) | 26/26 | 26/26 | 433.248 | 760.180 | 792.291 | 4.312 |
| [CP](https://doi.org/10.1145/2034691.2034697) (Pumpkin) | 5/26 | 26/26 | 1296.109 | 2272.547 | 2356.770 | 5.719 |

Each case contributes the median of its repetitions; P50/P95/max summarize those case medians. Timeout memory is included as observed, with no artificial memory penalty. It is not an upper bound on memory required to finish. If any case lacks telemetry, that method’s aggregate memory values are withheld; missing values are never zero-filled.

## Measurement scope

- **Extra heap:** peak live bytes requested through Rust’s global allocator during the library call, minus live bytes just before it. Includes preparation, models, search and the returned layout. Excludes the already loaded input, JSON serialization, stack, allocator metadata/caches and transient buffers internal to realloc. Counts live bytes, not cumulative allocation traffic.
- **RSS:** macOS `/usr/bin/time -l` maximum resident set size for the entire fresh child process, converted from bytes. Includes startup, one loaded input, libraries, stack, allocator retention, solver and output. No baseline subtraction is applied to RSS.
- **Isolation:** one case and one solve per process, no warmup; the allocator begins tracking the solve after input parsing and resets the heap peak. Raw records retain baseline, total peak and end heap bytes. This prevents earlier calls from contaminating either peak.
- **Timing:** allocation instrumentation adds overhead. Its diagnostic durations are not substituted for the original uninstrumented timings. A two-second process watchdog grace handles startup and cooperative timeout overruns; hard kills are recorded as missing memory.

The allocator delegates to [`System`](https://doc.rust-lang.org/std/alloc/trait.GlobalAlloc.html). RSS is reported by [Apple’s time implementation](https://github.com/apple-oss-distributions/shell_cmds/blob/main/time/time.c).

## Reproduce

```sh
python3 scripts/benchmark_memory.py --suite minizinc
python3 scripts/report_memory.py --suite minizinc
python3 scripts/report_native.py --suite minizinc
```

[Raw measurements](benchmark-minizinc-memory.jsonl) · [Summary](benchmark-minizinc-memory-summary.json) · [Timing benchmark](benchmark-minizinc.md)
