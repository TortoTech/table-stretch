# Shared bounds and A* optimization

Compared with [the previous implementation](https://github.com/TortoTech/table-stretch/tree/3bfc6998c97db3d3ea305a5cfca98bf151bb0658) on the same inputs, machine, 1-second full-call limit and three repetitions. Both timing and fresh-process memory were rerun. This is a comparison of the combined changes, not an attribution of gains to each individual change.

A* adds a feasible incumbent, suffix area/floor bounds, clipped candidate domains, direct final-column completion and parent links. It remains best-first search with column-minimality pruning. CP/LCG/MIP add root area bounds, a feasible objective upper bound and corresponding row caps. When the root lower bound meets the feasible height, preprocessing certifies the result without constructing a backend. Otherwise the existing engines and branchers are used. All preprocessing is included in the timings. [Algorithms and correctness](algorithms.md#bounds-shared-with-other-exact-methods) · [Model bounds](native-models.md#objective-bounds).

Pareto DP keeps its existing algorithm and shares its bound implementation with A*. HTML is unchanged. Small differences in their timings are run-to-run variation, not evidence of a new optimization.

## Ebooks: 1383 cases

| Method | Completed before → after | P50 before → after (ms) | P95 before → after (ms) | Root certificates |
| --- | --- | ---: | ---: | ---: |
| HTML heuristic | 1383/1383 → 1383/1383 | 0.0004 → 0.0003 | 0.0008 → 0.0007 | 0/1383 |
| **Pareto DP** | 1383/1383 → 1383/1383 | 0.0022 → 0.0021 | 0.0105 → 0.0102 | 610/1383 |
| A* | 1383/1383 → 1383/1383 | 0.0033 → 0.0022 | 0.0164 → 0.0106 | 610/1383 |
| [LCG](https://doi.org/10.1287/ijoc.2014.0637) (2015 cell-free, Pumpkin) | 1383/1383 → 1383/1383 | 0.0467 → 0.0180 | 0.4320 → 0.1396 | 611/1383 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (cell-free, microlp) | 1383/1383 → 1383/1383 | 0.0552 → 0.0159 | 1.1708 → 0.3619 | 611/1383 |
| [LCG](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 1383/1383 → 1383/1383 | 0.0655 → 0.0298 | 0.6591 → 0.3833 | 611/1383 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (unary, microlp) | 1383/1383 → 1383/1383 | 0.0540 → 0.0245 | 1.0748 → 0.7912 | 611/1383 |
| [CP](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 1367/1383 → 1375/1383 | 0.0589 → 0.0282 | 1.8572 → 0.9086 | 611/1383 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (one-hot, microlp) | 1382/1383 → 1383/1383 | 0.0681 → 0.0311 | 2.4027 → 1.4617 | 611/1383 |

Root certificates count cases certified before search in every repetition. They do not measure backend search speed. Remaining cases still require their named search algorithm.

| Measured implementation | Extra heap P95 before → after (KiB) | Change | RSS P95 before → after (KiB) |
| --- | ---: | ---: | ---: |
| HTML heuristic | 0.18 → 0.18 | +0.0% | 2192.00 → 2160.00 |
| **Pareto DP** | 9.39 → 9.39 | +0.0% | 2272.00 → 2224.00 |
| A* | 17.51 → 9.32 | -46.8% | 2272.00 → 2224.00 |
| [LCG](https://doi.org/10.1287/ijoc.2014.0637) (2015 cell-free, Pumpkin) | 265.40 → 204.22 | -23.1% | 3408.00 → 3168.00 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (cell-free, microlp) | — → 218.88 | no same-variant baseline | — → 3184.00 |
| [CP](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 553.98 → 513.26 | -7.4% | 3744.00 → 3600.00 |

Memory comparisons use the identical implementation variant on both sides. Memory is collected separately from timing; observed timeout peaks are not completion-memory bounds.

Featured MIP (microlp) changed from MIP (unary, microlp) to MIP (cell-free, microlp). The timing rows above compare each variant with itself; absent same-variant memory baselines are shown as missing, not substituted from another variant.

[Timing and all variants](benchmark-native.md) · [Memory details](benchmark-native-memory.md)

## MiniZinc: 26 cases

| Method | Completed before → after | P50 before → after (ms) | P95 before → after (ms) | Root certificates |
| --- | --- | ---: | ---: | ---: |
| HTML heuristic | 26/26 → 26/26 | 0.0030 → 0.0025 | 0.0058 → 0.0054 | 0/26 |
| A* | 26/26 → 26/26 | 0.2462 → 0.1617 | 0.8430 → 0.7697 | 0/26 |
| **Pareto DP** | 26/26 → 26/26 | 0.1626 → 0.1595 | 2.0084 → 1.9874 | 0/26 |
| [LCG](https://doi.org/10.1287/ijoc.2014.0637) (2015 cell-free, Pumpkin) | 18/26 → 25/26 | 3.9095 → 1.1595 | > 1000.00 → 2.7630 | 0/26 |
| [LCG](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 26/26 → 26/26 | 4.7811 → 3.8839 | 17.5817 → 10.7440 | 0/26 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (cell-free, microlp) | 26/26 → 26/26 | 4.4477 → 1.9597 | 26.6237 → 24.7333 | 0/26 |
| [CP](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 5/26 → 5/26 | > 1000.00 → > 1000.00 | > 1000.00 → > 1000.00 | 0/26 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (unary, microlp) | 1/26 → 5/26 | > 1000.00 → > 1000.00 | > 1000.00 → > 1000.00 | 0/26 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (one-hot, microlp) | 0/26 → 0/26 | > 1000.00 → > 1000.00 | > 1000.00 → > 1000.00 | 0/26 |

Root certificates count cases certified before search in every repetition. They do not measure backend search speed. Remaining cases still require their named search algorithm.

| Measured implementation | Extra heap P95 before → after (KiB) | Change | RSS P95 before → after (KiB) |
| --- | ---: | ---: | ---: |
| HTML heuristic | 0.57 → 0.57 | +0.0% | 2304.00 → 2272.00 |
| A* | 640.64 → 162.27 | -74.7% | 2896.00 → 2512.00 |
| **Pareto DP** | 264.41 → 264.41 | +0.0% | 2848.00 → 2752.00 |
| [LCG](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 2420.35 → 2375.33 | -1.9% | 6176.00 → 6016.00 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (cell-free, microlp) | 760.18 → 707.65 | -6.9% | 4416.00 → 4256.00 |
| [CP](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 2272.55 → 2120.96 | -6.7% | 5856.00 → 5664.00 |

Memory comparisons use the identical implementation variant on both sides. Memory is collected separately from timing; observed timeout peaks are not completion-memory bounds.

[Timing and all variants](benchmark-minizinc.md) · [Memory details](benchmark-minizinc-memory.md)

## Validation

All returned exact layouts match fixed reference optima. Rust tests cover exhaustive small integer widths, zero heights, gaps, capped final columns, path reconstruction and a case where the first completed A* tail is suboptimal. Rust tests, Clippy, Python checks and the existing abstract Lean proofs pass. Backend floating-point acceptance checks are unchanged. The abstract proofs do not verify the complete A* implementation or the CP/MIP engines.

[Machine-readable comparison](bound-optimization.json). Regenerate with `python3 scripts/report_bound_optimization.py` after refreshing both timing and memory suites.
