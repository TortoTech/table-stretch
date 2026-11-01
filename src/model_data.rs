use super::*;
use serde_json::{Value, json};

/// Export the same validated staircase model to the MiniZinc research models.
/// External engines have their own integer ranges; the comparison harness uses
/// the small integral units of the EPUB corpus, not arbitrary u32 inputs.
pub fn minizinc_data(table: &Table) -> Result<Value, Error> {
    let Prepared {
        budget,
        rows,
        suffix,
        ..
    } = prepare(table, false)?;
    let mut first = Vec::new();
    let mut last = Vec::new();
    let mut cell_row = Vec::new();
    let mut cell_col = Vec::new();
    let mut sw = Vec::new();
    let mut sh = Vec::new();
    let mut row_upper = vec![0u32; rows];
    for (j, col) in table.columns.iter().enumerate() {
        for (i, profile) in col.cells.iter().enumerate() {
            first.push(sw.len() + 1);
            for step in &profile.steps {
                sw.push(step.width);
                sh.push(step.height);
            }
            last.push(sw.len());
            cell_row.push(i + 1);
            cell_col.push(j + 1);
            row_upper[i] = row_upper[i].max(profile.steps[0].height);
        }
    }
    Ok(json!({"n":table.columns.len(), "m":rows, "budget":budget,
        "cells":first.len(), "steps":sw.len(), "first":first, "last":last,
        "cell_row":cell_row, "cell_col":cell_col, "sw":sw, "sh":sh,
        "lo":suffix.windows(2).map(|s| s[0]-s[1]).collect::<Vec<_>>(),
        "hi":table.columns.iter().map(|c| c.max_width).collect::<Vec<_>>(),
        "row_upper":row_upper}))
}
