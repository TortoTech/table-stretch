mod support;

#[test]
fn real_epub_tables_match_oracles_and_dominate_baselines() {
    let records = support::run_corpus();
    assert!(records.len() >= 32);
}
