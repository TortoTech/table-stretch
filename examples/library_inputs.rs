//! Build identical curve inputs from the expanded numeric library corpus.
use serde_json::{Value, json};
use std::{env, fs};
use table_stretch::{Column, Profile, Table};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let path = env::args().nth(1).ok_or("expected corpus path")?;
    let corpus: Value = serde_json::from_str(&fs::read_to_string(path)?)?;
    let mut inputs = vec![];
    for (index, sample) in corpus["tables"]
        .as_array()
        .ok_or("missing tables")?
        .iter()
        .enumerate()
    {
        let rows = sample["rows"].as_array().ok_or("missing rows")?;
        let n = rows[0].as_array().ok_or("invalid row")?.len();
        let mut columns = vec![];
        for j in 0..n {
            let cells: Vec<Profile> = rows
                .iter()
                .map(|r| {
                    let tokens: Vec<u32> = serde_json::from_value(r[j]["tokens"].clone())?;
                    let gap: u32 = serde_json::from_value(r[j]["gap"].clone())?;
                    Ok(Profile::from_tokens(&tokens, gap, 1)?)
                })
                .collect::<Result<_, Box<dyn std::error::Error>>>()?;
            columns.push(Column {
                min_width: cells.iter().map(|c| c.steps[0].width).max().unwrap(),
                max_width: cells
                    .iter()
                    .map(|c| c.steps.last().unwrap().width)
                    .max()
                    .unwrap(),
                cells,
            });
        }
        let lo: u32 = columns.iter().map(|c| c.min_width).sum();
        let hi: u32 = columns.iter().map(|c| c.max_width).sum();
        let mut widths: Vec<u32> = [10, 35, 70]
            .into_iter()
            .map(|p| lo + ((hi - lo) as u64 * p / 100) as u32)
            .collect();
        widths.sort_unstable();
        widths.dedup();
        for width in widths {
            let table = Table {
                width,
                reserved_width: 0,
                columns: columns.clone(),
            };
            inputs.push(
                json!({"sample_index":index,"width":width,"book":sample["book"],
                "document":sample["document"],"table_index":sample["table_index"],
                "source_kind":sample["source_kind"],"format":sample["format"],
                "book_sha256":sample["book_sha256"],"table":table,"reference_height":null}),
            );
        }
    }
    println!("{}", serde_json::to_string(&inputs)?);
    Ok(())
}
