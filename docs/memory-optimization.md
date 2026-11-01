# Model memory optimization

Historical snapshot after [6ceddbd](https://github.com/TortoTech/table-stretch/tree/6ceddbd). For subsequent search changes, see [shared-bound optimization](bound-optimization.md).

Compared with [the published baseline](https://github.com/TortoTech/table-stretch/tree/ae9faf0a989eb738b3d0295e4d6b042fa1db8c49), using the same 1,383 ebook cases and 26 MiniZinc cases, hardware, 1-second solve limit and three repetitions. Timing and memory remain separate measurement passes.

## Changes

- Grow the Pumpkin nogood arena on demand instead of reserving 1 MB.
- Encode sparse integer domains with interval-exclusion clauses instead of explicit holes.
- Use literal constants in element arrays and fold fixed cells into row/column lower bounds.
- Remove impossible low row heights and redundant MIP clauses and fixed-cell configuration variables.

These are equivalent model reductions; CP still disables learning and LCG still enables it. Gap clauses change propagation scheduling and explanations, so identical search traces or runtime improvements are not assumed. [Equivalence arguments](native-models.md#compact-model-construction).

## Peak additional live heap

| Dataset | Implementation before → after | P95 before (KiB) | P95 after (KiB) | Reduction |
| --- | --- | ---: | ---: | ---: |
| Ebooks | [LCG](https://doi.org/10.1287/ijoc.2014.0637) (2015 cell-free, Pumpkin) | 1360.227 | 265.398 | 80.5% |
| Ebooks | [MIP](https://doi.org/10.1287/ijoc.2014.0637) (unary, microlp) | 271.570 | 257.479 | 5.2% |
| Ebooks | [CP](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 1336.410 | 553.984 | 58.5% |
| MiniZinc | [LCG](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 12943.137 | 2420.348 | 81.3% |
| MiniZinc | [MIP](https://doi.org/10.1287/ijoc.2014.0637) (cell-free, microlp) | 792.184 | 760.180 | 4.0% |
| MiniZinc | [CP](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 9217.203 | 2272.547 | 75.3% |

Each family uses the version selected by its respective timing pass. Percentage reductions are only reported for the same variant. Timeout memory is the peak observed before termination, not a bound on memory required to complete.

## Timing and completion

| Dataset | Family | Completed before → after | P95 before (ms) | P95 after (ms) |
| --- | --- | --- | ---: | ---: |
| Ebooks | [LCG](https://doi.org/10.1287/ijoc.2014.0637) (Pumpkin) | 1383/1383 → 1383/1383 | 0.514 | 0.432 |
| Ebooks | [MIP](https://doi.org/10.1287/ijoc.2014.0637) (microlp) | 1383/1383 → 1383/1383 | 1.155 | 1.075 |
| Ebooks | [CP](https://doi.org/10.1145/2034691.2034697) (Pumpkin) | 1367/1383 → 1367/1383 | 2.079 | 1.857 |
| MiniZinc | [LCG](https://doi.org/10.1145/2034691.2034697) (Pumpkin) | 26/26 → 26/26 | 37.895 | 17.582 |
| MiniZinc | [MIP](https://doi.org/10.1287/ijoc.2014.0637) (microlp) | 26/26 → 26/26 | 26.629 | 26.624 |
| MiniZinc | [CP](https://doi.org/10.1145/2034691.2034697) (Pumpkin) | 5/26 → 5/26 | 1000.000 | 1000.000 |

### Tradeoffs across all variants

- MiniZinc: [LCG](https://doi.org/10.1287/ijoc.2014.0637) (2015 cell-free, Pumpkin) completion fell from 22/26 to 18/26 at the same time limit.

Reduced model memory does not guarantee faster search: the gap-clause representation changes propagation and conflict explanations. These regressions remain visible in the all-variant reports; family selection still prioritizes completion before P95 time.

All returned exact layouts are checked against the fixed reference optima. Regression tests cover large gaps, zero-height cells, fixed cells dominating row heights, and exhaustive small-width oracles. Rust tests, Clippy, Python checks and the existing abstract Lean proofs pass. MIP numerical acceptance tolerances are unchanged; these results do not constitute a rational optimality certificate for the floating-point backend.

[Ebook results](https://github.com/TortoTech/table-stretch/blob/6ceddbd/docs/benchmark-native.md) · [MiniZinc results](https://github.com/TortoTech/table-stretch/blob/6ceddbd/docs/benchmark-minizinc.md) · [Comparison data](memory-optimization.json)

Regenerate this fixed historical comparison with `python3 scripts/report_memory_optimization.py`.
