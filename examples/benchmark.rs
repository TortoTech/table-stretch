//! One isolated worker per real table. Emits flushed JSONL after each case.
use serde::Deserialize;
use serde_json::{Value, json};
use std::{
    env, fs,
    hint::black_box,
    io::{self, Write},
    time::Instant,
};
use table_stretch::{
    Column, Limits, Profile, Table, minizinc_data, solve, solve_astar, solve_html,
};

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

fn prepare(sample: &Sample) -> Table {
    let columns = (0..sample.rows[0].len())
        .map(|j| {
            let cells: Vec<_> = sample
                .rows
                .iter()
                .map(|r| Profile::from_tokens(&r[j].tokens, r[j].gap, 1).unwrap())
                .collect();
            Column {
                min_width: cells.iter().map(|c| c.steps[0].width).max().unwrap(),
                max_width: cells
                    .iter()
                    .map(|c| c.steps.last().unwrap().width)
                    .max()
                    .unwrap(),
                cells,
            }
        })
        .collect();
    Table {
        width: 0,
        reserved_width: 0,
        columns,
    }
}

fn budgets(t: &Table) -> Vec<u32> {
    let min: u32 = t.columns.iter().map(|c| c.min_width).sum();
    let max: u32 = t.columns.iter().map(|c| c.max_width).sum();
    let mut values = vec![
        min,
        (min + 8).min(max),
        (min + 24).min(max),
        (min + 64).min(max),
        max,
    ];
    for percent in [10, 25, 50, 75] {
        values.push(min + ((max - min) as u64 * percent / 100) as u32);
    }
    values.sort_unstable();
    values.dedup();
    values
}

// Independent evaluation from raw token widths; does not consult profiles.
fn evaluate(sample: &Sample, widths: &[u32]) -> Vec<u32> {
    sample
        .rows
        .iter()
        .map(|row| {
            row.iter()
                .zip(widths)
                .map(|(cell, &width)| {
                    let mut lines = u32::from(!cell.tokens.is_empty());
                    let mut used = 0u64;
                    for &token in &cell.tokens {
                        assert!(token <= width);
                        let next = if used == 0 {
                            token as u64
                        } else {
                            used + cell.gap as u64 + token as u64
                        };
                        if next > width as u64 {
                            lines += 1;
                            used = token as u64;
                        } else {
                            used = next;
                        }
                    }
                    lines
                })
                .max()
                .unwrap()
        })
        .collect()
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
            if spare > 0 && *w < c.max_width {
                *w += 1;
                spare -= 1;
            }
        }
    }
    widths
}

fn summary(times: &[u128]) -> Value {
    let mut sorted = times.to_vec();
    sorted.sort_unstable();
    json!({"samples_ns": times, "min_ns": sorted[0], "median_ns": sorted[sorted.len()/2], "max_ns": sorted[sorted.len()-1]})
}

fn emit(v: Value) {
    let mut out = io::stdout().lock();
    serde_json::to_writer(&mut out, &v).unwrap();
    writeln!(out).unwrap();
    out.flush().unwrap();
}

fn main() {
    let args: Vec<_> = env::args().skip(1).collect();
    assert!(args.len() == 3 || args.len() == 4);
    let corpus: Corpus = serde_json::from_str(&fs::read_to_string(&args[0]).unwrap()).unwrap();
    let index: usize = args[1].parse().unwrap();
    let repeats: usize = args[2].parse().unwrap();
    assert!(repeats > 0);
    let sample = &corpus.tables[index];
    let mut table = prepare(sample); // untimed profile warm-up
    let mut preparation = Vec::new();
    for _ in 0..repeats {
        let started = Instant::now();
        let prepared = black_box(prepare(black_box(sample)));
        preparation.push(started.elapsed().as_nanos());
        table = prepared; // drop previous table outside timing
    }
    let widths = budgets(&table);
    let profiles: usize = table
        .columns
        .iter()
        .flat_map(|c| &c.cells)
        .map(|c| c.steps.len())
        .sum();
    let candidates: Vec<_> = table
        .columns
        .iter()
        .map(|c| {
            let mut ws = vec![c.min_width];
            ws.extend(
                c.cells
                    .iter()
                    .flat_map(|p| &p.steps)
                    .map(|s| s.width)
                    .filter(|&w| w >= c.min_width && w <= c.max_width),
            );
            ws.sort_unstable();
            ws.dedup();
            ws.len()
        })
        .collect();
    emit(
        json!({"kind":"table", "sample_index": index, "book":sample.book,
        "document":sample.document, "table_index": sample.table_index,
        "rows":sample.rows.len(), "columns":table.columns.len(), "widths":widths,
        "profile_steps":profiles, "candidates_per_column":candidates,
        "profile_build":summary(&preparation), "model_data":minizinc_data(&Table { width: table.columns.iter().map(|c| c.max_width).sum(), ..table.clone() }).unwrap()}),
    );
    let algorithms = if args.get(3).is_some_and(|s| s == "all") {
        vec!["pareto", "astar2011", "html"]
    } else {
        vec!["pareto"]
    };
    let mut last_success = std::collections::HashMap::new();
    for width in widths {
        table.width = width;
        let mut reference = None;
        for &algorithm in &algorithms {
            // 'start' ensures a killed worker has an identifiable pending case.
            emit(
                json!({"kind":"start", "sample_index":index, "width":width, "algorithm":algorithm}),
            );
            let warm = dispatch(algorithm, black_box(&table));
            let mut times = Vec::new();
            let mut result = None;
            for _ in 0..repeats {
                let started = Instant::now();
                let current = black_box(dispatch(algorithm, black_box(&table)));
                times.push(started.elapsed().as_nanos());
                assert_eq!(
                    current.as_ref().map(|s| s.total_height),
                    warm.as_ref().map(|s| s.total_height)
                );
                result = Some(current);
            }
            let equal: u64 = evaluate(sample, &baseline(&table, false))
                .iter()
                .map(|&h| h as u64)
                .sum();
            let proportional: u64 = evaluate(sample, &baseline(&table, true))
                .iter()
                .map(|&h| h as u64)
                .sum();
            let mut record = json!({"kind":"case", "sample_index":index, "width":width, "algorithm":algorithm,
            "solve":summary(&times), "equal_height":equal, "proportional_height":proportional});
            match result.unwrap() {
                Ok(layout) => {
                    assert_eq!(layout.column_widths.iter().sum::<u32>(), width);
                    for (c, &w) in table.columns.iter().zip(&layout.column_widths) {
                        assert!((c.min_width..=c.max_width).contains(&w));
                    }
                    assert_eq!(evaluate(sample, &layout.column_widths), layout.row_heights);
                    assert_eq!(
                        layout.row_heights.iter().map(|&h| h as u64).sum::<u64>(),
                        layout.total_height
                    );
                    if layout.optimal {
                        assert!(
                            layout.total_height <= equal && layout.total_height <= proportional
                        );
                        if let Some(&last) = last_success.get(algorithm) {
                            assert!(layout.total_height <= last);
                        }
                        last_success.insert(algorithm, layout.total_height);
                        if let Some(h) = reference {
                            assert_eq!(layout.total_height, h);
                        }
                        reference = Some(layout.total_height);
                    }
                    record["status"] = json!(if layout.optimal {
                        "optimal"
                    } else {
                        "heuristic"
                    });
                    record["height"] = json!(layout.total_height);
                    record["stats"] = serde_json::to_value(&layout.stats).unwrap();
                }
                Err(e) => {
                    record["status"] = json!(match e {
                        table_stretch::Error::Limit(_) => "search_limit",
                        _ => "error",
                    });
                    record["error"] = json!(e.to_string());
                }
            }
            emit(record);
        }
    }
}

fn dispatch(algorithm: &str, table: &Table) -> Result<table_stretch::Layout, table_stretch::Error> {
    match algorithm {
        "pareto" => solve(table, Limits::default()),
        "astar2011" => solve_astar(table, Limits::default()),
        "html" => solve_html(table),
        _ => unreachable!(),
    }
}
