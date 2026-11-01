use std::{
    io::Write,
    process::{Command, Stdio},
};

#[test]
fn selectable_research_algorithms_report_their_guarantee() {
    for (method, expected, optimal) in [("astar2011", 3, true), ("html", 7, false)] {
        let output = Command::new(env!("CARGO_BIN_EXE_table-stretch"))
            .args([
                "--algorithm",
                method,
                concat!(env!("CARGO_MANIFEST_DIR"), "/examples/table.json"),
            ])
            .output()
            .unwrap();
        assert!(output.status.success());
        let value: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
        assert_eq!(value["total_height"], expected);
        assert_eq!(value["optimal"], optimal);
    }
}

#[test]
fn solves_json_from_stdin() {
    let mut child = Command::new(env!("CARGO_BIN_EXE_table-stretch"))
        .arg("-")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .unwrap();
    child
        .stdin
        .take()
        .unwrap()
        .write_all(include_bytes!("../examples/table.json"))
        .unwrap();
    let result = child.wait_with_output().unwrap();
    assert!(result.status.success());
    let json: serde_json::Value = serde_json::from_slice(&result.stdout).unwrap();
    assert_eq!(json["total_height"], 3);
    // Equal-height layouts need not retain the previous tie-breaking choice.
    let widths = json["column_widths"].as_array().unwrap();
    assert_eq!(widths.len(), 2);
    assert_eq!(widths.iter().map(|w| w.as_u64().unwrap()).sum::<u64>(), 10);
    assert_eq!(json["optimal"], true);
}

#[test]
fn invalid_json_fails_without_a_layout() {
    let mut child = Command::new(env!("CARGO_BIN_EXE_table-stretch"))
        .arg("-")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    child
        .stdin
        .take()
        .unwrap()
        .write_all(b"{\"width\": -1}")
        .unwrap();
    let result = child.wait_with_output().unwrap();
    assert!(!result.status.success());
    assert!(result.stdout.is_empty());
    assert!(!result.stderr.is_empty());
}
