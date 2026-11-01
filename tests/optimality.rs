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
    let research = [
        NativeAlgorithm::Cp2011,
        NativeAlgorithm::Lcg2011,
        NativeAlgorithm::Lcg2015,
        NativeAlgorithm::Mip2015Unary,
        NativeAlgorithm::Mip2015Onehot,
        NativeAlgorithm::Mip2015Cellfree,
    ]
    .map(|algorithm| solve_measured(t, Limits::default(), algorithm).map(|(layout, _)| layout));
    for actual in [
        solve(t, Limits::default()),
        solve_astar(t, Limits::default()),
        solve_measured(t, Limits::default(), NativeAlgorithm::Pareto).map(|(layout, _)| layout),
        solve_measured(t, Limits::default(), NativeAlgorithm::Astar2011).map(|(layout, _)| layout),
    ]
    .into_iter()
    .chain(research)
    {
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
    // A nontrivial four-column tradeoff requires an intermediate frontier;
    // two-column inputs now use direct terminal completion instead.
    let t = Table {
        width: 8,
        reserved_width: 0,
        columns: (0..4)
            .map(|j| Column {
                min_width: 1,
                max_width: 3,
                cells: (0..4)
                    .map(|r| {
                        if r == j {
                            profile(&[(1, 5), (2, 4), (3, 0)])
                        } else {
                            profile(&[(1, 0)])
                        }
                    })
                    .collect(),
            })
            .collect(),
    };
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
fn terminal_completion_and_bounds_match_integer_oracle() {
    let mut table: Table = serde_json::from_str(include_str!("../examples/table.json")).unwrap();
    let layout = solve(&table, Limits::default()).unwrap();
    assert!(layout.stats.terminal_evaluations > 0);
    assert_eq!(layout.stats.comparisons, 0); // no two-column Pareto frontier
    // A capped final column forces remaining stretch into earlier columns.
    table.columns.push(Column {
        min_width: 1,
        max_width: 1,
        cells: vec![profile(&[(1, 0)]); 2],
    });
    let max: u32 = table.columns.iter().map(|c| c.max_width).sum();
    for width in 0..=max + table.reserved_width + 1 {
        table.width = width;
        check(&table);
    }
    // Zero lower/upper bound may certify optimality without any expansion.
    table.width = max + table.reserved_width;
    for col in &mut table.columns {
        col.cells = vec![profile(&[(1, 0)]); 2];
    }
    let result = solve(
        &table,
        Limits {
            max_generated: 1,
            max_comparisons: 1,
            max_frontier: 1,
        },
    )
    .unwrap();
    assert!(result.optimal);
    assert_eq!(result.total_height, 0);
    assert_eq!(result.stats.generated, 0);
}

#[test]
fn adversarial_frontiers_and_path_reconstruction_match_oracle() {
    // Independent row costs create incomparable intermediate labels. The
    // optimal allocation is deliberately different from the HTML incumbent.
    for n in 3..=6 {
        let mut table = Table {
            width: 0,
            reserved_width: 3,
            columns: (0..n)
                .map(|j| Column {
                    min_width: 1,
                    max_width: 3,
                    cells: (0..n)
                        .map(|r| {
                            if r == j {
                                profile(&[(1, 5), (2, 4), (3, 0)])
                            } else {
                                profile(&[(1, 0)])
                            }
                        })
                        .collect(),
                })
                .collect(),
        };
        for budget in n..=3 * n {
            table.width = budget as u32 + table.reserved_width;
            check(&table);
            // Permuting columns changes predecessor paths and processing order,
            // but cannot change the optimal height of the same table.
            let original = solve(&table, Limits::default()).unwrap();
            table.columns.reverse();
            let reversed = solve(&table, Limits::default()).unwrap();
            assert_eq!(original.total_height, reversed.total_height);
            table.columns.reverse();
        }
    }
}

#[test]
fn feasible_deep_random_tables_match_oracle() {
    let mut seed = 0xf45e6182u64;
    let mut draw = |n: u32| {
        seed = seed.wrapping_mul(6364136223846793005).wrapping_add(1);
        ((seed >> 32) as u32) % n
    };
    for _ in 0..160 {
        let n = 3 + draw(4);
        let rows = 1 + draw(5);
        let columns: Vec<_> = (0..n)
            .map(|_| {
                let max_width = 2 + draw(3);
                Column {
                    min_width: 1,
                    max_width,
                    cells: (0..rows)
                        .map(|_| {
                            let mut height = 2 + draw(20);
                            Profile {
                                steps: (1..=max_width + 1)
                                    .map(|width| {
                                        height = height.saturating_sub(draw(7));
                                        Step { width, height }
                                    })
                                    .collect(),
                            }
                        })
                        .collect(),
                }
            })
            .collect();
        let max: u32 = columns.iter().map(|c| c.max_width).sum();
        let budget = n + draw(max - n + 1);
        check(&Table {
            width: budget + 2,
            reserved_width: 2,
            columns,
        });
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

#[test]
fn zero_wall_budget_never_claims_optimality() {
    use table_stretch::solve_measured_with_timeout;
    let t: Table = serde_json::from_str(include_str!("../examples/table.json")).unwrap();
    for a in [
        NativeAlgorithm::Pareto,
        NativeAlgorithm::Astar2011,
        NativeAlgorithm::Html,
        NativeAlgorithm::Cp2011,
        NativeAlgorithm::Lcg2011,
        NativeAlgorithm::Lcg2015,
        NativeAlgorithm::Mip2015Unary,
        NativeAlgorithm::Mip2015Onehot,
        NativeAlgorithm::Mip2015Cellfree,
    ] {
        assert!(matches!(
            solve_measured_with_timeout(&t, Limits::default(), a, Some(std::time::Duration::ZERO)),
            Err(Error::Limit(_))
        ));
    }
}

#[test]
fn cp_large_fixed_units_do_not_consume_a_sparse_domain_budget() {
    // Fixed bounds allocate one value, regardless of its absolute magnitude.
    let t = Table {
        width: 1,
        reserved_width: 0,
        columns: vec![Column {
            min_width: 1,
            max_width: 1,
            cells: vec![profile(&[(1, 6_000_000)])],
        }],
    };
    for a in [
        NativeAlgorithm::Cp2011,
        NativeAlgorithm::Lcg2011,
        NativeAlgorithm::Lcg2015,
    ] {
        let (layout, _) = solve_measured(&t, Limits::default(), a).unwrap();
        assert_eq!(layout.total_height, 6_000_000);
        assert!(layout.optimal);
    }
}

#[test]
fn cp_sparse_gap_limit_is_checked_before_constructing_domains() {
    let t = Table {
        width: 2,
        reserved_width: 0,
        columns: vec![Column {
            min_width: 1,
            max_width: 2,
            cells: vec![profile(&[(1, 2_000_000), (2, 0)])],
        }],
    };
    for a in [
        NativeAlgorithm::Cp2011,
        NativeAlgorithm::Lcg2011,
        NativeAlgorithm::Lcg2015,
    ] {
        assert_eq!(
            solve_measured(&t, Limits::default(), a).unwrap_err(),
            Error::Limit("CP model construction")
        );
    }
}

#[test]
fn cp_gapped_configurations_and_interior_backtracking_match_oracle() {
    // Deliberately discontinuous height domains: rejecting one choice must
    // advance to a supported configuration, not lose a feasible alternative.
    for width in 3..=15 {
        let t = Table {
            width,
            reserved_width: 0,
            columns: vec![
                Column {
                    min_width: 1,
                    max_width: 5,
                    cells: vec![
                        profile(&[(1, 103), (2, 43), (3, 17), (5, 0)]),
                        profile(&[(1, 4), (4, 0)]),
                    ],
                },
                Column {
                    min_width: 1,
                    max_width: 5,
                    cells: vec![
                        profile(&[(1, 101), (3, 41), (4, 13), (5, 0)]),
                        profile(&[(1, 7), (2, 0)]),
                    ],
                },
                Column {
                    min_width: 1,
                    max_width: 5,
                    cells: vec![
                        profile(&[(1, 107), (2, 47), (4, 11), (5, 0)]),
                        profile(&[(1, 5), (3, 0)]),
                    ],
                },
            ],
        };
        check(&t);
    }
}
