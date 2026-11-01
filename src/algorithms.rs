use super::*;
use std::{cmp::Ordering, collections::BinaryHeap};

/// W3C historical min/preferred proportional sizing, adapted to integer units,
/// explicit hard column bounds and mandatory full-container stretching.
/// A heuristic: optimal is always false, even if it happens to hit the optimum.
pub fn solve_html(table: &Table) -> Result<Layout, Error> {
    html_impl(table, None)
}

pub(super) fn html_impl(
    table: &Table,
    mut clock: Option<&mut PhaseClock>,
) -> Result<Layout, Error> {
    let Prepared { budget, suffix, .. } = prepare(table, false)?;
    let mut widths: Vec<_> = suffix.windows(2).map(|s| (s[0] - s[1]) as u32).collect();
    let preferred: Vec<_> = table
        .columns
        .iter()
        .zip(&widths)
        .map(|(c, &min)| {
            c.cells
                .iter()
                .map(|p| p.steps.last().unwrap().width)
                .max()
                .unwrap()
                .max(min)
                .min(c.max_width)
        })
        .collect();
    let capacity: u64 = preferred
        .iter()
        .zip(&widths)
        .map(|(&p, &w)| (p - w) as u64)
        .sum();
    let extra = (budget as u64 - suffix[0]).min(capacity);
    if let Some(clock) = clock.as_deref_mut() {
        clock.prepared();
    }
    for (w, &p) in widths.iter_mut().zip(&preferred) {
        *w += (extra * (p - *w) as u64).checked_div(capacity).unwrap_or(0) as u32;
    }
    finish_measured(table, budget, widths, Stats::default(), false, clock)
}

struct Node {
    bound: u64,
    serial: u64,
    state: State,
}
impl PartialEq for Node {
    fn eq(&self, other: &Self) -> bool {
        self.cmp(other) == Ordering::Equal
    }
}
impl Eq for Node {}
impl PartialOrd for Node {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}
impl Ord for Node {
    fn cmp(&self, other: &Self) -> Ordering {
        other
            .bound
            .cmp(&self.bound)
            .then_with(|| self.state.widths.len().cmp(&other.state.widths.len()))
            .then_with(|| other.serial.cmp(&self.serial))
    }
}

fn lower_bound(state: &State, budget: u32, areas: &[Vec<u128>]) -> Result<u64, Error> {
    let depth = state.widths.len();
    let remaining = (budget - state.used) as u128;
    let mut bound = 0u64;
    for (r, &height) in state.heights.iter().enumerate() {
        let estimate = if depth + 1 == areas.len() {
            0
        } else {
            // Positive minimum widths guarantee remaining > 0 before a leaf.
            areas[depth][r].div_ceil(remaining)
        };
        let value = u64::try_from(estimate.max(height as u128)).map_err(|_| Error::Overflow)?;
        bound = bound.checked_add(value).ok_or(Error::Overflow)?;
    }
    Ok(bound)
}

/// Gange et al. (DocEng 2011), section 3: best-first search, remaining-area
/// lower bound, depth tie-break, and weak column-minimality pruning.
/// This implementation supports only simple cells and adds integer bounds.
/// It omits their optional heuristic incumbent and spanning-cell machinery.
pub fn solve_astar(table: &Table, limits: Limits) -> Result<Layout, Error> {
    astar_impl(table, limits, None)
}

pub(super) fn astar_impl(
    table: &Table,
    limits: Limits,
    mut clock: Option<&mut PhaseClock>,
) -> Result<Layout, Error> {
    if limits.max_generated == 0 || limits.max_comparisons == 0 || limits.max_frontier == 0 {
        return Err(Error::Invalid("search limits must be positive"));
    }
    let Prepared {
        budget,
        rows,
        candidates,
        suffix,
    } = prepare(table, true)?;
    let n = table.columns.len();
    let mut areas = vec![vec![0u128; rows]; n + 1];
    for j in (0..n).rev() {
        for r in 0..rows {
            let minimum = candidates[j]
                .iter()
                .map(|(w, h)| *w as u128 * h[r] as u128)
                .min()
                .unwrap();
            areas[j][r] = areas[j + 1][r]
                .checked_add(minimum)
                .ok_or(Error::Overflow)?;
        }
    }
    if let Some(clock) = clock.as_deref_mut() {
        clock.prepared();
    }
    let initial = State {
        used: 0,
        heights: vec![0; rows],
        widths: vec![],
    };
    let mut heap = BinaryHeap::new();
    heap.push(Node {
        bound: lower_bound(&initial, budget, &areas)?,
        serial: 0,
        state: initial,
    });
    let mut stats = Stats {
        peak_frontier: 1,
        candidates_per_column: candidates.iter().map(Vec::len).collect(),
        ..Stats::default()
    };
    while let Some(node) = heap.pop() {
        let j = node.state.widths.len();
        if j == n {
            return finish_measured(table, budget, node.state.widths, stats, true, clock);
        }
        for (w, h) in candidates[j].iter().rev() {
            if stats.generated >= limits.max_generated {
                return Err(Error::Limit("generated states"));
            }
            stats.generated += 1;
            let used = node.state.used as u64 + *w as u64;
            if used + suffix[j + 1] > budget as u64 {
                continue;
            }
            let mut state = State {
                used: used as u32,
                heights: node
                    .state
                    .heights
                    .iter()
                    .zip(h)
                    .map(|(&a, &b)| a.max(b))
                    .collect(),
                widths: node.state.widths.clone(),
            };
            state.widths.push(*w);
            // A prefix is column-minimal iff every column above its minimum
            // has some cell that would exceed the row height if narrowed.
            let mut minimal = true;
            for (c, &width) in state.widths.iter().enumerate() {
                if width as u64 == suffix[c] - suffix[c + 1] {
                    continue;
                }
                let mut witness = false;
                for (r, cell) in table.columns[c].cells.iter().enumerate() {
                    if stats.comparisons >= limits.max_comparisons {
                        return Err(Error::Limit("column minimality checks"));
                    }
                    stats.comparisons += 1;
                    if cell
                        .height_at(width - 1)
                        .is_none_or(|height| height > state.heights[r])
                    {
                        witness = true;
                        break;
                    }
                }
                if !witness {
                    minimal = false;
                    break;
                }
            }
            if !minimal {
                stats.pruned += 1;
                continue;
            }
            let bound = lower_bound(&state, budget, &areas)?;
            if heap.len() >= limits.max_frontier {
                return Err(Error::Limit("priority queue size"));
            }
            heap.push(Node {
                bound,
                serial: stats.generated,
                state,
            });
            stats.peak_frontier = stats.peak_frontier.max(heap.len());
        }
    }
    Err(Error::Infeasible("no layout"))
}
