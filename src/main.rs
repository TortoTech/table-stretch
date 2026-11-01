use std::{
    env, fs,
    io::{self, Read},
    process::ExitCode,
};
use table_stretch::{Limits, NativeAlgorithm, Table, solve_measured};

fn run() -> Result<(), Box<dyn std::error::Error>> {
    let mut args: Vec<_> = env::args().skip(1).collect();
    let mut algorithm = "pareto".to_owned();
    if args.first().is_some_and(|s| s == "--algorithm") && args.len() >= 3 {
        algorithm = args[1].clone();
        args.drain(..2);
    }
    if args.len() != 1 || args[0] == "--help" || args[0] == "-h" {
        println!(
            "Usage: table-stretch [--algorithm pareto|astar2011|html|cp2011|lcg2011|lcg2015|mip2015_unary|mip2015_onehot|mip2015_cellfree] <table.json | ->\nReads JSON and writes JSON. HTML is a heuristic (optimal=false).\nUse '-' for stdin. Search limits use library defaults."
        );
        if args.len() == 1 {
            return Ok(());
        }
        return Err("expected one input path".into());
    }
    let input = if args[0] == "-" {
        let mut input = String::new();
        io::stdin().read_to_string(&mut input)?;
        input
    } else {
        fs::read_to_string(&args[0])?
    };
    let table: Table = serde_json::from_str(&input)?;
    let algorithm: NativeAlgorithm = serde_json::from_value(serde_json::Value::String(algorithm))?;
    let (layout, _) = solve_measured(&table, Limits::default(), algorithm)?;
    println!("{}", serde_json::to_string_pretty(&layout)?);
    Ok(())
}

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("{e}");
            ExitCode::FAILURE
        }
    }
}
