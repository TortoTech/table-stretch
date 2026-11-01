# Controlled evaluation and ablations

**Retrospective evaluation:** both corpora were used in earlier algorithm development. Grouping prevents new configuration selection from crossing book boundaries; it does not turn these into previously unseen data or establish generalization to new books.

The [protocol](ablation-protocol.json) was committed before measurement. Book hashes and duplicate aliases define disjoint groups: **10 validation books / 281 cases**, **21 evaluation books / 1102 cases**. All widths of a source table stay together. All **26 MiniZinc** instances are a separate evaluation suite. No evaluation result is used to choose the featured algorithm or ablation profile.

One full implementation per family is selected using validation completion count, then capped P95, median and name. The same frozen choice is used for both evaluation suites. Every measured configuration uses the same 1-second call limit, one warmup and three timed repetitions, with shuffled order. Three separate fresh-process memory repetitions measure extra live heap and process RSS. Input conversion, startup and JSON are outside library timing; all preparation and solver construction are inside.

## Validation-only selection

| Family | Selected implementation | Completed | P95 (ms) |
| --- | --- | ---: | ---: |
| Pareto DP | **Pareto DP** | 281/281 | 0.0085 |
| A* | A* | 281/281 | 0.0084 |
| LCG | [LCG](https://doi.org/10.1287/ijoc.2014.0637) (2015 cell-free, Pumpkin) | 281/281 | 0.0931 |
| MIP | [MIP](https://doi.org/10.1287/ijoc.2014.0637) (cell-free, microlp) | 281/281 | 0.2108 |
| CP | [CP](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 280/281 | 0.3919 |

[All validation metrics and locked selection](ablation/selection.json). Selection is based on these full configurations only; ablations are explanatory, not candidates selected on the evaluation set.

## Configurations

- **base:** search-family enhancements disabled; Pareto dominance and A* area/column-minimality mechanisms remain. Research models retain the prior compact encodings, static floors/caps and fixed-cell elimination, but disable the new root area bound and feasible-incumbent restrictions.
- **common:** add the incumbent, area/floor bounds and global candidate caps to search methods, leaving terminal completion and compact paths off. For CP/LCG/MIP, common is identical to full and is not measured twice.
- **full:** all current enhancements.
- **without_X:** remove that enhancement from full. Removing the incumbent also removes its dependent row caps and root certificate in research models. This is an explicitly coupled removal, not an isolated measurement of incumbent construction.

The three-way base/common/full comparison and leave-one-out comparisons expose interactions but are not a full factorial design. Different engines still perform different propagation/inference; this is not a normalization of every internal pruning rule. [Exact flag values and applicability](ablation-protocol.json).

## Observed effects

Full configurations are kept fixed even where a leave-one-out configuration has a lower P95. Small differences are descriptive measurements, not claims of statistical significance.

| Suite | Method | Base P95 (ms) | Full P95 (ms) | Base completed | Full completed |
| --- | --- | ---: | ---: | ---: | ---: |
| Books | Pareto DP | 0.0554 | 0.0102 | 1102/1102 | 1102/1102 |
| Books | A* | 0.0214 | 0.0114 | 1102/1102 | 1102/1102 |
| Books | LCG | 0.4396 | 0.1409 | 1102/1102 | 1102/1102 |
| Books | MIP | 1.6743 | 0.4072 | 1102/1102 | 1102/1102 |
| Books | CP | 2.3291 | 1.0740 | 1088/1102 | 1095/1102 |
| MiniZinc | Pareto DP | 170.1322 | 2.0000 | 26/26 | 26/26 |
| MiniZinc | A* | 1.2053 | 0.7799 | 26/26 | 26/26 |
| MiniZinc | LCG | > 1000.00 | 2.7655 | 18/26 | 25/26 |
| MiniZinc | MIP | 26.5800 | 24.5291 | 26/26 | 26/26 |
| MiniZinc | CP | > 1000.00 | > 1000.00 | 5/26 | 5/26 |

Full configurations certify **477–478/1102 book cases** at the root, versus **0/26 MiniZinc cases**. These calls remain timed. This helps explain the suite-level difficulty difference under the same deadline and timing scope.


## Book-grouped evaluation

![Book-grouped evaluation; Pareto DP outlined in blue, minima in green.](assets/ablation-ebooks.svg?v=d7f449464353)

<details>
<summary>Table data and paper links</summary>

| Metric | **Pareto DP** | A* | [LCG](https://doi.org/10.1287/ijoc.2014.0637) | [MIP](https://doi.org/10.1287/ijoc.2014.0637) | [CP](https://doi.org/10.1145/2034691.2034697) |
| --- | ---: | ---: | ---: | ---: | ---: |
| P50 (ms) | $\color{green}{0.002}$ | 0.002 | 0.018 | 0.016 | 0.030 |
| P95 (ms) | $\color{green}{0.010}$ | 0.011 | 0.141 | 0.407 | 1.074 |
| Extra heap P95 (KiB) | $\color{green}{10.67}$ | 10.99 | 213.60 | 227.77 | 566.94 |
| RSS P95 (KiB) | $\color{green}{2288.00}$ | $\color{green}{2288.00}$ | 3232.00 | 3248.00 | 3728.00 |
| Completed | 1102/1102 | 1102/1102 | 1102/1102 | 1102/1102 | 1095/1102 |

</details>

![Performance profiles: Book-grouped evaluation](assets/ablation-ebooks-performance.svg?v=c04c573c2352)

Performance-profile denominator includes every case. An implementation counts as solved only when all repetitions finish optimally; failures have infinite ratios. At 1×, the curve gives the fraction of cases where that implementation is fastest. The log-scale x-axis includes every finite ratio, so each curve ends at its completion fraction.

### Pareto DP: Pareto DP

| Configuration | Completed | P50 (ms) | P95 (ms) | Heap P95 (KiB) | RSS P95 (KiB) | Memory completed | Root certificates | Paired time / full | Pairs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 1102/1102 | 0.0036 | 0.0554 | 21.02 | 2304.00 | 1102/1102 | 0 | 2.074× | 1102 |
| common | 1102/1102 | 0.0025 | 0.0163 | 11.50 | 2288.00 | 1102/1102 | 477 | 1.207× | 1102 |
| full | 1102/1102 | 0.0021 | 0.0102 | 10.67 | 2288.00 | 1102/1102 | 477 | 1.000× | 1102 |
| without_incumbent | 1102/1102 | 0.0022 | 0.0145 | 13.48 | 2272.00 | 1102/1102 | 0 | 1.082× | 1102 |
| without_area_bound | 1102/1102 | 0.0021 | 0.0101 | 10.77 | 2288.00 | 1102/1102 | 397 | 1.008× | 1102 |
| without_floor_bound | 1102/1102 | 0.0021 | 0.0101 | 10.67 | 2288.00 | 1102/1102 | 378 | 1.009× | 1102 |
| without_column_caps | 1102/1102 | 0.0021 | 0.0096 | 11.61 | 2288.00 | 1102/1102 | 359 | 1.018× | 1102 |
| without_terminal_column | 1102/1102 | 0.0023 | 0.0133 | 11.47 | 2288.00 | 1102/1102 | 477 | 1.119× | 1102 |
| without_compact_paths | 1102/1102 | 0.0022 | 0.0134 | 10.68 | 2288.00 | 1102/1102 | 477 | 1.066× | 1102 |

### A*: A*

| Configuration | Completed | P50 (ms) | P95 (ms) | Heap P95 (KiB) | RSS P95 (KiB) | Memory completed | Root certificates | Paired time / full | Pairs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 1102/1102 | 0.0037 | 0.0214 | 20.18 | 2272.00 | 1102/1102 | 0 | 1.626× | 1102 |
| common | 1102/1102 | 0.0025 | 0.0144 | 11.61 | 2288.00 | 1102/1102 | 477 | 1.120× | 1102 |
| full | 1102/1102 | 0.0022 | 0.0114 | 10.99 | 2288.00 | 1102/1102 | 477 | 1.000× | 1102 |
| without_incumbent | 1102/1102 | 0.0023 | 0.0117 | 11.01 | 2272.00 | 1102/1102 | 0 | 1.046× | 1102 |
| without_area_bound | 1102/1102 | 0.0023 | 0.0126 | 10.77 | 2288.00 | 1102/1102 | 397 | 1.055× | 1102 |
| without_floor_bound | 1102/1102 | 0.0022 | 0.0115 | 11.00 | 2288.00 | 1102/1102 | 378 | 1.009× | 1102 |
| without_column_caps | 1102/1102 | 0.0022 | 0.0117 | 11.84 | 2288.00 | 1102/1102 | 359 | 1.019× | 1102 |
| without_terminal_column | 1102/1102 | 0.0024 | 0.0143 | 11.63 | 2288.00 | 1102/1102 | 477 | 1.102× | 1102 |
| without_compact_paths | 1102/1102 | 0.0023 | 0.0122 | 10.80 | 2288.00 | 1102/1102 | 477 | 1.031× | 1102 |

### LCG: LCG (2015 cell-free, Pumpkin)

| Configuration | Completed | P50 (ms) | P95 (ms) | Heap P95 (KiB) | RSS P95 (KiB) | Memory completed | Root certificates | Paired time / full | Pairs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 1102/1102 | 0.0478 | 0.4396 | 283.57 | 3440.00 | 1102/1102 | 0 | 4.474× | 1102 |
| full | 1102/1102 | 0.0180 | 0.1409 | 213.60 | 3232.00 | 1102/1102 | 478 | 1.000× | 1102 |
| without_area_bound | 1102/1102 | 0.0243 | 0.1727 | 226.54 | 3264.00 | 1102/1102 | 397 | 1.279× | 1102 |
| without_incumbent | 1102/1102 | 0.0463 | 0.4636 | 281.22 | 3440.00 | 1102/1102 | 0 | 4.276× | 1102 |
| without_row_caps | 1102/1102 | 0.0194 | 0.1532 | 251.58 | 3296.00 | 1102/1102 | 478 | 1.078× | 1102 |
| without_root_certificate | 1102/1102 | 0.0277 | 0.1437 | 223.89 | 3248.00 | 1102/1102 | 0 | 2.435× | 1102 |

### MIP: MIP (cell-free, microlp)

| Configuration | Completed | P50 (ms) | P95 (ms) | Heap P95 (KiB) | RSS P95 (KiB) | Memory completed | Root certificates | Paired time / full | Pairs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 1102/1102 | 0.0561 | 1.6743 | 458.81 | 3728.00 | 1102/1102 | 0 | 4.203× | 1102 |
| full | 1102/1102 | 0.0163 | 0.4072 | 227.77 | 3248.00 | 1102/1102 | 478 | 1.000× | 1102 |
| without_area_bound | 1102/1102 | 0.0254 | 0.7708 | 280.09 | 3344.00 | 1102/1102 | 397 | 1.456× | 1102 |
| without_incumbent | 1102/1102 | 0.0498 | 0.9862 | 445.84 | 3584.00 | 1102/1102 | 0 | 3.483× | 1102 |
| without_row_caps | 1102/1102 | 0.0226 | 0.7780 | 399.69 | 3552.00 | 1102/1102 | 478 | 1.332× | 1102 |
| without_root_certificate | 1102/1102 | 0.0260 | 0.3982 | 260.43 | 3264.00 | 1102/1102 | 0 | 1.977× | 1102 |

### CP: CP (2011, Pumpkin)

| Configuration | Completed | P50 (ms) | P95 (ms) | Heap P95 (KiB) | RSS P95 (KiB) | Memory completed | Root certificates | Paired time / full | Pairs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 1088/1102 | 0.0626 | 2.3291 | 606.27 | 3840.00 | 1088/1102 | 0 | 3.727× | 1088 |
| full | 1095/1102 | 0.0302 | 1.0740 | 566.94 | 3728.00 | 1095/1102 | 478 | 1.000× | 1095 |
| without_area_bound | 1093/1102 | 0.0414 | 1.6723 | 583.22 | 3744.00 | 1093/1102 | 397 | 1.343× | 1093 |
| without_incumbent | 1089/1102 | 0.0610 | 1.5539 | 606.27 | 3824.00 | 1089/1102 | 0 | 3.500× | 1089 |
| without_row_caps | 1095/1102 | 0.0314 | 1.0885 | 568.38 | 3744.00 | 1095/1102 | 478 | 1.004× | 1095 |
| without_root_certificate | 1095/1102 | 0.0516 | 1.0649 | 605.34 | 3792.00 | 1095/1102 | 0 | 2.922× | 1095 |

## MiniZinc evaluation

![MiniZinc evaluation; Pareto DP outlined in blue, minima in green.](assets/ablation-minizinc.svg?v=2ef594d5eeaa)

<details>
<summary>Table data and paper links</summary>

| Metric | **Pareto DP** | A* | [LCG](https://doi.org/10.1287/ijoc.2014.0637) | [MIP](https://doi.org/10.1287/ijoc.2014.0637) | [CP](https://doi.org/10.1145/2034691.2034697) |
| --- | ---: | ---: | ---: | ---: | ---: |
| P50 (ms) | 0.162 | $\color{green}{0.159}$ | 1.137 | 1.920 | > 1000.00 |
| P95 (ms) | 2.000 | $\color{green}{0.780}$ | 2.765 | 24.529 | > 1000.00 |
| Extra heap P95 (KiB) | 263.73 | $\color{green}{162.06}$ | 754.02 | 707.65 | 2120.96 |
| RSS P95 (KiB) | 2848.00 | $\color{green}{2560.00}$ | 4240.00 | 4256.00 | 5680.00 |
| Completed | 26/26 | 26/26 | 25/26 | 26/26 | 5/26 |

</details>

![Performance profiles: MiniZinc evaluation](assets/ablation-minizinc-performance.svg?v=60e71966d7fd)

Performance-profile denominator includes every case. An implementation counts as solved only when all repetitions finish optimally; failures have infinite ratios. At 1×, the curve gives the fraction of cases where that implementation is fastest. The log-scale x-axis includes every finite ratio, so each curve ends at its completion fraction.

### Pareto DP: Pareto DP

| Configuration | Completed | P50 (ms) | P95 (ms) | Heap P95 (KiB) | RSS P95 (KiB) | Memory completed | Root certificates | Paired time / full | Pairs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 26/26 | 2.3122 | 170.1322 | 2567.36 | 4736.00 | 26/26 | 0 | 11.808× | 26 |
| common | 26/26 | 0.3430 | 4.8498 | 358.27 | 2912.00 | 26/26 | 0 | 2.470× | 26 |
| full | 26/26 | 0.1620 | 2.0000 | 263.73 | 2848.00 | 26/26 | 0 | 1.000× | 26 |
| without_incumbent | 26/26 | 0.2545 | 7.9984 | 574.63 | 3040.00 | 26/26 | 0 | 1.830× | 26 |
| without_area_bound | 26/26 | 0.1650 | 2.1163 | 263.73 | 2816.00 | 26/26 | 0 | 1.068× | 26 |
| without_floor_bound | 26/26 | 0.1746 | 2.0124 | 366.66 | 2864.00 | 26/26 | 0 | 1.049× | 26 |
| without_column_caps | 26/26 | 0.1712 | 1.9891 | 398.48 | 2864.00 | 26/26 | 0 | 1.055× | 26 |
| without_terminal_column | 26/26 | 0.3107 | 4.4662 | 366.66 | 2880.00 | 26/26 | 0 | 2.166× | 26 |
| without_compact_paths | 26/26 | 0.1968 | 2.1618 | 249.79 | 2848.00 | 26/26 | 0 | 1.154× | 26 |

### A*: A*

| Configuration | Completed | P50 (ms) | P95 (ms) | Heap P95 (KiB) | RSS P95 (KiB) | Memory completed | Root certificates | Paired time / full | Pairs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 26/26 | 0.3102 | 1.2053 | 673.48 | 2912.00 | 26/26 | 0 | 2.258× | 26 |
| common | 26/26 | 0.2005 | 0.8864 | 265.95 | 2688.00 | 26/26 | 0 | 1.380× | 26 |
| full | 26/26 | 0.1585 | 0.7799 | 162.06 | 2560.00 | 26/26 | 0 | 1.000× | 26 |
| without_incumbent | 26/26 | 0.1645 | 1.0104 | 215.71 | 2720.00 | 26/26 | 0 | 1.092× | 26 |
| without_area_bound | 26/26 | 0.1841 | 0.9730 | 155.73 | 2560.00 | 26/26 | 0 | 1.186× | 26 |
| without_floor_bound | 26/26 | 0.1772 | 0.7860 | 251.38 | 2720.00 | 26/26 | 0 | 1.098× | 26 |
| without_column_caps | 26/26 | 0.1774 | 0.7965 | 287.41 | 2752.00 | 26/26 | 0 | 1.098× | 26 |
| without_terminal_column | 26/26 | 0.1904 | 0.8522 | 258.79 | 2656.00 | 26/26 | 0 | 1.306× | 26 |
| without_compact_paths | 26/26 | 0.1698 | 0.8099 | 165.02 | 2576.00 | 26/26 | 0 | 1.052× | 26 |

### LCG: LCG (2015 cell-free, Pumpkin)

| Configuration | Completed | P50 (ms) | P95 (ms) | Heap P95 (KiB) | RSS P95 (KiB) | Memory completed | Root certificates | Paired time / full | Pairs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 18/26 | 3.8610 | > 1000.00 | 44547.94 | 44416.00 | 18/26 | 0 | 3.477× | 17 |
| full | 25/26 | 1.1371 | 2.7655 | 754.02 | 4240.00 | 25/26 | 0 | 1.000× | 25 |
| without_area_bound | 25/26 | 1.1192 | 3.0477 | 754.02 | 4336.00 | 25/26 | 0 | 1.091× | 25 |
| without_incumbent | 20/26 | 2.3089 | > 1000.00 | 44617.54 | 44352.00 | 20/26 | 0 | 2.865× | 19 |
| without_row_caps | 25/26 | 1.0513 | 2.7600 | 754.02 | 4240.00 | 25/26 | 0 | 0.978× | 25 |
| without_root_certificate | 25/26 | 1.1010 | 2.7435 | 754.02 | 4240.00 | 25/26 | 0 | 1.002× | 25 |

### MIP: MIP (cell-free, microlp)

| Configuration | Completed | P50 (ms) | P95 (ms) | Heap P95 (KiB) | RSS P95 (KiB) | Memory completed | Root certificates | Paired time / full | Pairs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 26/26 | 4.4603 | 26.5800 | 760.18 | 4384.00 | 26/26 | 0 | 1.520× | 26 |
| full | 26/26 | 1.9203 | 24.5291 | 707.65 | 4256.00 | 26/26 | 0 | 1.000× | 26 |
| without_area_bound | 26/26 | 3.5453 | 27.5634 | 807.37 | 4352.00 | 26/26 | 0 | 1.396× | 26 |
| without_incumbent | 26/26 | 2.4054 | 25.0317 | 687.78 | 4304.00 | 26/26 | 0 | 1.032× | 26 |
| without_row_caps | 26/26 | 2.1225 | 24.6002 | 707.65 | 4288.00 | 26/26 | 0 | 1.013× | 26 |
| without_root_certificate | 26/26 | 1.8944 | 24.6400 | 707.65 | 4336.00 | 26/26 | 0 | 1.009× | 26 |

### CP: CP (2011, Pumpkin)

| Configuration | Completed | P50 (ms) | P95 (ms) | Heap P95 (KiB) | RSS P95 (KiB) | Memory completed | Root certificates | Paired time / full | Pairs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 5/26 | > 1000.00 | > 1000.00 | 2272.55 | 5872.00 | 5/26 | 0 | 1.895× | 5 |
| full | 5/26 | > 1000.00 | > 1000.00 | 2120.96 | 5680.00 | 5/26 | 0 | 1.000× | 5 |
| without_area_bound | 5/26 | > 1000.00 | > 1000.00 | 2120.10 | 5680.00 | 5/26 | 0 | 1.601× | 5 |
| without_incumbent | 5/26 | > 1000.00 | > 1000.00 | 2266.55 | 5840.00 | 5/26 | 0 | 1.249× | 5 |
| without_row_caps | 5/26 | > 1000.00 | > 1000.00 | 2120.96 | 5696.00 | 5/26 | 0 | 1.002× | 5 |
| without_root_certificate | 5/26 | > 1000.00 | > 1000.00 | 2120.96 | 5680.00 | 5/26 | 0 | 1.001× | 5 |

## Interpretation and limits

P50/P95 use one median per case; incomplete timing repetitions are censored at the common limit. Paired ratios are geometric means of per-case time ratios on cases completed by both configurations; values above 1 mean slower than full. The pair count and completion counts must be read alongside the ratio, since unsolved cases are excluded from that paired statistic. Aggregate ratios alone do not establish statistical significance or an isolated causal effect in the presence of interactions.

Root certificates represent preprocessing that already proves optimality; their cost is timed. Memory percentiles include observed timeout peaks and are not bounds on memory needed to finish. A configuration missing any memory telemetry has its aggregate memory withheld. Instrumented memory timings are not substituted for uninstrumented runtime. Raw records retain failures, individual runs and solver statistics.

Source hashes, release-binary hashes, Rust version, machine details and protocol/selection hashes are recorded in every raw file. The existing abstract Lean proof covers the abstract Pareto reductions, not an end-to-end proof of all solver implementations. Every returned exact layout is checked against the fixed reference optimum, and all frozen configurations have independent exhaustive-width regression tests.

## Reproduce

Use macOS for the RSS collector and a full Git clone containing the frozen protocol commit. Preserve the published records before rerunning: the harness refuses to overwrite existing results. Selection is recomputed from the new validation measurements, so another machine may select different implementations.

```sh
mkdir -p .tools
mv docs/ablation .tools/ablation-published
python3 scripts/ablation_protocol.py
python3 scripts/benchmark_ablation.py validation
python3 scripts/benchmark_ablation.py select
python3 scripts/benchmark_ablation.py minizinc
python3 scripts/benchmark_ablation.py ebooks
python3 scripts/benchmark_ablation.py minizinc --mode memory
python3 scripts/benchmark_ablation.py ebooks --mode memory
python3 scripts/report_ablation.py
```

To regenerate tables from the published measurements without rerunning solvers, run only `python3 scripts/report_ablation.py`. The legacy `report_native.py --suite ebooks|minizinc` command generates the earlier comparison; running it replaces the corresponding README table with that separate experiment.

[Protocol](ablation-protocol.json) · [Locked selection](ablation/selection.json) · [Summary and raw-file hashes](ablation-summary.json) · [Raw records](ablation/)

[Optimization benchmarking guidelines](https://arxiv.org/abs/1709.08242) · [Ablation analysis](https://www.cs.ubc.ca/labs/algorithms/Projects/Ablation/) · [Performance profiles](https://doi.org/10.1007/S101070100263)
