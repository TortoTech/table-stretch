//! Persistent benchmark worker: JSON parsing/IPC is outside every timed call.
use serde::Deserialize;
use serde_json::json;
use std::{
    fs,
    io::{self, BufRead, Write},
    time::{Duration, Instant},
};
use table_stretch::{AblationOptions, Limits, NativeAlgorithm, Table, solve_ablation_with_timeout};

#[derive(Deserialize)]
struct Case {
    table: Table,
}
#[derive(Deserialize)]
struct Request {
    id: usize,
    case: usize,
    algorithm: NativeAlgorithm,
    timeout_ms: u64,
    #[serde(default)]
    options: AblationOptions,
}
fn error_status(e: &table_stretch::Error) -> &'static str {
    match e {
        table_stretch::Error::Limit("wall time") => "timeout",
        table_stretch::Error::Limit(_) => "resource_limit",
        _ => "error",
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let path = std::env::args().nth(1).ok_or("expected input manifest")?;
    let cases: Vec<Case> = serde_json::from_str(&fs::read_to_string(path)?)?;
    let stdin = io::stdin();
    let mut stdout = io::stdout().lock();
    for line in stdin.lock().lines() {
        let request: Request = serde_json::from_str(&line?)?;
        let table = &cases.get(request.case).ok_or("invalid case index")?.table;
        let limits = Limits {
            max_generated: u64::MAX,
            max_comparisons: u64::MAX,
            max_frontier: usize::MAX,
        };
        let start = Instant::now();
        let result = solve_ablation_with_timeout(
            table,
            limits,
            request.algorithm,
            request.options,
            Some(Duration::from_millis(request.timeout_ms)),
        );
        let wall_ns = start.elapsed().as_nanos();
        let output = match result {
            Ok((layout, phases)) => json!({"id":request.id,"wall_ns":wall_ns,
                "status":if layout.optimal {"optimal"} else {"heuristic"},"layout":layout,"phases":phases}),
            Err(e) => json!({"id":request.id,"wall_ns":wall_ns,
                "status":error_status(&e),
                "error":e.to_string(),"layout":null,"phases":null}),
        };
        serde_json::to_writer(&mut stdout, &output)?;
        writeln!(stdout)?;
        stdout.flush()?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn construction_limits_are_not_timeouts() {
        assert_eq!(
            error_status(&table_stretch::Error::Limit("CP model construction")),
            "resource_limit"
        );
        assert_eq!(
            error_status(&table_stretch::Error::Limit("wall time")),
            "timeout"
        );
    }
}
