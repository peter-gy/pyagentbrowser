use std::{
    fs,
    path::{Path, PathBuf},
};

use crate::{generate, source::Source};

fn source(text: &str) -> Source {
    Source::new(Path::new("native/actions.rs"), text.to_owned()).feature("documents")
}

#[test]
#[should_panic(expected = "anchor count changed")]
fn missing_anchor_stops_adaptation() {
    source("fn current() {}").replace("entrypoint", "fn old() {}", "fn adapted() {}", 1, &[]);
}

#[test]
#[should_panic(expected = "anchor count changed")]
fn ambiguous_anchor_stops_adaptation() {
    source("call(); call();").replace("entrypoint", "call();", "adapted();", 1, &[]);
}

#[test]
#[should_panic(expected = "overlaps generated patch")]
fn overlapping_edits_require_an_explicit_dependency() {
    source("call();")
        .replace("scope", "call();", "scoped_call();", 1, &[])
        .replace("capture", "scoped_call", "capture", 1, &[]);
}

#[test]
fn dependent_edit_preserves_surrounding_source() {
    let result = source("before(); call(); after();")
        .replace("scope", "call();", "scoped_call();", 1, &[])
        .replace("capture", "scoped_call", "capture", 1, &["scope"]);
    assert_eq!(&*result, "before(); capture(); after();");
}

#[test]
#[should_panic(expected = "overlaps generated patch scope")]
fn partial_edit_preserves_the_provenance_of_its_surrounding_generated_text() {
    source("call();")
        .replace("scope", "call();", "start(); scoped(); end();", 1, &[])
        .replace("capture", "scoped();", "capture();", 1, &["scope"])
        .replace("finalize", "end();", "finish();", 1, &[]);
}

#[test]
#[should_panic(expected = "declared dependency scope was not used")]
fn unused_patch_dependency_stops_adaptation() {
    source("call();").replace("capture", "call();", "capture();", 1, &["scope"]);
}

#[test]
fn complete_function_replacement_preserves_following_declarations() {
    let result = source("fn assets() { embedded() }\nfn next_feature() { live() }\n").replace(
        "assets",
        "fn assets() { embedded() }",
        "fn assets() { missing() }",
        1,
        &[],
    );
    assert_eq!(
        &*result,
        "fn assets() { missing() }\nfn next_feature() { live() }\n"
    );
}

#[test]
fn pinned_source_generates_an_attributed_patch_report() {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../third_party/agent-browser");
    let output = tempfile::tempdir().unwrap();
    let report = generate(&root, output.path()).unwrap();
    assert!(output.path().join("agent_browser_upstream.rs").is_file());
    assert!(output.path().join("cdp_generated.rs").is_file());
    let scope = report
        .patches
        .iter()
        .find(|patch| patch.name == "post-policy command scope")
        .unwrap();
    assert_eq!(scope.module, Path::new("cli/src/native/actions.rs"));
    assert_eq!(scope.feature, "documents");
    assert_eq!(scope.matches, 1);
    assert!(report.inputs.contains(&root.join("cli/build.rs")));
}

#[test]
#[should_panic(expected = "failed to parse protocol")]
fn malformed_protocol_schema_stops_generation() {
    let pinned =
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../third_party/agent-browser/cli");
    let temporary = tempfile::tempdir().unwrap();
    let protocol = temporary.path().join("cdp-protocol");
    fs::create_dir(&protocol).unwrap();
    fs::copy(pinned.join("build.rs"), temporary.path().join("build.rs")).unwrap();
    fs::write(protocol.join("browser_protocol.json"), "{").unwrap();
    fs::write(protocol.join("js_protocol.json"), "{\"domains\":[]}").unwrap();
    crate::protocol::generate(&protocol, temporary.path());
}

#[test]
#[should_panic(expected = "upstream protocol generator changed")]
fn upstream_generator_changes_require_a_parity_audit() {
    let temporary = tempfile::tempdir().unwrap();
    let protocol = temporary.path().join("cdp-protocol");
    fs::create_dir(&protocol).unwrap();
    fs::write(
        temporary.path().join("build.rs"),
        "fn main() { generate_new_protocol(); }",
    )
    .unwrap();
    crate::protocol::generate(&protocol, temporary.path());
}
