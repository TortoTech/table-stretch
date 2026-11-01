//! Exact Pareto search with objective bounds and a monotone terminal column.
use super::*;

struct Label<P: Trace> {
    used: u32,
    heights: Vec<u32>,
    path: P,
    tail: u32,
}

pub(super) struct Bounds {
    area: Vec<Vec<u128>>,
    floor: Vec<Vec<u32>>,
}

impl Bounds {
    pub(super) fn configured(
        candidates: &Options,
        rows: usize,
        use_area: bool,
        use_floor: bool,
    ) -> Result<Self, Error> {
        let n = candidates.len();
        let mut area = vec![vec![0u128; rows]; n + 1];
        let mut floor = vec![vec![0; rows]; n + 1];
        for j in (0..n).rev() {
            for r in 0..rows {
                let minimum = if use_area {
                    candidates[j]
                        .iter()
                        .map(|(w, h)| *w as u128 * h[r] as u128)
                        .min()
                        .unwrap()
                } else {
                    0
                };
                area[j][r] = area[j + 1][r].checked_add(minimum).ok_or(Error::Overflow)?;
                if use_floor {
                    floor[j][r] = floor[j + 1][r].max(candidates[j].last().unwrap().1[r]);
                }
            }
        }
        Ok(Self { area, floor })
    }

    // All remaining columns must share `remaining`. Each final row is at least
    // its current height, every remaining cell's minimum height, and the sum
    // of remaining minimum cell areas divided by remaining width.
    fn cannot_improve(
        &self,
        heights: &[u32],
        next: usize,
        remaining: u32,
        upper: u64,
    ) -> Result<bool, Error> {
        Ok(self.lower_bound(heights, next, remaining, upper)? >= upper)
    }

    // Stop accumulating once a caller's incumbent has already been reached.
    pub(super) fn lower_bound(
        &self,
        heights: &[u32],
        next: usize,
        remaining: u32,
        upper: u64,
    ) -> Result<u64, Error> {
        let mut lower = 0u64;
        for (r, &height) in heights.iter().enumerate() {
            let area = if next + 1 == self.area.len() {
                0
            } else {
                self.area[next][r].div_ceil(remaining as u128)
            };
            let value = area.max(height as u128).max(self.floor[next][r] as u128);
            lower = lower
                .checked_add(u64::try_from(value).map_err(|_| Error::Overflow)?)
                .ok_or(Error::Overflow)?;
            if lower >= upper {
                return Ok(lower);
            }
        }
        Ok(lower)
    }
}

struct Incumbent {
    height: u64,
    widths: Vec<u32>,
}

impl Incumbent {
    // The prefix has n-1 columns. Increasing the final width cannot increase
    // height, so one endpoint replaces all final-column choices. A pending
    // penultimate width is not allocated in the path arena.
    fn complete<P: Trace>(
        &mut self,
        table: &Table,
        prefix: &Label<P>,
        pending: Option<u32>,
        arena: &[TraceLink],
        stats: &mut Stats,
    ) -> Result<(), Error> {
        stats.terminal_evaluations = stats
            .terminal_evaluations
            .checked_add(1)
            .ok_or(Error::Overflow)?;
        let last = table.columns.last().unwrap();
        let width = last
            .max_width
            .min(table.width - table.reserved_width - prefix.used);
        let mut height = 0u64;
        for (&old, cell) in prefix.heights.iter().zip(&last.cells) {
            height = height
                .checked_add(old.max(cell.height_at(width).unwrap()) as u64)
                .ok_or(Error::Overflow)?;
            // Unvisited rows have nonnegative heights.
            if height >= self.height {
                return Ok(());
            }
        }
        let mut widths = prefix.path.widths(arena);
        if let Some(w) = pending {
            widths.push(w);
        }
        widths.push(width);
        self.height = height;
        self.widths = widths;
        stats.incumbent_updates += 1;
        Ok(())
    }
}

fn compare(stats: &mut Stats, limits: Limits) -> Result<(), Error> {
    if stats.comparisons >= limits.max_comparisons {
        return Err(Error::Limit("dominance comparisons"));
    }
    stats.comparisons += 1;
    Ok(())
}

pub(super) fn solve_impl(
    table: &Table,
    limits: Limits,
    clock: Option<&mut PhaseClock>,
) -> Result<Layout, Error> {
    solve_configured(table, limits, clock, AblationOptions::default())
}

pub(super) fn solve_configured(
    table: &Table,
    limits: Limits,
    clock: Option<&mut PhaseClock>,
    options: AblationOptions,
) -> Result<Layout, Error> {
    if options.compact_paths {
        search::<Option<usize>>(table, limits, clock, options)
    } else {
        search::<Vec<u32>>(table, limits, clock, options)
    }
}
fn search<P: Trace>(
    table: &Table,
    limits: Limits,
    mut clock: Option<&mut PhaseClock>,
    options: AblationOptions,
) -> Result<Layout, Error> {
    if limits.max_generated == 0 || limits.max_comparisons == 0 || limits.max_frontier == 0 {
        return Err(Error::Invalid("search limits must be positive"));
    }
    let Prepared {
        budget,
        rows,
        mut candidates,
        suffix,
    } = prepare(table, true)?;
    // Tighten each column using the mandatory minima of every other column.
    // This cap is global, so it remains valid under every search prefix.
    if options.column_caps {
        for (j, options) in candidates.iter_mut().enumerate() {
            let cap = budget as u64 - (suffix[0] - (suffix[j] - suffix[j + 1]));
            options.truncate(options.partition_point(|(w, _)| *w as u64 <= cap));
        }
    }
    let bounds = Bounds::configured(&candidates, rows, options.area_bound, options.floor_bound)?;
    let mut best = if options.incumbent {
        let initial = solve_html(table)?;
        Incumbent {
            height: initial.total_height,
            widths: initial.column_widths,
        }
    } else {
        Incumbent {
            height: u64::MAX,
            widths: vec![],
        }
    };
    let mut stats = Stats {
        candidates_per_column: candidates.iter().map(Vec::len).collect(),
        peak_frontier: 1,
        ..Stats::default()
    };
    let root = Label {
        used: 0,
        heights: vec![0; rows],
        path: P::root(),
        tail: 0,
    };
    if let Some(clock) = clock.as_deref_mut() {
        clock.prepared();
    }
    if bounds.cannot_improve(&root.heights, 0, budget, best.height)? {
        stats.bound_pruned += 1;
        return finish_measured(table, budget, best.widths, stats, true, clock);
    }
    let n = candidates.len();
    let mut arena = Vec::new();
    if options.terminal_column && n == 1 {
        best.complete(table, &root, None, &arena, &mut stats)?;
        return finish_measured(table, budget, best.widths, stats, true, clock);
    }
    let mut frontier = vec![root];
    let mut scratch = Label {
        used: 0,
        heights: vec![0; rows],
        path: P::root(),
        tail: 0,
    };
    for j in 0..if options.terminal_column { n - 1 } else { n } {
        let mut next: Vec<Label<P>> = Vec::new();
        for state in &frontier {
            if let Some(clock) = clock.as_deref() {
                clock.check()?;
            }
            if bounds.cannot_improve(&state.heights, j, budget - state.used, best.height)? {
                stats.bound_pruned += 1;
                continue;
            }
            let available = budget as u64 - state.used as u64 - suffix[j + 1];
            let end = candidates[j].partition_point(|(w, _)| *w as u64 <= available);
            for (width, heights) in candidates[j][..end].iter().rev() {
                if stats.generated >= limits.max_generated {
                    return Err(Error::Limit("generated states"));
                }
                stats.generated += 1;
                scratch.used = state.used + *width;
                scratch.path = state.path.clone();
                scratch.tail = *width;
                for ((dest, &old), &new) in
                    scratch.heights.iter_mut().zip(&state.heights).zip(heights)
                {
                    *dest = old.max(new);
                }
                if options.terminal_column && j + 2 == n {
                    // No frontier is needed for the penultimate or last column.
                    best.complete(table, &scratch, Some(*width), &arena, &mut stats)?;
                    continue;
                }
                if j + 1 == n {
                    let height = total_height(&scratch.heights)?;
                    if height < best.height {
                        best.height = height;
                        best.widths = scratch.path.widths(&arena);
                        best.widths.push(*width);
                        stats.incumbent_updates += 1;
                    }
                    continue;
                }
                if bounds.cannot_improve(
                    &scratch.heights,
                    j + 1,
                    budget - scratch.used,
                    best.height,
                )? {
                    stats.bound_pruned += 1;
                    continue;
                }
                let mut rejected = false;
                for old in &next {
                    compare(&mut stats, limits)?;
                    if old.used <= scratch.used
                        && old
                            .heights
                            .iter()
                            .zip(&scratch.heights)
                            .all(|(a, b)| a <= b)
                    {
                        rejected = true;
                        break;
                    }
                }
                if rejected {
                    stats.pruned += 1;
                    continue;
                }
                // Check rejection first, then delete in place. No rebuilding
                // of the whole frontier and no allocation for rejected labels.
                let mut index = 0;
                while index < next.len() {
                    compare(&mut stats, limits)?;
                    let old = &next[index];
                    if scratch.used <= old.used
                        && scratch
                            .heights
                            .iter()
                            .zip(&old.heights)
                            .all(|(a, b)| a <= b)
                    {
                        next.swap_remove(index);
                        stats.pruned += 1;
                    } else {
                        index += 1;
                    }
                }
                if next.len() >= limits.max_frontier {
                    return Err(Error::Limit("frontier size"));
                }
                next.push(Label {
                    used: scratch.used,
                    heights: std::mem::replace(&mut scratch.heights, vec![0; rows]),
                    path: scratch.path.clone(),
                    tail: scratch.tail,
                });
                stats.peak_frontier = stats.peak_frontier.max(next.len());
            }
        }
        // Allocate a path node only after the entire layer has been pruned.
        for label in &mut next {
            label.path = label.path.append(label.tail, &mut arena);
        }
        frontier = next;
        if frontier.is_empty() {
            break;
        }
    }
    finish_measured(table, budget, best.widths, stats, true, clock)
}
