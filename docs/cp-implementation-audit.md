# Native CP implementation audit

Reviewed baseline: [`5d3d36b`](https://github.com/TortoTech/table-stretch/tree/5d3d36b300b976eae8bd4acb410fc2b7326922b8).

No incorrect optimum was found in the tested inputs. Three implementation issues were found and fixed; they concern resource handling and benchmark robustness, rather than the table feasibility model.

## Findings and fixes

1. **Incorrect CP construction guard.** The old estimate charged absolute widths/heights as though every bounded domain were a dense bitset. Pumpkin 0.5.0 stores bounded domains compactly. A single fixed cell with width 1 and height 6,000,000 was incorrectly rejected with `Limit("CP domain allocation")`; the added regression failed on the baseline. Conversely, sparse domains scan the entire interval and materialize each hole. The guard now estimates sparse interval scans and model entries, with a one-million-entry cap before solver allocation. Large fixed values are accepted within the backend's signed arithmetic bounds. This is a work estimate, not a hard memory limit.
2. **Resource errors mislabeled as timeouts.** The native worker classified every `Error::Limit` as `timeout`, including immediate model-construction rejection. Only `Limit("wall time")` is now a timeout; other count/resource limits are recorded as `resource_limit` and remain unfinished cases in the common scoring. The six original CP timeout cases had actual wall-time errors near one second, so this issue did not cause those six failures.
3. **Incomplete hard watchdog.** `select()` followed by blocking `readline()` could hang after a partial response; waiting for process exit after stdout EOF could also block indefinitely. The worker now reads chunks against one absolute response deadline and kills/reaps a stalled process. Regression tests cover partial output and a process that closes stdout but remains alive.

## CP model and search review

- Curves are clipped to feasible column bounds, retain the effective hard minimum, and discard equal-height dominated configurations.
- Each cell has one configuration index and width/height element constraints. Column width and row height dominate the selected dimensions; the global width budget and sum-of-row-heights objective are enforced.
- The brancher selects the unfixed cell with the lowest minimum remaining height, tries that minimum, and keeps column-major ties. Configuration heights uniquely identify indices after plateau removal. Remaining width/height/index variables are assigned before declaring a solution.
- CP uses `NoLearningResolver`: chronological backtracking and negation of the last decision. LCG uses `ResolutionResolver`. `analysis_mode = NoLearning` still allows ordinary initial-clause propagation; it does not disable constraint propagation. The static brancher reports restarts as pointless.
- Optimization repeatedly asks for a strictly smaller objective. Only an `Optimal` result is accepted; feasible incumbents at timeout are not marked optimal. Returned widths, original cell heights, objective consistency, and final stretching are checked independently of the backend model.

The model and cell selection match the relevant descriptions in [Gange et al. (2011), sections 4 and 6](https://www.researchgate.net/publication/221353238_Optimal_automatic_table_layout). This does not establish identical propagation, tie behavior, or performance to historical Chuffed. In particular, the older Gecode benchmark used column-width branching, while this CP control uses cell-height branching. Its result cannot diagnose a bug in this implementation by timing alone.

The pinned Pumpkin sources checked were `engine/cp/assignments.rs`, `engine/constraint_satisfaction_solver.rs`, `optimisation/linear_sat_unsat.rs`, `branching/brancher.rs`, the element propagator, and the no-learning resolver. Sparse construction and resolver behavior were checked in code rather than inferred from solver labels.

## Validation

Independent integer-width enumeration exercises all six research implementations. Added cases cover large fixed units, sparse domains with large gaps, and discontinuous configurations requiring backtracking. CLI integration, timeout classification, watchdog cleanup, formatting, Clippy, and the existing Lean checks also pass. The Lean proof remains a proof of the abstract Pareto algorithm, not the CP engine.

The six original slow CP cases were also retried with a five-second budget, alongside the same configuration model with learning enabled. [Diagnostic records](cp-audit-diagnostics.json) include input hashes, exact statuses, measured times and returned layouts. One CP case completed in 1.355 seconds; five still reached the five-second limit. Configuration LCG completed all six in 9.9–19.8 ms with matching optimum heights. This supports a search-efficiency explanation for these cases, not a general claim about every CP engine. This is a single-run diagnostic, separate from the full [one-second benchmark](benchmark-native.md).

```sh
bash scripts/check.sh
cargo build --locked --release --example native_worker
python3 scripts/audit_cp.py
python3 scripts/benchmark_native.py
python3 scripts/report_native.py
```
