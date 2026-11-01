//! Every retained library case is checked against two distinct exact searches.
use serde::Deserialize;
use table_stretch::{Limits, Table, solve, solve_astar};

#[derive(Deserialize)]
struct Case {
    table: Table,
    reference_height: u64,
    reference_verified_by: Vec<String>,
}

#[test]
fn expanded_library_matches_fixed_references() {
    let cases: Vec<Case> =
        serde_json::from_str(include_str!("../docs/benchmark-library-inputs.json")).unwrap();
    assert!(cases.len() >= 1300);
    let limits = Limits {
        max_generated: 1_000_000,
        max_comparisons: 20_000_000,
        max_frontier: 10_000,
    };
    for (index, case) in cases.iter().enumerate() {
        assert!(case.reference_verified_by.len() >= 2);
        for result in [solve(&case.table, limits), solve_astar(&case.table, limits)] {
            let layout = result.unwrap_or_else(|e| panic!("case {index}: {e}"));
            assert!(layout.optimal);
            assert_eq!(layout.total_height, case.reference_height, "case {index}");
            assert_eq!(layout.column_widths.iter().sum::<u32>(), case.table.width);
            for (col, &w) in case.table.columns.iter().zip(&layout.column_widths) {
                assert!((col.min_width..=col.max_width).contains(&w));
                for (cell, &h) in col.cells.iter().zip(&layout.row_heights) {
                    assert!(cell.height_at(w).unwrap() <= h);
                }
            }
        }
    }
}
