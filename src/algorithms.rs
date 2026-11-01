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

struct Node<P: Trace> {
    bound: u64,
    serial: u64,
    depth: usize,
    used: u32,
    heights: Vec<u32>,
    path: P,
}
impl<P: Trace> PartialEq for Node<P> {
    fn eq(&self, other: &Self) -> bool {
        self.cmp(other) == Ordering::Equal
    }
}
impl<P: Trace> Eq for Node<P> {}
impl<P: Trace> PartialOrd for Node<P> {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}
impl<P: Trace> Ord for Node<P> {
    fn cmp(&self, other: &Self) -> Ordering {
        other
            .bound
            .cmp(&self.bound)
            .then_with(|| self.depth.cmp(&other.depth))
            .then_with(|| other.serial.cmp(&self.serial))
    }
}

struct Incumbent {
    height: u64,
    widths: Vec<u32>,
}
impl Incumbent {
    fn complete<P: Trace>(
        &mut self,
        table: &Table,
        prefix: &Node<P>,
        arena: &[TraceLink],
        stats: &mut Stats,
    ) -> Result<(), Error> {
        stats.terminal_evaluations += 1;
        let last = table.columns.last().unwrap();
        let width = last
            .max_width
            .min(table.width - table.reserved_width - prefix.used);
        let mut height = 0u64;
        for (&old, cell) in prefix.heights.iter().zip(&last.cells) {
            height = height
                .checked_add(old.max(cell.height_at(width).unwrap()) as u64)
                .ok_or(Error::Overflow)?;
            if height >= self.height {
                return Ok(());
            }
        }
        let mut widths = prefix.path.widths(arena);
        widths.push(width);
        self.height = height;
        self.widths = widths;
        stats.incumbent_updates += 1;
        Ok(())
    }
}

/// Gange et al. (DocEng 2011) best-first search and column-minimality pruning,
/// enhanced with a feasible incumbent, area/floor bounds, a terminal-column
/// shortcut, and parent links. Supports simple cells, without spans.
pub fn solve_astar(table: &Table, limits: Limits) -> Result<Layout, Error> {
    astar_impl(table, limits, None)
}

pub(super) fn astar_impl(
    table: &Table,
    limits: Limits,
    clock: Option<&mut PhaseClock>,
) -> Result<Layout, Error> {
    astar_configured(table, limits, clock, AblationOptions::default())
}

pub(super) fn astar_configured(
    table: &Table,
    limits: Limits,
    clock: Option<&mut PhaseClock>,
    options: AblationOptions,
) -> Result<Layout, Error> {
    if options.compact_paths {
        astar_search::<Option<usize>>(table, limits, clock, options)
    } else {
        astar_search::<Vec<u32>>(table, limits, clock, options)
    }
}

fn astar_search<P: Trace>(
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
    if options.column_caps {
        for (j, options) in candidates.iter_mut().enumerate() {
            let cap = budget as u64 - (suffix[0] - (suffix[j] - suffix[j + 1]));
            options.truncate(options.partition_point(|(w, _)| *w as u64 <= cap));
        }
    }
    let bounds =
        pareto::Bounds::configured(&candidates, rows, options.area_bound, options.floor_bound)?;
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
        peak_frontier: 1,
        candidates_per_column: candidates.iter().map(Vec::len).collect(),
        ..Stats::default()
    };
    let root = Node {
        bound: bounds.lower_bound(&vec![0; rows], 0, budget, best.height)?,
        serial: 0,
        depth: 0,
        used: 0,
        heights: vec![0; rows],
        path: P::root(),
    };
    if let Some(clock) = clock.as_deref_mut() {
        clock.prepared();
    }
    let n = table.columns.len();
    let mut heap = BinaryHeap::new();
    let mut arena: Vec<TraceLink> = Vec::new();
    heap.push(root);
    while let Some(node) = heap.pop() {
        if let Some(clock) = clock.as_deref() {
            clock.check()?;
        }
        // A completed tail only updates the incumbent. Stop when no OPEN
        // lower bound can beat it, not at the first generated complete layout.
        if node.bound >= best.height {
            stats.bound_pruned += 1;
            break;
        }
        let j = node.depth;
        if j == n {
            let height = total_height(&node.heights)?;
            if height < best.height {
                best.height = height;
                best.widths = node.path.widths(&arena);
                stats.incumbent_updates += 1;
            }
            continue;
        }
        if options.terminal_column && j + 1 == n {
            best.complete(table, &node, &arena, &mut stats)?;
            continue;
        }
        let available = budget as u64 - node.used as u64 - suffix[j + 1];
        let end = candidates[j].partition_point(|(w, _)| *w as u64 <= available);
        for (w, h) in candidates[j][..end].iter().rev() {
            if stats.generated >= limits.max_generated {
                return Err(Error::Limit("generated states"));
            }
            stats.generated += 1;
            let mut child = Node {
                bound: 0,
                serial: stats.generated,
                depth: j + 1,
                used: node.used + *w,
                heights: node
                    .heights
                    .iter()
                    .zip(h)
                    .map(|(&a, &b)| a.max(b))
                    .collect(),
                path: P::root(),
            };
            child.bound = bounds.lower_bound(
                &child.heights,
                child.depth,
                budget - child.used,
                best.height,
            )?;
            if child.bound >= best.height {
                stats.bound_pruned += 1;
                continue;
            }
            // Check the new column and then traverse the prefix without
            // allocating/copying an entire width vector for each queue entry.
            let mut minimal = true;
            let widths = std::iter::once(*w).chain(node.path.reversed(&arena));
            for (c, width) in (0..=j).rev().zip(widths) {
                if width as u64 != suffix[c] - suffix[c + 1] {
                    let mut witness = false;
                    for (r, cell) in table.columns[c].cells.iter().enumerate() {
                        if stats.comparisons >= limits.max_comparisons {
                            return Err(Error::Limit("column minimality checks"));
                        }
                        stats.comparisons += 1;
                        if cell
                            .height_at(width - 1)
                            .is_none_or(|height| height > child.heights[r])
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
            }
            if !minimal {
                stats.pruned += 1;
                continue;
            }
            // Last-column evaluation needs the current link only transiently.
            let checkpoint = arena.len();
            child.path = node.path.append(*w, &mut arena);
            if options.terminal_column && child.depth + 1 == n {
                best.complete(table, &child, &arena, &mut stats)?;
                arena.truncate(checkpoint);
                continue;
            }
            if heap.len() >= limits.max_frontier {
                return Err(Error::Limit("priority queue size"));
            }
            heap.push(child);
            stats.peak_frontier = stats.peak_frontier.max(heap.len());
        }
    }
    finish_measured(table, budget, best.widths, stats, true, clock)
}
