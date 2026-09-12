use std::process::Command;

#[test]
fn failed_audit_returns_json_and_a_nonzero_exit() {
    let directory = tempfile::tempdir().unwrap();
    let result = Command::new(env!("CARGO_BIN_EXE_agent-browser-build"))
        .arg(directory.path().join("missing-source"))
        .arg(directory.path().join("generated"))
        .output()
        .unwrap();
    assert_eq!(result.status.code(), Some(1));
    let report: serde_json::Value = serde_json::from_slice(&result.stdout).unwrap();
    assert_eq!(report["success"], false);
    assert!(report["error"]
        .as_str()
        .unwrap()
        .contains("required upstream agent-browser file is missing"));
    assert!(report["report"]["source"]
        .as_str()
        .unwrap()
        .ends_with("missing-source"));
    assert!(result.stderr.is_empty());
}
