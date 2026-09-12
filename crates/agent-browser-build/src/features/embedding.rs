use super::super::source::read_rewrite_source;
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
