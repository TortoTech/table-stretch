use table_stretch::{
    Column, Error, Limits, NativeAlgorithm, Profile, Step, Table, solve, solve_astar, solve_html,
    solve_measured,
};

fn profile(points: &[(u32, u32)]) -> Profile {
    Profile {
        steps: points
            .iter()
            .map(|&(width, height)| Step { width, height })
            .collect(),
    }
}

// Independent oracle: every integer width, no breakpoints, no pruning, and a
// separate linear evaluation of the input curves. Tests exact-fill layouts.
fn brute(table: &Table) -> Option<u64> {
    fn visit(t: &Table, j: usize, remaining: u32, widths: &mut Vec<u32>, best: &mut Option<u64>) {
        if j == t.columns.len() {
            if remaining != 0 {
                return;
            }
            let mut total = 0u64;
            for r in 0..t.columns[0].cells.len() {
                let mut row = 0;
                for (c, &w) in t.columns.iter().zip(widths.iter()) {
                    let Some(step) = c.cells[r].steps.iter().rev().find(|s| s.width <= w) else {
                        return;
                    };
                    row = row.max(step.height);
                }
                total += row as u64;
            }
            if best.is_none_or(|b| total < b) {
                *best = Some(total);
            }
            return;
        }
        let c = &t.columns[j];
        for w in c.min_width..=c.max_width.min(remaining) {
            widths.push(w);
            visit(t, j + 1, remaining - w, widths, best);
            widths.pop();
        }
    }
    let budget = table.width.checked_sub(table.reserved_width)?;
    let mut best = None;
    visit(table, 0, budget, &mut Vec::new(), &mut best);
    best
}

fn check(t: &Table) {
    let expected = brute(t);
    for actual in [
        solve(t, Limits::default()),
        solve_astar(t, Limits::default()),
        solve_measured(t, Limits::default(), NativeAlgorithm::Pareto).map(|(layout, _)| layout),
        solve_measured(t, Limits::default(), NativeAlgorithm::Astar2011).map(|(layout, _)| layout),
    ] {
        match (expected, actual) {
            (None, Err(Error::Infeasible(_))) => (),
            (Some(height), Ok(actual)) => {
                assert_eq!(actual.total_height, height, "table: {t:?}");
                assert!(actual.optimal);
                assert_eq!(
                    actual.column_widths.iter().sum::<u32>() + t.reserved_width,
                    t.width
                );
                for (c, &w) in t.columns.iter().zip(&actual.column_widths) {
                    assert!((c.min_width..=c.max_width).contains(&w));
                    for (cell, &h) in c.cells.iter().zip(&actual.row_heights) {
                        assert!(cell.height_at(w).unwrap() <= h);
                    }
                }
            }
            pair => panic!("oracle mismatch {pair:?}, table {t:?}"),
        }
    }
    if let Some(expected) = expected {
        let html = solve_html(t).unwrap();
        let measured = solve_measured(t, Limits::default(), NativeAlgorithm::Html)
            .unwrap()
            .0;
        assert_eq!(html.column_widths, measured.column_widths);
        assert_eq!(html.row_heights, measured.row_heights);
        assert!(!html.optimal);
        assert!(html.total_height >= expected);
        assert_eq!(
            html.column_widths.iter().sum::<u32>() + t.reserved_width,
            t.width
        );
    } else {
        assert!(matches!(solve_html(t), Err(Error::Infeasible(_))));
    }
}

#[test]
fn randomized_exhaustive_integer_width_oracle() {
    let mut seed = 0x8a5cd789u64;
    let mut draw = |n: u32| {
        seed = seed.wrapping_mul(6364136223846793005).wrapping_add(1);
        ((seed >> 32) as u32) % n
    };
    for _ in 0..240 {
        let cols = 1 + draw(4);
        let rows = 1 + draw(4);
        let mut columns = Vec::new();
        for _ in 0..cols {
            let max_width = 2 + draw(5);
            let min_width = 1 + draw(max_width);
            let cells = (0..rows)
                .map(|_| {
                    let first = 1 + draw(max_width);
                    let mut height = draw(12);
                    let steps = (first..=max_width + 1)
                        .map(|width| {
                            height = height.saturating_sub(draw(4));
                            Step { width, height }
                        })
                        .collect();
                    Profile { steps }
                })
                .collect();
            columns.push(Column {
                min_width,
                max_width,
                cells,
            });
        }
        let max: u32 = columns.iter().map(|c| c.max_width).sum();
        let reserved_width = draw(4);
        for width in 0..=max + reserved_width + 2 {
            check(&Table {
                width,
                reserved_width,
                columns: columns.clone(),
            });
        }
    }
}

#[test]
fn row_vectors_are_necessary() {
    let t = Table {
        width: 8,
        reserved_width: 0,
        columns: vec![
            Column {
                min_width: 2,
                max_width: 4,
                cells: vec![profile(&[(2, 5), (4, 0)]), profile(&[(2, 0)])],
            },
            Column {
                min_width: 2,
                max_width: 4,
                cells: vec![profile(&[(2, 0)]), profile(&[(2, 6), (4, 0)])],
            },
            Column {
                min_width: 2,
                max_width: 2,
                cells: vec![profile(&[(2, 0)]), profile(&[(2, 10)])],
            },
        ],
    };
    check(&t);
    assert_eq!(solve(&t, Limits::default()).unwrap().total_height, 10);
}

#[test]
fn proportional_widths_can_be_suboptimal() {
    let table: Table = serde_json::from_str(include_str!("../examples/table.json")).unwrap();
    check(&table);
    assert_eq!(solve(&table, Limits::default()).unwrap().total_height, 3);
    // Equal/proportional widths [5,5] give row heights [6,1].
    assert_eq!(table.columns[0].cells[0].height_at(5), Some(6));
}

#[test]
fn limits_never_claim_optimality() {
    let t: Table = serde_json::from_str(include_str!("../examples/table.json")).unwrap();
    for limits in [
        Limits {
            max_generated: 1,
            ..Limits::default()
        },
        Limits {
            max_comparisons: 1,
            ..Limits::default()
        },
        Limits {
            max_frontier: 1,
            ..Limits::default()
        },
    ] {
        assert!(matches!(solve(&t, limits), Err(Error::Limit(_))));
    }
}

#[test]
fn rejects_malformed_inputs() {
    let base: Table = serde_json::from_str(include_str!("../examples/table.json")).unwrap();
    for steps in [
        vec![],
        vec![Step {
            width: 0,
            height: 1,
        }],
        vec![
            Step {
                width: 1,
                height: 1,
            },
            Step {
                width: 1,
                height: 0,
            },
        ],
        vec![
            Step {
                width: 1,
                height: 1,
            },
            Step {
                width: 2,
                height: 2,
            },
        ],
    ] {
        let mut t = base.clone();
        t.columns[0].cells[0].steps = steps;
        assert!(matches!(
            solve(&t, Limits::default()),
            Err(Error::Invalid(_))
        ));
    }
    let mut t = base.clone();
    t.columns[0].cells.pop();
    assert!(matches!(
        solve(&t, Limits::default()),
        Err(Error::Invalid(_))
    ));
    t = base.clone();
    t.columns.clear();
    assert!(matches!(
        solve(&t, Limits::default()),
        Err(Error::Invalid(_))
    ));
    t = base;
    t.columns[0].min_width = 0;
    assert!(matches!(
        solve(&t, Limits::default()),
        Err(Error::Invalid(_))
    ));
}

#[test]
fn large_units_caps_empty_content_and_overflow() {
    let t = Table {
        width: u32::MAX,
        reserved_width: 0,
        columns: vec![
            Column {
                min_width: 1,
                max_width: 2,
                cells: vec![profile(&[(1, u32::MAX)])],
            },
            Column {
                min_width: 1,
                max_width: u32::MAX,
                cells: vec![profile(&[(1, 0)])],
            },
        ],
    };
    let s = solve(&t, Limits::default()).unwrap();
    assert_eq!(s.column_widths, vec![2, u32::MAX - 2]);
    assert_eq!(s.total_height, u32::MAX as u64);
    assert_eq!(
        Profile::from_tokens(&[u32::MAX, 1], 1, 1).unwrap_err(),
        Error::Overflow
    );
    assert_eq!(
        Profile::from_tokens(&[], 1, 1).unwrap().height_at(1),
        Some(0)
    );
    assert!(Profile::from_tokens(&[0], 1, 1).is_err());
    assert!(Profile::from_tokens(&[1], 1, 0).is_err());
}

// Independent partition DP, considering every possible last line.
fn partition_lines(tokens: &[u32], gap: u32, width: u32) -> Option<u32> {
    let n = tokens.len();
    let mut dp = vec![u32::MAX / 2; n + 1];
    dp[0] = 0;
    for end in 1..=n {
        for start in 0..end {
            let used = tokens[start..end].iter().sum::<u32>() + gap * (end - start - 1) as u32;
            if used <= width {
                dp[end] = dp[end].min(dp[start] + 1);
            }
        }
    }
    (dp[n] < u32::MAX / 2).then_some(dp[n])
}

#[test]
fn token_breakpoints_match_all_line_partitions() {
    for n in 1..=6u32 {
        for mut code in 0..3u32.pow(n) {
            let tokens: Vec<_> = (0..n)
                .map(|_| {
                    let t = 1 + code % 3;
                    code /= 3;
                    t
                })
                .collect();
            for gap in [0, 1, 3] {
                let p = Profile::from_tokens(&tokens, gap, 2).unwrap();
                for width in 1..=tokens.iter().sum::<u32>() + gap * (n - 1) + 2 {
                    assert_eq!(
                        p.height_at(width),
                        partition_lines(&tokens, gap, width).map(|n| 2 * n)
                    );
                }
            }
        }
    }
}
