# Native Rust research models

`src/research.rs` builds and solves the research formulations directly in Rust. There is no MiniZinc, FlatZinc, FFI solver binding, or external solver process in the native benchmark.

| CLI / `NativeAlgorithm` | Formulation | Search engine |
| --- | --- | --- |
| `cp2011` / `Cp2011` | Per-cell configuration index, width/height element constraints | Pumpkin 0.5.0, `NoLearningResolver`, `analysis_mode = NoLearning` |
| `lcg2011` / `Lcg2011` | Same configuration model and branching as CP | Pumpkin 0.5.0, `ResolutionResolver`, 1-UIP learning |
| `lcg2015` / `Lcg2015` | Cell-free adjacent-threshold clauses, restricted row/column value domains | Pumpkin 0.5.0, default activity-based brancher and 1-UIP learning |
| `mip2015_unary` / `Mip2015Unary` | Per-cell prefix binary configuration encoding | microlp 0.7.0, LP relaxation and integer branch-and-bound |
| `mip2015_onehot` / `Mip2015Onehot` | Per-cell one-hot configuration encoding | microlp 0.7.0 |
| `mip2015_cellfree` / `Mip2015Cellfree` | Shared row/column unary threshold variables, restricted domains | microlp 0.7.0 |

The models adapt [Gange et al. (2011)](https://doi.org/10.1145/2034691.2034697) and [Bilauca et al. (2015)](https://doi.org/10.1287/ijoc.2014.0637) to this project's rectangular, integer-width input with hard column bounds. They are not reproductions of historical Chuffed or CPLEX engine performance. The earlier [research audit](research-audit.md) records which paper sections and search details were verified.

[Pumpkin](https://github.com/ConSol-Lab/Pumpkin) supplies actual propagation explanations, conflict analysis, learned nogoods, and non-chronological backtracking. The CP control sets `analysis_mode = NoLearning` and uses the chronological `NoLearningResolver`; initial clauses still propagate normally. Configuration CP/LCG both select the unfixed cell with the smallest minimum height, try that minimum first, and break ties in column-major order. Remaining variables are assigned after cell heights. The cell-free variant uses Pumpkin's default brancher. Engine defaults and propagators differ from the original papers.

[microlp](https://docs.rs/microlp/0.7.0/microlp/) supplies a pure Rust LP/MIP solver; its optional HiGHS backend is not enabled. All MIP encodings use a zero optimality gap. Integer widths and objective consistency are checked against the original curves before accepting a result. MIP optimality is still subject to floating-point solver tolerances; this validation is not a rational optimality certificate.

See the [implementation audit](cp-implementation-audit.md) for resource-boundary regressions and the investigation of CP timeouts.

## Model equivalence

Write a cell's minimal staircase as `(a_k, b_k)`, with widths increasing and heights strictly decreasing. Width `w` and row height `h` cover the cell exactly when there exists a configuration `k` with `w >= a_k` and `h >= b_k`.

The configuration model encodes that existence using an index and two element constraints. The one-hot MIP encodes it with `sum(z_k) = 1`, `w >= sum(a_k z_k)`, and `h >= sum(b_k z_k)`.

The unary MIP uses prefix bits `z_2 >= ... >= z_K` and the constant `z_1 = 1`. It requires `w >= a_1 + sum((a_k-a_(k-1)) z_k)` and `h >= b_1 + sum((b_k-b_(k-1)) z_k)`. Every integral prefix selects exactly one configuration, including the first when all explicit bits are zero.

Equivalently, require `w >= a_1`, `h >= b_K`, and, for every adjacent pair, `h >= b_k OR w >= a_(k+1)`. If `w` lies on plateau `k`, that clause requires at least `b_k`; all other clauses follow. This is the cell-free CP model.

For each column, retain its effective hard minimum and all remaining cell breakpoints. Any feasible width can be reduced to the largest retained value below it without changing any cell height or increasing total width. Each actual row height is a maximum of cell heights, hence belongs to their union. These restricted domains preserve an optimum; this is the no-span version of RCSV.

The shared unary MIP encodes each such ordered domain `v_1 < ... < v_K` once: `x = v_1 + sum((v_k-v_(k-1)) b_k)` with prefix bits. The predicate `x >= t` is either a constant or the first corresponding threshold bit. Therefore each cell-free disjunction becomes a linear inequality between at most two shared bits. No per-cell configuration variables are needed. The constant part of the row-height objective is restored when reading the answer.

Common preprocessing clips curves to feasible column bounds and removes equal-height plateaus. The upper bound for a column also subtracts all other columns' effective minima. These operations preserve every relevant cell height. Finally, stretching within caps cannot increase height; a strict decrease would contradict a claimed optimum and is rejected by the implementation.

### Compact model construction

For each row, the maximum of its cells' minimum achievable heights is a valid lower bound. Values below that bound are removed from the row domain. A cell with one remaining configuration then needs no separate configuration variables or constraints: its width and height requirements already follow from the column and row lower bounds. CP and MIP both apply this reduction; the cell-free MIP also drops clauses that contain a constant true predicate.

CP configuration arrays use Pumpkin's literal `i32` elements, rather than creating an integer variable for every constant. Finite domains use bounded variables and one clause `x <= v_i OR x >= v_(i+1)` for each nonempty gap in their sorted allowed values. Together with the outer bounds, these clauses exclude exactly the disallowed integers. Construction depends on the number of allowed values, not the length of the numeric interval. Gap exclusions are ordinary model constraints even when learning is disabled; they do not enable learned clauses in the CP control. Propagation scheduling and explanations can differ from the previous explicit-hole representation.

The nogood arena grows on demand (`memory_preallocated = 0`) instead of reserving 1 MB on its first insertion. These changes preserve feasible layouts and the optimum, while reducing constant domains, hole records, redundant constraints and unused capacity. They do not establish identical search traces or runtimes.

These equivalences are mathematical arguments. The existing Lean development proves the abstract Pareto kernel, not Pumpkin, microlp, or this model construction. Independent integer-width enumeration tests all six new implementations on randomized and adversarial inputs, including plateaus, hard minima, zero-height cells, and infeasible budgets.

### Objective bounds

For row `r`, compute `A_r = sum_j min_w(w * h_jr(w))` over each cell's feasible clipped curve. Its minimum occurs at a plateau start, so there is no enumeration of all integer widths. For any layout, `H_r * B >= H_r * sum_j(w_j) >= sum_j(w_j * h_jr(w_j)) >= A_r`. Therefore `ceil(A_r / B)` is a valid integer lower bound on that row. Combine it with the largest cell minimum, and round up to the next value in the row's allowed height union. Every actual row maximum is in that union, so this rounding also preserves an optimum.

The proportional heuristic supplies a feasible total height `U`. Let the row floors be `L_r` and `L = sum_r L_r`. Restricting the objective to `sum_r H_r <= U` retains a global optimum, though it can discard worse feasible layouts. For each row, `H_r <= U - (L - L_r)` is then valid. These bounds reduce the row domains before model construction. CP uses `U` as the objective-domain upper bound; both MIP encodings add an objective cutoff, with the cell-free constant offset subtracted exactly.

If `L == U`, the feasible layout is already certified optimal and no backend is constructed. Otherwise CP/LCG keep their original branchers and learning settings, and MIP keeps its original integrality requirements and numerical acceptance checks. No shared solver state, cross-call incumbent, or precomputed reference optimum is used. These preprocessing costs and direct certificates are included in the benchmark. A timeout still returns an error, not the feasible heuristic as an alleged optimum.

## Library and limits

```rust
use std::time::Duration;
use table_stretch::{Limits, NativeAlgorithm, Table, solve_measured_with_timeout};

fn compare(table: &Table) -> Result<(), table_stretch::Error> {
    let (layout, phases) = solve_measured_with_timeout(
        table, Limits::default(), NativeAlgorithm::Lcg2015,
        Some(Duration::from_secs(1)),
    )?;
    println!("{} {:?}", layout.total_height, phases);
    Ok(())
}
```

`solve_measured` is the same API without a wall limit. The CLI supports all names above. `Limits` count limits apply to Pareto/A*; the optional wall limit applies to every method and includes validation and construction. Cancellation is cooperative, and a late completion returns an error. The benchmark adds a process watchdog. Timeout results never claim optimality.

The CP backend checks its signed-integer arithmetic bounds and limits estimated construction work to one million model entries. It avoids Pumpkin 0.5.0's explicit-hole sparse constructor; the estimate counts allowed values, gap clauses and nonconstant cell entries. This is a construction-work guard, not a byte-level memory cap. Resource-limit failures are reported separately from wall-clock timeouts. MIP dimensions must fit signed 32-bit integer bounds. These backend limits can reject inputs the original Pareto API supports. Phase fields are `prepare_ns`, `model_ns`, `search_ns`, and `finalize_ns`; model time is zero for algorithms without a solver model. The overall benchmark timer also includes teardown and small call overhead.
