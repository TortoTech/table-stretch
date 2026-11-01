use serde::{Deserialize, Serialize};
use table_stretch::{Column, Limits, Profile, Table, solve};

#[derive(Deserialize)]
struct Corpus {
    tables: Vec<Sample>,
}
#[derive(Deserialize)]
struct Sample {
    book: String,
    document: String,
    table_index: usize,
    rows: Vec<Vec<Cell>>,
}
#[derive(Deserialize)]
struct Cell {
    tokens: Vec<u32>,
    gap: u32,
}

#[derive(Serialize)]
pub struct Record {
    book: String,
    document: String,
    table_index: usize,
    rows: usize,
    columns: usize,
    width: u32,
    optimal_height: u64,
    equal_extra_height: u64,
    proportional_height: u64,
    exhaustive_height: Option<u64>,
    elapsed_us: u128,
    peak_frontier: usize,
    generated: u64,
}

fn height(t: &Table, widths: &[u32]) -> u64 {
    (0..t.columns[0].cells.len())
        .map(|r| {
            t.columns
                .iter()
                .zip(widths)
                .map(|(col, &w)| {
                    col.cells[r]
                        .steps
                        .iter()
                        .rev()
                        .find(|p| p.width <= w)
                        .unwrap()
                        .height
                })
                .max()
                .unwrap() as u64
        })
        .sum()
}

fn baseline(t: &Table, proportional: bool) -> Vec<u32> {
    let mut widths: Vec<_> = t.columns.iter().map(|c| c.min_width).collect();
    let mut spare = t.width - widths.iter().sum::<u32>();
    if proportional {
        let capacity: u64 = t
            .columns
            .iter()
            .map(|c| (c.max_width - c.min_width) as u64)
            .sum();
        let available = spare;
        for (w, c) in widths.iter_mut().zip(&t.columns) {
            let add = (available as u64 * (c.max_width - c.min_width) as u64)
                .checked_div(capacity)
                .unwrap_or(0) as u32;
            *w += add;
            spare -= add;
        }
    }
    while spare > 0 {
        for (w, c) in widths.iter_mut().zip(&t.columns) {
            if *w < c.max_width && spare > 0 {
                *w += 1;
                spare -= 1;
            }
        }
    }
    widths
}

// Enumerate ALL integer allocations, independently of the solver's candidate
// construction and Pareto dominance. Used where column count and slack allow.
fn exhaustive(t: &Table) -> Option<u64> {
    let min: u32 = t.columns.iter().map(|c| c.min_width).sum();
    if t.columns.len() > 3 || t.width - min > 128 {
        return None;
    }
    fn rec(t: &Table, i: usize, left: u32, ws: &mut Vec<u32>, best: &mut u64) {
        if i == t.columns.len() {
            if left == 0 {
                *best = (*best).min(height(t, ws));
            }
            return;
        }
        let suffix: u32 = t.columns[i + 1..].iter().map(|c| c.min_width).sum();
        if left < t.columns[i].min_width + suffix {
            return;
        }
        for w in t.columns[i].min_width..=t.columns[i].max_width.min(left - suffix) {
            ws.push(w);
            rec(t, i + 1, left - w, ws, best);
            ws.pop();
        }
    }
    let mut best = u64::MAX;
    rec(t, 0, t.width, &mut Vec::new(), &mut best);
    Some(best)
}

pub fn run_corpus() -> Vec<Record> {
    let corpus: Corpus = serde_json::from_str(include_str!("../fixtures/ebooks.json")).unwrap();
    let mut records = Vec::new();
    for sample in corpus.tables {
        let mut columns = Vec::new();
        for j in 0..sample.rows[0].len() {
            let cells: Vec<_> = sample
                .rows
                .iter()
                .map(|r| Profile::from_tokens(&r[j].tokens, r[j].gap, 1).unwrap())
                .collect();
            let min_width = cells.iter().map(|c| c.steps[0].width).max().unwrap();
            let max_width = cells
                .iter()
                .map(|c| c.steps.last().unwrap().width)
                .max()
                .unwrap();
            columns.push(Column {
                min_width,
                max_width,
                cells,
            });
        }
        let min: u32 = columns.iter().map(|c| c.min_width).sum();
        let max: u32 = columns.iter().map(|c| c.max_width).sum();
        let mut budgets = vec![
            min,
            (min + 8).min(max),
            (min + 24).min(max),
            (min + 64).min(max),
            max,
        ];
        budgets.sort_unstable();
        budgets.dedup();
        let mut last_height = u64::MAX;
        for width in budgets {
            let t = Table {
                width,
                reserved_width: 0,
                columns: columns.clone(),
            };
            let started = std::time::Instant::now();
            let result = solve(&t, Limits::default()).unwrap_or_else(|e| {
                panic!("{} {} width={width}: {e}", sample.book, sample.document)
            });
            let elapsed_us = started.elapsed().as_micros();
            assert_eq!(result.column_widths.iter().sum::<u32>(), width);
            assert_eq!(height(&t, &result.column_widths), result.total_height);
            for (c, &w) in t.columns.iter().zip(&result.column_widths) {
                assert!((c.min_width..=c.max_width).contains(&w));
            }
            assert!(result.total_height <= last_height);
            last_height = result.total_height;
            let equal_extra_height = height(&t, &baseline(&t, false));
            let proportional_height = height(&t, &baseline(&t, true));
            assert!(result.total_height <= equal_extra_height);
            assert!(result.total_height <= proportional_height);
            let oracle = exhaustive(&t);
            if let Some(h) = oracle {
                assert_eq!(result.total_height, h);
            }
            records.push(Record {
                book: sample.book.clone(),
                document: sample.document.clone(),
                table_index: sample.table_index,
                rows: sample.rows.len(),
                columns: columns.len(),
                width,
                optimal_height: result.total_height,
                equal_extra_height,
                proportional_height,
                exhaustive_height: oracle,
                elapsed_us,
                peak_frontier: result.stats.peak_frontier,
                generated: result.stats.generated,
            });
        }
    }
    records
}
