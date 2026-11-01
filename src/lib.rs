//! Exact minimum-height rectangular table layout. See docs/proof.md for the
//! model and proof, and proof/Optimality.lean for the verified abstract kernel.
//! Widths/heights are integer layout units, not necessarily physical pixels.

use serde::{Deserialize, Serialize};
use std::fmt;
use std::time::Instant;

/// Instrumentation for the native benchmark only; ordinary solve calls do not
/// read clocks. Search includes search-state initialization, not final stretch.
#[derive(Default, Debug, Serialize)]
pub struct PhaseTimes {
    pub prepare_ns: u128,
    pub search_ns: u128,
    pub finalize_ns: u128,
}

pub enum NativeAlgorithm {
    Pareto,
    Astar2011,
    Html,
}

struct PhaseClock {
    start: Instant,
    times: PhaseTimes,
}
impl PhaseClock {
    fn prepared(&mut self) {
        self.times.prepare_ns = self.start.elapsed().as_nanos();
        self.start = Instant::now();
    }
    fn searched(&mut self) {
        self.times.search_ns = self.start.elapsed().as_nanos();
        self.start = Instant::now();
    }
}

pub fn solve_measured(
    table: &Table,
    limits: Limits,
    algorithm: NativeAlgorithm,
) -> Result<(Layout, PhaseTimes), Error> {
    let mut clock = PhaseClock {
        start: Instant::now(),
        times: PhaseTimes::default(),
    };
    let layout = match algorithm {
        NativeAlgorithm::Pareto => solve_impl(table, limits, Some(&mut clock)),
        NativeAlgorithm::Astar2011 => algorithms::astar_impl(table, limits, Some(&mut clock)),
        NativeAlgorithm::Html => algorithms::html_impl(table, Some(&mut clock)),
    }?;
    Ok((layout, clock.times))
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Step {
    pub width: u32,
    pub height: u32,
}

/// Complete non-increasing height staircase. Below the first width the cell
/// does not fit; above the last width its height is constant.
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Profile {
    pub steps: Vec<Step>,
}

impl Profile {
    fn validate(&self) -> Result<(), Error> {
        if self.steps.is_empty()
            || self.steps.iter().any(|s| s.width == 0)
            || self
                .steps
                .windows(2)
                .any(|s| s[0].width >= s[1].width || s[0].height < s[1].height)
        {
            return Err(Error::Invalid(
                "profile widths must increase and heights must not increase",
            ));
        }
        Ok(())
    }

    /// Requires a valid profile (solve validates all input profiles).
    pub fn height_at(&self, width: u32) -> Option<u32> {
        let i = self.steps.partition_point(|s| s.width <= width);
        i.checked_sub(1).map(|j| self.steps[j].height)
    }

    /// Ordered, unbreakable tokens with measured widths, a fixed inter-token
    /// gap, and constant line height. No hyphenation or forced line breaks.
    /// Greedy wrapping minimizes line count for this particular text model.
    pub fn from_tokens(tokens: &[u32], gap: u32, line_height: u32) -> Result<Self, Error> {
        if line_height == 0 || tokens.contains(&0) {
            return Err(Error::Invalid(
                "token widths and line height must be positive",
            ));
        }
        if tokens.is_empty() {
            return Ok(Self {
                steps: vec![Step {
                    width: 1,
                    height: 0,
                }],
            });
        }
        let total = tokens
            .iter()
            .try_fold(0u64, |a, &v| a.checked_add(v as u64))
            .ok_or(Error::Overflow)?;
        let gaps = (tokens.len() as u64 - 1)
            .checked_mul(gap as u64)
            .ok_or(Error::Overflow)?;
        let end = u32::try_from(total.checked_add(gaps).ok_or(Error::Overflow)?)
            .map_err(|_| Error::Overflow)?;
        let height = |width: u32| -> Result<u32, Error> {
            let mut lines = 1u32;
            let mut used = tokens[0] as u64;
            for &token in &tokens[1..] {
                let next = used + gap as u64 + token as u64;
                if next <= width as u64 {
                    used = next;
                } else {
                    lines = lines.checked_add(1).ok_or(Error::Overflow)?;
                    used = token as u64;
                }
            }
            lines.checked_mul(line_height).ok_or(Error::Overflow)
        };
        let mut width = *tokens.iter().max().unwrap();
        let mut steps = Vec::new();
        loop {
            let h = height(width)?;
            steps.push(Step { width, height: h });
            if h == line_height {
                break;
            }
            // First integer width that reduces height; no per-pixel scan.
            let (mut lo, mut hi) = (width + 1, end);
            while lo < hi {
                let mid = lo + (hi - lo) / 2;
                if height(mid)? < h {
                    hi = mid;
                } else {
                    lo = mid + 1;
                }
            }
            width = lo;
        }
        Ok(Self { steps })
    }
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Column {
    pub min_width: u32,
    pub max_width: u32,
    /// One profile per row, in row order.
    pub cells: Vec<Profile>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Table {
    pub width: u32,
    /// Total fixed horizontal space for borders, gaps, etc. Cell padding must
    /// already be included in the cell profiles if it affects wrapping.
    #[serde(default)]
    pub reserved_width: u32,
    pub columns: Vec<Column>,
}

#[derive(Clone, Copy, Debug)]
pub struct Limits {
    pub max_generated: u64,
    pub max_comparisons: u64,
    pub max_frontier: usize,
}

impl Default for Limits {
    fn default() -> Self {
        Self {
            max_generated: 1_000_000,
            max_comparisons: 20_000_000,
            max_frontier: 10_000,
        }
    }
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct Stats {
    pub generated: u64,
    pub comparisons: u64,
    pub pruned: u64,
    pub peak_frontier: usize,
    pub candidates_per_column: Vec<usize>,
}

#[derive(Clone, Debug, Serialize)]
pub struct Layout {
    /// True only when a successful exact solver established optimality.
    pub optimal: bool,
    pub column_widths: Vec<u32>,
    pub row_heights: Vec<u32>,
    pub total_height: u64,
    pub stats: Stats,
}

#[derive(Debug, PartialEq, Eq)]
pub enum Error {
    Invalid(&'static str),
    Infeasible(&'static str),
    Limit(&'static str),
    Overflow,
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Invalid(s) => write!(f, "invalid input: {s}"),
            Self::Infeasible(s) => write!(f, "infeasible: {s}"),
            Self::Limit(s) => write!(f, "search limit reached ({s}); optimality not established"),
            Self::Overflow => write!(f, "layout arithmetic exceeds supported integer range"),
        }
    }
}
impl std::error::Error for Error {}

#[derive(Clone)]
struct State {
    used: u32,
    heights: Vec<u32>,
    widths: Vec<u32>,
}

fn dominates(a: &State, b: &State) -> bool {
    a.used <= b.used && a.heights.iter().zip(&b.heights).all(|(x, y)| x <= y)
}

fn total_height(heights: &[u32]) -> Result<u64, Error> {
    heights
        .iter()
        .try_fold(0u64, |a, &b| a.checked_add(b as u64))
        .ok_or(Error::Overflow)
}

type Options = Vec<Vec<(u32, Vec<u32>)>>;
struct Prepared {
    budget: u32,
    rows: usize,
    candidates: Options,
    suffix: Vec<u64>,
}
fn prepare(table: &Table, build_candidates: bool) -> Result<Prepared, Error> {
    if table.columns.is_empty() || table.columns[0].cells.is_empty() {
        return Err(Error::Invalid("at least one column and one row required"));
    }
    let budget = table
        .width
        .checked_sub(table.reserved_width)
        .ok_or(Error::Infeasible(
            "fixed horizontal space exceeds container",
        ))?;
    let rows = table.columns[0].cells.len();
    let mut candidates = Vec::new();
    let mut minimums = Vec::new();
    let mut max_sum = 0u64;
    for col in &table.columns {
        if col.min_width == 0 || col.min_width > col.max_width || col.cells.len() != rows {
            return Err(Error::Invalid(
                "invalid column bounds or non-rectangular table",
            ));
        }
        let mut min = col.min_width;
        for cell in &col.cells {
            cell.validate()?;
            min = min.max(cell.steps[0].width);
        }
        if min > col.max_width {
            return Err(Error::Infeasible("cell cannot fit within column maximum"));
        }
        if build_candidates {
            let mut widths = vec![min];
            for cell in &col.cells {
                widths.extend(
                    cell.steps
                        .iter()
                        .map(|s| s.width)
                        .filter(|&w| w > min && w <= col.max_width && w <= budget),
                );
            }
            widths.sort_unstable();
            widths.dedup();
            let options: Vec<_> = widths
                .into_iter()
                .map(|w| {
                    (
                        w,
                        col.cells
                            .iter()
                            .map(|c| c.height_at(w).unwrap())
                            .collect::<Vec<_>>(),
                    )
                })
                .collect();
            candidates.push(options);
        }
        minimums.push(min);
        max_sum = max_sum
            .checked_add(col.max_width as u64)
            .ok_or(Error::Overflow)?;
    }
    // Minimum width required by every not-yet-assigned suffix.
    let n = table.columns.len();
    let mut suffix = vec![0u64; n + 1];
    for j in (0..n).rev() {
        suffix[j] = suffix[j + 1]
            .checked_add(minimums[j] as u64)
            .ok_or(Error::Overflow)?;
    }
    if suffix[0] > budget as u64 {
        return Err(Error::Infeasible("minimum content widths exceed container"));
    }
    if max_sum < budget as u64 {
        return Err(Error::Infeasible("column maxima cannot fill container"));
    }
    Ok(Prepared {
        budget,
        rows,
        candidates,
        suffix,
    })
}

/// Solve exactly over the supplied complete staircase profiles, then stretch
/// to exactly table.width without violating column upper bounds.
pub fn solve(table: &Table, limits: Limits) -> Result<Layout, Error> {
    solve_impl(table, limits, None)
}

fn solve_impl(
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
    if let Some(clock) = clock.as_deref_mut() {
        clock.prepared();
    }
    let mut stats = Stats {
        candidates_per_column: candidates.iter().map(Vec::len).collect(),
        peak_frontier: 1,
        ..Stats::default()
    };
    let mut frontier = vec![State {
        used: 0,
        heights: vec![0; rows],
        widths: vec![],
    }];
    for (j, options) in candidates.iter().enumerate() {
        let mut next: Vec<State> = Vec::new();
        for state in &frontier {
            for (width, heights) in options {
                if stats.generated >= limits.max_generated {
                    return Err(Error::Limit("generated states"));
                }
                stats.generated += 1;
                let used = state.used as u64 + *width as u64;
                if used + suffix[j + 1] > budget as u64 {
                    continue;
                }
                let mut widths = state.widths.clone();
                widths.push(*width);
                let candidate = State {
                    used: used as u32,
                    heights: state
                        .heights
                        .iter()
                        .zip(heights)
                        .map(|(&a, &b)| a.max(b))
                        .collect(),
                    widths,
                };
                let mut rejected = false;
                for old in &next {
                    if stats.comparisons >= limits.max_comparisons {
                        return Err(Error::Limit("dominance comparisons"));
                    }
                    stats.comparisons += 1;
                    if dominates(old, &candidate) {
                        rejected = true;
                        break;
                    }
                }
                if rejected {
                    stats.pruned += 1;
                    continue;
                }
                // Two passes ensure no earlier state is lost if candidate is rejected.
                let mut keep = Vec::with_capacity(next.len());
                for old in next {
                    if stats.comparisons >= limits.max_comparisons {
                        return Err(Error::Limit("dominance comparisons"));
                    }
                    stats.comparisons += 1;
                    if dominates(&candidate, &old) {
                        stats.pruned += 1;
                    } else {
                        keep.push(old);
                    }
                }
                if keep.len() >= limits.max_frontier {
                    return Err(Error::Limit("frontier size"));
                }
                keep.push(candidate);
                stats.peak_frontier = stats.peak_frontier.max(keep.len());
                next = keep;
            }
        }
        frontier = next;
    }
    let mut best: Option<(u64, State)> = None;
    for state in frontier {
        let height = total_height(&state.heights)?;
        if best
            .as_ref()
            .is_none_or(|(h, s)| (height, state.used) < (*h, s.used))
        {
            best = Some((height, state));
        }
    }
    let (_, best) = best.ok_or(Error::Infeasible("no layout"))?;
    finish_measured(table, budget, best.widths, stats, true, clock)
}

fn finish_measured(
    table: &Table,
    budget: u32,
    widths: Vec<u32>,
    stats: Stats,
    optimal: bool,
    mut clock: Option<&mut PhaseClock>,
) -> Result<Layout, Error> {
    if let Some(clock) = clock.as_deref_mut() {
        clock.searched();
    }
    let layout = finish(table, budget, widths, stats, optimal)?;
    if let Some(clock) = clock {
        clock.times.finalize_ns = clock.start.elapsed().as_nanos();
    }
    Ok(layout)
}

fn finish(
    table: &Table,
    budget: u32,
    mut widths: Vec<u32>,
    stats: Stats,
    optimal: bool,
) -> Result<Layout, Error> {
    let rows = table.columns[0].cells.len();
    // Distribute spare width in batches. Equal extra allocation until a column
    // hits its cap; remainder units go to earlier columns deterministically.
    let mut spare = budget - widths.iter().sum::<u32>();
    while spare > 0 {
        let active: Vec<_> = table
            .columns
            .iter()
            .enumerate()
            .filter(|(j, c)| widths[*j] < c.max_width)
            .map(|(j, _)| j)
            .collect();
        let count = active.len() as u64;
        let share = ((spare as u64 / count).max(1)) as u32;
        for j in active {
            let extra = share.min(spare).min(table.columns[j].max_width - widths[j]);
            widths[j] += extra;
            spare -= extra;
        }
    }
    let mut row_heights = vec![0; rows];
    for (col, &width) in table.columns.iter().zip(&widths) {
        for (height, cell) in row_heights.iter_mut().zip(&col.cells) {
            *height = (*height).max(cell.height_at(width).unwrap());
        }
    }
    Ok(Layout {
        optimal,
        total_height: total_height(&row_heights)?,
        row_heights,
        column_widths: widths,
        stats,
    })
}

mod algorithms;
pub use algorithms::{solve_astar, solve_html};
mod model_data;
pub use model_data::minizinc_data;
