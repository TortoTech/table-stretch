//! Public MiniZinc configurations at their original container widths.
use serde::Deserialize;
use std::time::Duration;
use table_stretch::{Limits, NativeAlgorithm, Table, solve_measured_with_timeout};

#[derive(Deserialize)]
struct Case {
    source_file: String,
    table: Table,
    reference_height: u64,
}

#[test]
fn public_minizinc_instances_match_fixed_optima() {
    let cases: Vec<Case> =
        serde_json::from_str(include_str!("../docs/benchmark-minizinc-inputs.json")).unwrap();
    assert_eq!(cases.len(), 26);
    for case in cases {
        for algorithm in [NativeAlgorithm::Pareto, NativeAlgorithm::Astar2011] {
            let (layout, _) = solve_measured_with_timeout(
                &case.table,
                Limits::default(),
                algorithm,
                Some(Duration::from_secs(5)),
            )
            .unwrap_or_else(|e| panic!("{}: {e}", case.source_file));
            assert!(layout.optimal);
            assert_eq!(
                layout.total_height, case.reference_height,
                "{}",
                case.source_file
            );
            assert_eq!(layout.column_widths.iter().sum::<u32>(), case.table.width);
            for (row, &height) in layout.row_heights.iter().enumerate() {
                let actual = case
                    .table
                    .columns
                    .iter()
                    .zip(&layout.column_widths)
                    .map(|(col, &width)| col.cells[row].height_at(width).unwrap())
                    .max()
                    .unwrap();
                assert_eq!(height, actual);
            }
        }
    }
}
