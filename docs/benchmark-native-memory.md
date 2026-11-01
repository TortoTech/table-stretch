# Ebook memory benchmark

1383 cases, 3 fresh processes per method/case, 1-second solve limit. Apple M6, 16 GiB RAM. Recorded at 2026-11-01T08:05:53.845730+00:00.

The six implementations are fixed to those selected by the corresponding timing benchmark. Rows retain its P95 time order. Completion counts below belong to this separate instrumented memory pass.

| Method | Completed | Measured | Extra heap P50 (KiB) | Extra heap P95 (KiB) | Extra heap max (KiB) | RSS P95 (MiB) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| HTML heuristic | 1383/1383 | 1383/1383 | 0.086 | 0.176 | 0.625 | 2.141 |
| **Pareto DP** | 1383/1383 | 1383/1383 | 2.141 | 9.395 | 103.586 | 2.203 |
| A* | 1383/1383 | 1383/1383 | 3.176 | 17.512 | 174.703 | 2.219 |
| [LCG](https://doi.org/10.1287/ijoc.2014.0637) (Pumpkin) | 1383/1383 | 1383/1383 | 1090.195 | 1360.227 | 4681.586 | 3.531 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (microlp) | 1383/1383 | 1383/1383 | 62.617 | 271.570 | 3873.969 | 3.344 |
| [CP](https://doi.org/10.1145/2034691.2034697) (Pumpkin) | 1367/1383 | 1383/1383 | 312.730 | 1336.410 | 14058.559 | 4.422 |

Each case contributes the median of its repetitions; P50/P95/max summarize those case medians. Timeout memory is included as observed, with no artificial memory penalty. It is not an upper bound on memory required to finish. If any case lacks telemetry, that method’s aggregate memory values are withheld; missing values are never zero-filled.

## Measurement scope

- **Extra heap:** peak live bytes requested through Rust’s global allocator during the library call, minus live bytes just before it. Includes preparation, models, search and the returned layout. Excludes the already loaded input, JSON serialization, stack, allocator metadata/caches and transient buffers internal to realloc. Counts live bytes, not cumulative allocation traffic.
- **RSS:** macOS `/usr/bin/time -l` maximum resident set size for the entire fresh child process, converted from bytes. Includes startup, one loaded input, libraries, stack, allocator retention, solver and output. No baseline subtraction is applied to RSS.
- **Isolation:** one case and one solve per process, no warmup; the allocator begins tracking the solve after input parsing and resets the heap peak. Raw records retain baseline, total peak and end heap bytes. This prevents earlier calls from contaminating either peak.
- **Timing:** allocation instrumentation adds overhead. Its diagnostic durations are not substituted for the original uninstrumented timings. A two-second process watchdog grace handles startup and cooperative timeout overruns; hard kills are recorded as missing memory.

The allocator delegates to [`System`](https://doc.rust-lang.org/std/alloc/trait.GlobalAlloc.html). RSS is reported by [Apple’s time implementation](https://github.com/apple-oss-distributions/shell_cmds/blob/main/time/time.c).

## Reproduce

```sh
python3 scripts/benchmark_memory.py --suite ebooks
python3 scripts/report_memory.py --suite ebooks
python3 scripts/report_native.py --suite ebooks
```

[Raw measurements](benchmark-native-memory.jsonl) · [Summary](benchmark-native-memory-summary.json) · [Timing benchmark](benchmark-native.md)
