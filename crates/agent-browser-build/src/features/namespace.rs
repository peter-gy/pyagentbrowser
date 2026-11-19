use super::super::{
    patch::{replace_n_named, replace_once_named},
    source::{read_rewrite_source, Source},
};
use std::{
    fs,
    path::{Path, PathBuf},
};

// Upstream resolves its socket and state directories from one process-wide
// namespace variable. Each rewrite sends that read to the adapter, which
// answers for the engine the calling thread works for. Every upstream caller
// of the two directory functions then follows the engine's namespace.

pub(crate) fn rewrite_connection_module(out_dir: &Path, source: &Path) -> PathBuf {
    let destination = out_dir.join("agent_browser_connection.rs");
    let contents = read_rewrite_source(source, "connection file").feature("namespace");
    // The socket directory and the Windows port identity.
    let contents = replace_n_named(
        contents,
        "connection namespace source",
        "    if let Ok(namespace) = env::var(\"AGENT_BROWSER_NAMESPACE\") {\n",
        "    if let Some(namespace) = crate::namespace::current() {\n",
        2,
    );
    fs::write(destination.as_path(), contents).expect("failed to write generated connection file");
    destination
}

pub(crate) fn rewrite_state_module(out_dir: &Path, source: &Path) -> PathBuf {
    let destination = out_dir.join("agent_browser_state.rs");
    let contents = read_rewrite_source(source, "state file").feature("namespace");
    let contents = replace_once_named(
        contents,
        "state namespace source",
        "    if let Ok(namespace) = std::env::var(\"AGENT_BROWSER_NAMESPACE\") {\n",
        "    if let Some(namespace) = crate::namespace::current() {\n",
    );
    fs::write(destination.as_path(), contents).expect("failed to write generated state file");
    destination
}

pub(crate) fn rewrite_session_info_namespace(contents: Source) -> Source {
    replace_once_named(
        contents,
        "session info namespace source",
        "        \"namespace\": env::var(\"AGENT_BROWSER_NAMESPACE\").ok(),\n",
        "        \"namespace\": crate::namespace::current(),\n",
    )
}
