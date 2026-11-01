//! In-process, pure Rust implementations of the research formulations.
//! These reproduce models, not the original Chuffed/CPLEX implementations.
use super::*;
use microlp::{
    ComparisonOp as Op, OptimizationDirection, Problem, SolutionStatus, SolveOutcome, Variable,
};
use pumpkin_conflict_resolvers::resolvers::{NoLearningResolver, ResolutionResolver};
use pumpkin_constraints::{binary_less_than_or_equals, element, equals, less_than_or_equals};
use pumpkin_core::branching::{Brancher, BrancherEvent, SelectionContext};
use pumpkin_core::conflict_resolving::ConflictResolver;
use pumpkin_core::optimisation::{OptimisationDirection, linear_sat_unsat::LinearSatUnsat};
use pumpkin_core::options::{ConflictResolverType, SolverOptions};
use pumpkin_core::predicates::Predicate;
use pumpkin_core::results::{OptimisationResult, ProblemSolution, SolutionReference};
use pumpkin_core::termination::TerminationCondition;
use pumpkin_core::variables::{DomainId, TransformableVariable};
use pumpkin_core::{Solver, predicate};
use std::ops::ControlFlow;

struct Data {
    budget: u32,
    lo: Vec<u32>,
    hi: Vec<u32>,
    cells: Vec<Vec<Vec<Step>>>,
    widths: Vec<Vec<u32>>,
    heights: Vec<Vec<u32>>,
}

fn data(table: &Table, options: AblationOptions) -> Result<Data, Error> {
    let p = prepare(table, false)?;
    let mut d = Data {
        budget: p.budget,
        lo: vec![],
        hi: vec![],
        cells: vec![],
        widths: vec![],
        heights: vec![vec![]; p.rows],
    };
    for (j, col) in table.columns.iter().enumerate() {
        let lo = (p.suffix[j] - p.suffix[j + 1]) as u32;
        let hi = col
            .max_width
            .min((p.budget as u64 - p.suffix[0] + lo as u64) as u32);
        d.lo.push(lo);
        d.hi.push(hi);
        let mut widths = vec![lo];
        let mut cells = vec![];
        for (r, cell) in col.cells.iter().enumerate() {
            let mut steps = vec![Step {
                width: lo,
                height: cell.height_at(lo).unwrap(),
            }];
            for s in &cell.steps {
                if s.width > lo && s.width <= hi && s.height < steps.last().unwrap().height {
                    steps.push(*s);
                }
            }
            widths.extend(steps.iter().map(|s| s.width));
            d.heights[r].extend(steps.iter().map(|s| s.height));
            cells.push(steps);
        }
        widths.sort_unstable();
        widths.dedup();
        d.widths.push(widths);
        d.cells.push(cells);
    }
    for (r, h) in d.heights.iter_mut().enumerate() {
        h.sort_unstable();
        h.dedup();
        // Every row must accommodate even the shortest configuration of each
        // cell. This also folds fixed cells into a shared row lower bound.
        let minimum = d
            .cells
            .iter()
            .map(|c| c[r].last().unwrap().height)
            .max()
            .unwrap();
        // H_r * budget >= sum_j min_w(w * h_jr(w)). Each minimum is
        // attained at a retained plateau start, including the clipped lo.
        let area = if options.area_bound {
            d.cells.iter().try_fold(0u128, |sum, c| {
                sum.checked_add(
                    c[r].iter()
                        .map(|s| s.width as u128 * s.height as u128)
                        .min()
                        .unwrap(),
                )
                .ok_or(Error::Overflow)
            })?
        } else {
            0
        };
        let minimum = (minimum as u128).max(area.div_ceil(d.budget as u128));
        h.retain(|&value| value as u128 >= minimum);
    }
    Ok(d)
}

struct Deadline(Option<Instant>);
impl TerminationCondition for Deadline {
    fn should_stop(&mut self) -> bool {
        self.0.is_some_and(|d| Instant::now() >= d)
    }
}

// Represent a finite value set using bounds and one disjunction per gap.
// Pumpkin's sparse integer constructor records every missing integer; these
// clauses instead exclude whole open intervals with O(number of values) space.
fn discrete_integer(solver: &mut Solver, values: &[u32]) -> DomainId {
    debug_assert!(!values.is_empty() && values.windows(2).all(|p| p[0] < p[1]));
    let var = solver.new_bounded_integer(values[0] as i32, *values.last().unwrap() as i32);
    for pair in values.windows(2) {
        if pair[1] - pair[0] > 1 {
            let tag = solver.new_constraint_tag();
            solver.add_clause(
                [
                    predicate!(var <= pair[0] as i32),
                    predicate!(var >= pair[1] as i32),
                ],
                tag,
            );
        }
    }
    var
}

// 2011 sequential search: select the cell with smallest minimum height,
// try that height first; ties keep the column-major input order.
#[derive(Debug)]
struct CellSearch {
    cells: Vec<DomainId>,
    rest: Vec<DomainId>,
}
impl Brancher for CellSearch {
    fn next_decision(&mut self, c: &mut SelectionContext) -> Option<Predicate> {
        let var = self
            .cells
            .iter()
            .copied()
            .filter(|&v| c.lower_bound(v) < c.upper_bound(v))
            .min_by_key(|&v| c.lower_bound(v))
            .or_else(|| {
                self.rest
                    .iter()
                    .copied()
                    .find(|&v| c.lower_bound(v) < c.upper_bound(v))
            })?;
        Some(predicate!(var == c.lower_bound(var)))
    }
    fn subscribe_to_events(&self) -> Vec<BrancherEvent> {
        vec![]
    }
}

fn optimize<B: Brancher, R: ConflictResolver>(
    solver: &mut Solver,
    brancher: &mut B,
    resolver: &mut R,
    objective: DomainId,
    widths: &[DomainId],
    clock: &PhaseClock,
) -> Result<(Vec<u32>, u64), Error> {
    let callback = |_: &Solver, _: SolutionReference, _: &B, _: &R| -> ControlFlow<()> {
        ControlFlow::Continue(())
    };
    let result = solver.optimise(
        brancher,
        &mut Deadline(clock.deadline),
        resolver,
        LinearSatUnsat::new(OptimisationDirection::Minimise, objective, callback),
    );
    match result {
        OptimisationResult::Optimal(s) => Ok((
            widths
                .iter()
                .map(|&w| s.get_integer_value(w) as u32)
                .collect(),
            s.get_integer_value(objective) as u64,
        )),
        OptimisationResult::Unsatisfiable => Err(Error::Infeasible("CP model")),
        _ => Err(Error::Limit("wall time")),
    }
}

fn cp(
    d: &Data,
    algorithm: NativeAlgorithm,
    clock: &mut PhaseClock,
    upper: Option<u64>,
) -> Result<(Vec<u32>, u64), Error> {
    let no_learning = matches!(algorithm, NativeAlgorithm::Cp2011);
    let cellfree = matches!(algorithm, NativeAlgorithm::Lcg2015);
    // Count model entries, not numeric interval spans. Gap clauses avoid
    // allocating one trail/hole entry per missing integer.
    let sum_h: u64 = d.heights.iter().map(|v| *v.last().unwrap() as u64).sum();
    let sum_w: u64 = d.hi.iter().map(|&v| v as u64).sum();
    if sum_h >= i32::MAX as u64 / 2 || sum_w >= i32::MAX as u64 / 2 {
        return Err(Error::Overflow);
    }
    let mut construction_work = (d.lo.len() + d.heights.len() + 1) as u64;
    if cellfree {
        construction_work += d
            .widths
            .iter()
            .chain(&d.heights)
            .map(|v| v.len() as u64)
            .sum::<u64>();
        construction_work += d
            .cells
            .iter()
            .flatten()
            .map(|c| c.len() as u64)
            .sum::<u64>();
    } else {
        construction_work += d
            .cells
            .iter()
            .flatten()
            .filter(|c| c.len() > 1)
            .map(|c| 3 + 6 * c.len() as u64)
            .sum::<u64>();
    }
    if construction_work > 1_000_000 {
        return Err(Error::Limit("CP model construction"));
    }
    let mut solver = Solver::with_options(SolverOptions {
        analysis_mode: if no_learning {
            ConflictResolverType::NoLearning
        } else {
            ConflictResolverType::OneUIP
        },
        memory_preallocated: 0,
        ..SolverOptions::default()
    });
    let w: Vec<_> =
        d.lo.iter()
            .zip(&d.hi)
            .enumerate()
            .map(|(j, (&lo, &hi))| {
                if cellfree {
                    discrete_integer(&mut solver, &d.widths[j])
                } else {
                    solver.new_bounded_integer(lo as i32, hi as i32)
                }
            })
            .collect();
    let h: Vec<_> = d
        .heights
        .iter()
        .map(|v| {
            if cellfree {
                discrete_integer(&mut solver, v)
            } else {
                solver.new_bounded_integer(*v.first().unwrap() as i32, *v.last().unwrap() as i32)
            }
        })
        .collect();
    let min_h: u32 = d.heights.iter().map(|v| v[0]).sum();
    let objective =
        solver.new_bounded_integer(min_h as i32, sum_h.min(upper.unwrap_or(sum_h)) as i32);
    let tag = solver.new_constraint_tag();
    solver
        .add_constraint(less_than_or_equals(
            w.clone(),
            d.budget.min(sum_w as u32) as i32,
            tag,
        ))
        .post();
    let mut terms: Vec<_> = h.iter().map(|v| v.scaled(1)).collect();
    terms.push(objective.scaled(-1));
    let tag = solver.new_constraint_tag();
    solver.add_constraint(equals(terms, 0, tag)).post();
    let mut cells = vec![];
    let mut rest = w.clone();
    rest.extend(&h);
    rest.push(objective);
    for (j, column) in d.cells.iter().enumerate() {
        clock.check()?;
        for (r, curve) in column.iter().enumerate() {
            // Width is already covered by d.lo; height by the row minimum.
            if curve.len() == 1 {
                continue;
            }
            if cellfree {
                for pair in curve.windows(2) {
                    let tag = solver.new_constraint_tag();
                    solver.add_clause(
                        [
                            predicate!(h[r] >= pair[0].height as i32),
                            predicate!(w[j] >= pair[1].width as i32),
                        ],
                        tag,
                    );
                }
            } else {
                let idx = solver.new_bounded_integer(0, (curve.len() - 1) as i32);
                let ch = discrete_integer(
                    &mut solver,
                    &curve.iter().rev().map(|s| s.height).collect::<Vec<_>>(),
                );
                let cw = discrete_integer(
                    &mut solver,
                    &curve.iter().map(|s| s.width).collect::<Vec<_>>(),
                );
                // Pumpkin supports literal integers in element arrays: no
                // constant domains, watches or trail entries are needed.
                let hs: Vec<_> = curve.iter().map(|s| s.height as i32).collect();
                let ws: Vec<_> = curve.iter().map(|s| s.width as i32).collect();
                let tag = solver.new_constraint_tag();
                solver.add_constraint(element(idx, hs, ch, tag)).post();
                let tag = solver.new_constraint_tag();
                solver.add_constraint(element(idx, ws, cw, tag)).post();
                let tag = solver.new_constraint_tag();
                solver
                    .add_constraint(binary_less_than_or_equals(ch, h[r], tag))
                    .post();
                let tag = solver.new_constraint_tag();
                solver
                    .add_constraint(binary_less_than_or_equals(cw, w[j], tag))
                    .post();
                cells.push(ch);
                rest.extend([idx, cw]);
            }
        }
    }
    clock.check()?;
    // Brancher construction is model setup, not search.
    if cellfree {
        let mut b = solver.default_brancher();
        let mut r = ResolutionResolver::default();
        clock.modeled();
        optimize(&mut solver, &mut b, &mut r, objective, &w, clock)
    } else {
        let mut b = CellSearch { cells, rest };
        if no_learning {
            clock.modeled();
            optimize(
                &mut solver,
                &mut b,
                &mut NoLearningResolver,
                objective,
                &w,
                clock,
            )
        } else {
            let mut r = ResolutionResolver::default();
            clock.modeled();
            optimize(&mut solver, &mut b, &mut r, objective, &w, clock)
        }
    }
}

// Prefix binaries encode a value from a sorted discrete domain. b[k] means
// value >= values[k+1]; the first threshold is the constant true.
struct Unary {
    values: Vec<u32>,
    bits: Vec<Variable>,
}
impl Unary {
    fn new(p: &mut Problem, values: &[u32], cost: f64) -> Self {
        let bits: Vec<_> = values
            .windows(2)
            .map(|v| p.add_binary_var(cost * (v[1] - v[0]) as f64))
            .collect();
        for pair in bits.windows(2) {
            p.add_constraint([(pair[0], 1.), (pair[1], -1.)], Op::Ge, 0.);
        }
        Self {
            values: values.to_vec(),
            bits,
        }
    }
    fn terms(&self) -> Vec<(Variable, f64)> {
        self.bits
            .iter()
            .zip(self.values.windows(2))
            .map(|(&b, v)| (b, (v[1] - v[0]) as f64))
            .collect()
    }
    fn threshold(&self, value: u32) -> (Option<Variable>, f64) {
        let k = self.values.partition_point(|&v| v < value);
        if k == 0 {
            (None, 1.)
        } else if k == self.values.len() {
            (None, 0.)
        } else {
            (Some(self.bits[k - 1]), 0.)
        }
    }
    fn value(&self, s: &microlp::Solution) -> Result<u32, Error> {
        let mut value = self.values[0];
        for (&b, v) in self.bits.iter().zip(self.values.windows(2)) {
            value += integer(s.var_value(b))? * (v[1] - v[0]);
        }
        Ok(value)
    }
}
fn clause(p: &mut Problem, a: (Option<Variable>, f64), b: (Option<Variable>, f64)) {
    if a.1 + b.1 >= 1. {
        return;
    }
    let terms: Vec<_> = [a.0, b.0].into_iter().flatten().map(|v| (v, 1.)).collect();
    p.add_constraint(terms, Op::Ge, 1. - a.1 - b.1);
}
fn integer(value: f64) -> Result<u32, Error> {
    if !value.is_finite()
        || (value - value.round()).abs() > 1e-5
        || value.round() < 0.
        || value.round() > u32::MAX as f64
    {
        return Err(Error::Solver(
            "non-integral or out-of-range assignment".into(),
        ));
    }
    Ok(value.round() as u32)
}
fn mip(
    d: &Data,
    algorithm: NativeAlgorithm,
    clock: &mut PhaseClock,
    upper: Option<u64>,
) -> Result<(Vec<u32>, u64), Error> {
    if d.hi
        .iter()
        .chain(d.heights.iter().flatten())
        .any(|&v| v > i32::MAX as u32)
    {
        return Err(Error::Overflow);
    }
    let mut p = Problem::new(OptimizationDirection::Minimize);
    let cellfree = matches!(algorithm, NativeAlgorithm::Mip2015Cellfree);
    let mut w = vec![];
    let mut uw = vec![];
    let mut offset = 0u64;
    if cellfree {
        uw = d.widths.iter().map(|v| Unary::new(&mut p, v, 0.)).collect();
        let uh: Vec<_> = d
            .heights
            .iter()
            .map(|v| Unary::new(&mut p, v, 1.))
            .collect();
        offset = uh.iter().map(|v| v.values[0] as u64).sum();
        if let Some(upper) = upper {
            p.add_constraint(
                uh.iter().flat_map(Unary::terms).collect::<Vec<_>>(),
                Op::Le,
                (upper - offset) as f64,
            );
        }
        p.add_constraint(
            uw.iter().flat_map(Unary::terms).collect::<Vec<_>>(),
            Op::Le,
            d.budget as f64 - uw.iter().map(|v| v.values[0] as f64).sum::<f64>(),
        );
        for (j, col) in d.cells.iter().enumerate() {
            clock.check()?;
            for (r, curve) in col.iter().enumerate() {
                for pair in curve.windows(2) {
                    clause(
                        &mut p,
                        uh[r].threshold(pair[0].height),
                        uw[j].threshold(pair[1].width),
                    );
                }
            }
        }
    } else {
        w =
            d.lo.iter()
                .zip(&d.hi)
                .map(|(&lo, &hi)| p.add_integer_var(0., (lo as i32, hi as i32)))
                .collect();
        let h: Vec<_> = d
            .heights
            .iter()
            .map(|v| p.add_integer_var(1., (*v.first().unwrap() as i32, *v.last().unwrap() as i32)))
            .collect();
        p.add_constraint(
            w.iter().map(|&v| (v, 1.)).collect::<Vec<_>>(),
            Op::Le,
            d.budget as f64,
        );
        if let Some(upper) = upper {
            p.add_constraint(
                h.iter().map(|&v| (v, 1.)).collect::<Vec<_>>(),
                Op::Le,
                upper as f64,
            );
        }
        for (j, col) in d.cells.iter().enumerate() {
            clock.check()?;
            for (r, curve) in col.iter().enumerate() {
                if curve.len() == 1 {
                    continue;
                }
                let mut wt = vec![(w[j], 1.)];
                let mut ht = vec![(h[r], 1.)];
                if matches!(algorithm, NativeAlgorithm::Mip2015Onehot) {
                    let z: Vec<_> = curve.iter().map(|_| p.add_binary_var(0.)).collect();
                    p.add_constraint(z.iter().map(|&v| (v, 1.)).collect::<Vec<_>>(), Op::Eq, 1.);
                    for (&z, s) in z.iter().zip(curve) {
                        wt.push((z, -(s.width as f64)));
                        ht.push((z, -(s.height as f64)));
                    }
                    p.add_constraint(wt, Op::Ge, 0.);
                    p.add_constraint(ht, Op::Ge, 0.);
                } else {
                    let z: Vec<_> = curve.windows(2).map(|_| p.add_binary_var(0.)).collect();
                    for pair in z.windows(2) {
                        p.add_constraint([(pair[0], 1.), (pair[1], -1.)], Op::Ge, 0.);
                    }
                    for (&z, s) in z.iter().zip(curve.windows(2)) {
                        wt.push((z, -((s[1].width - s[0].width) as f64)));
                        ht.push((z, (s[0].height - s[1].height) as f64));
                    }
                    p.add_constraint(wt, Op::Ge, curve[0].width as f64);
                    p.add_constraint(ht, Op::Ge, curve[0].height as f64);
                }
            }
        }
    }
    clock.check()?;
    if let Some(deadline) = clock.deadline {
        p.set_time_limit(deadline.saturating_duration_since(Instant::now()));
    }
    clock.modeled();
    let solution = match p.solve().map_err(|e| Error::Solver(e.to_string()))? {
        SolveOutcome::Solution(s) if s.status() == SolutionStatus::Optimal => s,
        _ => return Err(Error::Limit("wall time")),
    };
    let widths = if cellfree {
        uw.iter()
            .map(|u| u.value(&solution))
            .collect::<Result<Vec<_>, _>>()?
    } else {
        w.iter()
            .map(|&v| integer(solution.var_value(v)))
            .collect::<Result<Vec<_>, _>>()?
    };
    let objective = solution.objective() + offset as f64;
    if !objective.is_finite()
        || (objective - objective.round()).abs() > 1e-5
        || objective < 0.
        || objective > (1u64 << 53) as f64
    {
        return Err(Error::Solver("invalid MIP objective".into()));
    }
    Ok((widths, objective.round() as u64))
}

pub(super) fn solve_impl(
    table: &Table,
    algorithm: NativeAlgorithm,
    clock: &mut PhaseClock,
    options: AblationOptions,
) -> Result<Layout, Error> {
    let mut d = data(table, options)?;
    let initial = if options.incumbent {
        Some(solve_html(table)?)
    } else {
        None
    };
    let upper = initial.as_ref().map(|layout| layout.total_height);
    let lower = d.heights.iter().try_fold(0u64, |sum, h| {
        sum.checked_add(h[0] as u64).ok_or(Error::Overflow)
    })?;
    // Keep at least one global optimum: the feasible incumbent proves that
    // height > upper is unnecessary. Other rows must still meet their floors.
    if let Some(upper) = upper.filter(|_| options.row_caps) {
        for heights in &mut d.heights {
            let cap = upper - (lower - heights[0] as u64);
            heights.retain(|&h| h as u64 <= cap);
        }
    }
    clock.check()?;
    clock.prepared();
    if options.root_certificate && upper == Some(lower) {
        return finish_measured(
            table,
            d.budget,
            initial.unwrap().column_widths,
            Stats {
                bound_pruned: 1,
                ..Stats::default()
            },
            true,
            Some(clock),
        );
    }
    let (widths, objective) = match algorithm {
        NativeAlgorithm::Cp2011 | NativeAlgorithm::Lcg2011 | NativeAlgorithm::Lcg2015 => {
            cp(&d, algorithm, clock, upper)?
        }
        _ => mip(&d, algorithm, clock, upper)?,
    };
    clock.check()?;
    clock.searched();
    if widths.len() != table.columns.len()
        || widths.iter().map(|&v| v as u64).sum::<u64>() > d.budget as u64
        || widths
            .iter()
            .zip(d.lo.iter().zip(&d.hi))
            .any(|(&w, (&lo, &hi))| w < lo || w > hi)
    {
        return Err(Error::Solver("invalid column widths".into()));
    }
    let mut heights = vec![0; d.heights.len()];
    for (col, &w) in table.columns.iter().zip(&widths) {
        for (h, c) in heights.iter_mut().zip(&col.cells) {
            *h = (*h).max(
                c.height_at(w)
                    .ok_or_else(|| Error::Solver("cell does not fit".into()))?,
            );
        }
    }
    if total_height(&heights)? != objective {
        return Err(Error::Solver(
            "objective disagrees with original profiles".into(),
        ));
    }
    let layout = finish(table, d.budget, widths, Stats::default(), true)?;
    if layout.total_height != objective {
        return Err(Error::Solver("stretch improved claimed optimum".into()));
    }
    clock.times.finalize_ns = clock.start.elapsed().as_nanos();
    Ok(layout)
}
