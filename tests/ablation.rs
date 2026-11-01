use std::time::Duration;
use table_stretch::{
    AblationOptions, Column, Error, Limits, NativeAlgorithm, Profile, Step, Table,
    solve_ablation_with_timeout,
};

fn oracle(t: &Table) -> u64 {
    fn visit(t: &Table, widths: &mut Vec<u32>, remaining: u32, best: &mut u64) {
        if widths.len() == t.columns.len() {
            if remaining != 0 {
                return;
            }
            let height = (0..t.columns[0].cells.len())
                .map(|r| {
                    t.columns
                        .iter()
                        .zip(widths.iter())
                        .map(|(c, w)| {
                            c.cells[r]
                                .steps
                                .iter()
                                .rfind(|s| s.width <= *w)
                                .unwrap()
                                .height as u64
                        })
                        .max()
                        .unwrap()
                })
                .sum();
            *best = (*best).min(height);
            return;
        }
        let c = &t.columns[widths.len()];
        for w in c.min_width..=c.max_width.min(remaining) {
            widths.push(w);
            visit(t, widths, remaining - w, best);
            widths.pop();
        }
    }
    let mut best = u64::MAX;
    visit(t, &mut vec![], t.width - t.reserved_width, &mut best);
    best
}

#[test]
fn every_frozen_ablation_matches_exhaustive_widths() {
    let protocol: serde_json::Value =
        serde_json::from_str(include_str!("../docs/ablation-protocol.json")).unwrap();
    let mut seed = 0x7f382a9u64;
    let mut draw = |n| {
        seed = seed.wrapping_mul(6364136223846793005).wrapping_add(1);
        ((seed >> 32) as u32) % n
    };
    for case in 0..24 {
        let n = 1 + draw(4);
        let rows = 1 + draw(3);
        let columns: Vec<_> = (0..n)
            .map(|_| Column {
                min_width: 1,
                max_width: 3,
                cells: (0..rows)
                    .map(|_| {
                        let mut height = if case == 0 { 0 } else { 3 + draw(15) };
                        Profile {
                            steps: (1..=3)
                                .map(|width| {
                                    if width > 1 {
                                        height = height.saturating_sub(draw(6));
                                    }
                                    Step { width, height }
                                })
                                .collect(),
                        }
                    })
                    .collect(),
            })
            .collect();
        let table = Table {
            width: n + draw(2 * n + 1) + 2,
            reserved_width: 2,
            columns,
        };
        let expected = oracle(&table);
        for (method, profiles) in protocol["profiles"].as_object().unwrap() {
            let algorithm: NativeAlgorithm =
                serde_json::from_value(serde_json::json!(method)).unwrap();
            for (name, config) in profiles.as_object().unwrap() {
                let options: AblationOptions = serde_json::from_value(config.clone()).unwrap();
                let (layout, _) = solve_ablation_with_timeout(
                    &table,
                    Limits::default(),
                    algorithm,
                    options,
                    Some(Duration::from_secs(2)),
                )
                .unwrap_or_else(|e| panic!("{case} {method}/{name}: {e}; {table:?}"));
                assert!(layout.optimal);
                assert_eq!(
                    layout.total_height, expected,
                    "{case} {method}/{name}; {table:?}"
                );
                assert_eq!(layout.column_widths.iter().sum::<u32>() + 2, table.width);
                for (column, width) in table.columns.iter().zip(&layout.column_widths) {
                    assert!((column.min_width..=column.max_width).contains(width));
                    for (cell, height) in column.cells.iter().zip(&layout.row_heights) {
                        assert!(cell.height_at(*width).unwrap() <= *height);
                    }
                }
            }
        }
    }
}

#[test]
fn ablations_cannot_bypass_deadlines() {
    let table = Table {
        width: 1,
        reserved_width: 0,
        columns: vec![Column {
            min_width: 1,
            max_width: 1,
            cells: vec![Profile {
                steps: vec![Step {
                    width: 1,
                    height: 0,
                }],
            }],
        }],
    };
    for algorithm in [
        NativeAlgorithm::Pareto,
        NativeAlgorithm::Astar2011,
        NativeAlgorithm::Cp2011,
        NativeAlgorithm::Lcg2011,
        NativeAlgorithm::Lcg2015,
        NativeAlgorithm::Mip2015Unary,
        NativeAlgorithm::Mip2015Onehot,
        NativeAlgorithm::Mip2015Cellfree,
    ] {
        assert_eq!(
            solve_ablation_with_timeout(
                &table,
                Limits::default(),
                algorithm,
                AblationOptions::default(),
                Some(Duration::ZERO)
            )
            .unwrap_err(),
            Error::Limit("wall time")
        );
    }
}
