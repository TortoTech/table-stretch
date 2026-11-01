//! Persistent benchmark worker: JSON parsing/IPC is outside every timed call.
use serde::Deserialize;
use serde_json::json;
use std::{
    fs,
    io::{self, BufRead, Write},
    time::{Duration, Instant},
};
use table_stretch::{Limits, NativeAlgorithm, Table, solve_measured_with_timeout};

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
        let result = solve_measured_with_timeout(
            table,
            limits,
            request.algorithm,
            Some(Duration::from_millis(request.timeout_ms)),
        );
        let wall_ns = start.elapsed().as_nanos();
        let output = match result {
            Ok((layout, phases)) => json!({"id":request.id,"wall_ns":wall_ns,
                "status":if layout.optimal {"optimal"} else {"heuristic"},"layout":layout,"phases":phases}),
            Err(e) => json!({"id":request.id,"wall_ns":wall_ns,
                "status":if matches!(e,table_stretch::Error::Limit(_)) {"timeout"} else {"error"},
                "error":e.to_string(),"layout":null,"phases":null}),
        };
        serde_json::to_writer(&mut stdout, &output)?;
        writeln!(stdout)?;
        stdout.flush()?;
    }
    Ok(())
}
