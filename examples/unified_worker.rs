//! One fresh process per run, with the same input/validation/fallback protocol
//! for native algorithms and MiniZinc. The parent owns the wall-clock deadline.
use serde::Deserialize;
use serde_json::{Value, json};
use std::error::Error;
use std::fs::{self, File};
use std::io::{BufRead, BufReader, Write};
use std::path::Path;
use std::process::{Command, Stdio};
use std::time::Instant;
use table_stretch::{
    Layout, Limits, NativeAlgorithm, Stats, Table, minizinc_data, solve_html, solve_measured,
};

fn emit(value: Value) -> Result<(), Box<dyn Error>> {
    let mut out = std::io::stdout().lock();
    serde_json::to_writer(&mut out, &value)?;
    writeln!(out)?;
    out.flush()?;
    Ok(())
}

#[derive(Deserialize)]
struct Solution {
    widths: Vec<u32>,
    heights: Vec<u32>,
    height: u64,
}

fn row_heights(table: &Table, widths: &[u32]) -> Result<Vec<u32>, Box<dyn Error>> {
    let mut rows = vec![0; table.columns[0].cells.len()];
    for (c, &w) in table.columns.iter().zip(widths) {
        for (r, cell) in rows.iter_mut().zip(&c.cells) {
            *r = (*r).max(cell.height_at(w).ok_or("cell does not fit")?);
        }
    }
    Ok(rows)
}

// Validate the solver's actual assignment before stretching. Then return the
// exact heights after full-width stretching, just like native Layout results.
fn normalize(table: &Table, s: &Solution, optimal: bool) -> Result<Layout, Box<dyn Error>> {
    let budget = (table.width - table.reserved_width) as u64;
    if s.widths.len() != table.columns.len()
        || s.heights.len() != table.columns[0].cells.len()
        || s.widths.iter().map(|&w| w as u64).sum::<u64>() > budget
        || table
            .columns
            .iter()
            .zip(&s.widths)
            .any(|(c, &w)| w < c.min_width || w > c.max_width)
        || s.heights.iter().map(|&h| h as u64).sum::<u64>() != s.height
    {
        return Err("invalid solver dimensions, bounds or objective".into());
    }
    let actual = row_heights(table, &s.widths)?;
    if actual.iter().zip(&s.heights).any(|(a, h)| a > h)
        || (optimal && actual.iter().map(|&h| h as u64).sum::<u64>() != s.height)
    {
        return Err("solver heights disagree with input profiles".into());
    }
    let mut widths = s.widths.clone();
    let mut spare = budget - widths.iter().map(|&w| w as u64).sum::<u64>();
    while spare > 0 {
        let active: Vec<_> = table
            .columns
            .iter()
            .enumerate()
            .filter(|(j, c)| widths[*j] < c.max_width)
            .map(|(j, _)| j)
            .collect();
        if active.is_empty() {
            return Err("cannot fill container".into());
        }
        let share = (spare / active.len() as u64).max(1);
        for j in active {
            let add = spare
                .min(share)
                .min((table.columns[j].max_width - widths[j]) as u64);
            widths[j] += add as u32;
            spare -= add;
        }
    }
    let rows = row_heights(table, &widths)?;
    let height = rows.iter().map(|&h| h as u64).sum();
    if optimal && height != s.height {
        return Err("stretch improved a claimed optimum".into());
    }
    Ok(Layout {
        optimal,
        column_widths: widths,
        row_heights: rows,
        total_height: height,
        stats: Stats::default(),
    })
}

fn run() -> Result<(), Box<dyn Error>> {
    let args: Vec<_> = std::env::args().collect();
    if args.len() != 6 {
        return Err("usage: unified_worker METHOD INPUT MINIZINC MODELS_DIR SCRATCH_DIR".into());
    }
    let started = Instant::now();
    let table: Table = serde_json::from_slice(&fs::read(&args[2])?)?;
    let read_ns = started.elapsed().as_nanos();
    let fallback_start = Instant::now();
    // A common feasible fallback also validates every input profile. It is
    // deliberately charged to every method, including the HTML baseline.
    let fallback = solve_html(&table)?;
    let fallback_ns = fallback_start.elapsed().as_nanos();
    emit(json!({"kind":"incumbent", "source":"common_fallback", "layout":fallback}))?;
    let native = match args[1].as_str() {
        "pareto" => Some(NativeAlgorithm::Pareto),
        "astar2011" => Some(NativeAlgorithm::Astar2011),
        "html" => Some(NativeAlgorithm::Html),
        _ => None,
    };
    if let Some(algorithm) = native {
        // Only the benchmark disables count limits. The same parent watchdog
        // controls all methods; library and CLI defaults are unchanged.
        let limits = Limits {
            max_generated: u64::MAX,
            max_comparisons: u64::MAX,
            max_frontier: usize::MAX,
        };
        let (layout, phases) = solve_measured(&table, limits, algorithm)?;
        emit(
            json!({"kind":"result", "status":if layout.optimal {"optimal"} else {"heuristic"},
            "layout":layout, "phases":{"read_ns":read_ns,"fallback_ns":fallback_ns,"native":phases}}),
        )?;
        return Ok(());
    }
    let (solver, model, flags): (_, _, &[&str]) = match args[1].as_str() {
        "cp2011_gecode" => ("gecode", "cp2011.mzn", &[]),
        "lcg2011_chuffed" => ("chuffed", "cp2011.mzn", &["-f", "--vsids"]),
        "lcg2015_cellfree" => ("chuffed", "lcg2015.mzn", &["-f", "--vsids"]),
        "mip2015_unary" => ("highs", "mip2015.mzn", &[]),
        "mip2015_onehot" => ("highs", "mip2015_onehot.mzn", &[]),
        _ => return Err("unknown method".into()),
    };
    let prep = Instant::now();
    let input_path = Path::new(&args[5]).join("data.json");
    fs::write(&input_path, serde_json::to_vec(&minizinc_data(&table)?)?)?;
    let export_ns = prep.elapsed().as_nanos();
    let external_start = Instant::now();
    let err_path = Path::new(&args[5]).join("stderr.txt");
    let mut child = Command::new(&args[3])
        .args([
            "-O0",
            "--solver",
            solver,
            "--statistics",
            "--json-stream",
            "--intermediate-solutions",
            "-p",
            "1",
            "-r",
            "1",
        ])
        .args(flags)
        .arg(Path::new(&args[4]).join(model))
        .arg(&input_path)
        .stdout(Stdio::piped())
        .stderr(File::create(&err_path)?)
        .spawn()?;
    let mut solution = None;
    let mut status = String::new();
    let mut stats = serde_json::Map::new();
    let mut best_height = fallback.total_height;
    let mut normalize_ns = 0;
    for line in BufReader::new(child.stdout.take().unwrap()).lines() {
        let value: Value = serde_json::from_str(&line?)?;
        match value["type"].as_str() {
            Some("solution") => {
                let s: Solution = serde_json::from_str(
                    value["output"]["default"]
                        .as_str()
                        .ok_or("missing solution output")?,
                )?;
                let begin = Instant::now();
                let layout = normalize(&table, &s, false)?;
                normalize_ns += begin.elapsed().as_nanos();
                if layout.total_height < best_height {
                    best_height = layout.total_height;
                    emit(json!({"kind":"incumbent", "source":"solver", "layout":layout}))?;
                }
                solution = Some(s);
            }
            Some("status") => status = value["status"].as_str().unwrap_or("").into(),
            Some("statistics") => {
                if let Some(values) = value["statistics"].as_object() {
                    stats.extend(values.clone());
                }
            }
            Some("error") => return Err(format!("MiniZinc error: {value}").into()),
            _ => (),
        }
    }
    if !child.wait()?.success() {
        return Err(fs::read_to_string(err_path)?.into());
    }
    let external_process_ns = external_start.elapsed().as_nanos();
    if status != "OPTIMAL_SOLUTION" {
        return Err(format!("unexpected completed solver status: {status}").into());
    }
    let finalize = Instant::now();
    let layout = normalize(&table, &solution.ok_or("no solver solution")?, true)?;
    let finalize_ns = finalize.elapsed().as_nanos();
    emit(json!({"kind":"result","status":"optimal","layout":layout,
        "phases":{"read_ns":read_ns,"fallback_ns":fallback_ns,"export_ns":export_ns,
        "external_process_ns":external_process_ns,"incumbent_normalize_ns":normalize_ns,
        "finalize_ns":finalize_ns,"engine_statistics":stats},
        "stderr":fs::read_to_string(err_path)?}))?;
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        let _ = emit(json!({"kind":"error","message":error.to_string()}));
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn normalize_checks_before_stretching() {
        let t: Table = serde_json::from_str(include_str!("table.json")).unwrap();
        let s = Solution {
            widths: vec![7, 3],
            heights: vec![2, 1],
            height: 3,
        };
        assert_eq!(normalize(&t, &s, true).unwrap().total_height, 3);
        let bad = Solution {
            widths: vec![5, 5],
            heights: vec![2, 1],
            height: 3,
        };
        assert!(normalize(&t, &bad, false).is_err());
        let loose = Solution {
            widths: vec![7, 3],
            heights: vec![8, 1],
            height: 9,
        };
        assert!(normalize(&t, &loose, true).is_err());
        assert_eq!(normalize(&t, &loose, false).unwrap().total_height, 3);
    }
}
