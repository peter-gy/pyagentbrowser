use super::super::{
    patch::replace_once_named,
    source::{path_literal, read_rewrite_source, require_file},
};
use std::{
    fs,
    path::{Path, PathBuf},
};

pub(crate) fn rewrite_browser_module(out_dir: &Path, source: &Path) -> PathBuf {
    let destination = out_dir.join("agent_browser_browser.rs");
    let contents = read_rewrite_source(source, "browser file").feature("embedding");
    assert!(
        contents.contains("\"targetId\": p.target_id"),
        "upstream tab_list target id contract changed"
    );
    fs::write(destination.as_path(), contents).expect("failed to write generated browser file");
    destination
}

/// Submodule and the declaration line that names it.
const SESSION_SETTINGS_SUBMODULES: &[(&str, &str)] = &[
    ("patch", "mod patch;\n"),
    ("plan", "mod plan;\n"),
    ("proxy", "mod proxy;\n"),
    ("running", "mod running;\n"),
    ("seed", "mod seed;\n"),
    ("spec", "mod spec;\n"),
    ("store", "mod store;\n"),
    ("tests", "pub(crate) mod tests;\n"),
];

/// Exports `StoreError` so the adapter can implement the settings `Store`
/// that keeps an embedded session's security settings in memory.
pub(crate) fn rewrite_session_settings_module(out_dir: &Path, source: &Path) -> PathBuf {
    let root = source.parent().expect("session settings module directory");
    let mut contents = read_rewrite_source(source, "session settings module").feature("embedding");
    // The adapted module file lives in OUT_DIR, so each submodule names its
    // pinned source file.
    for (name, declaration) in SESSION_SETTINGS_SUBMODULES {
        let path = root.join(format!("{name}.rs"));
        require_file(&path);
        contents = replace_once_named(
            contents,
            &format!("session settings {name} source"),
            declaration,
            &format!("#[path = \"{}\"]\n{declaration}", path_literal(&path)),
        );
    }
    let contents = replace_once_named(
        contents,
        "session settings store error export",
        "#[cfg(test)]\npub use store::{MemStore, StoreError};",
        "pub use store::StoreError;\n#[cfg(test)]\npub use store::MemStore;",
    );
    let destination = out_dir.join("agent_browser_session_settings.rs");
    fs::write(destination.as_path(), contents)
        .expect("failed to write generated session settings file");
    destination
}

/// Chrome 157 renamed the feature that exposes `document.modelContext` from
/// `WebMCPTesting` to `WebMCP`. Chrome ignores a feature name it does not know,
/// so the launch enables both.
pub(crate) fn rewrite_chrome_module(out_dir: &Path, source: &Path) -> PathBuf {
    let contents = read_rewrite_source(source, "Chrome launch file").feature("webmcp");
    let contents = replace_once_named(
        contents,
        "WebMCP feature name",
        "        enable_features.push(\"WebMCPTesting\".to_string());\n",
        "        enable_features.push(\"WebMCPTesting\".to_string());\n        enable_features.push(\"WebMCP\".to_string());\n",
    );
    let destination = out_dir.join("agent_browser_cdp_chrome.rs");
    fs::write(destination.as_path(), contents).expect("failed to write generated Chrome file");
    destination
}
