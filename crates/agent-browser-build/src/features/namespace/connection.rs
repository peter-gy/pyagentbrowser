use super::super::super::{
    patch::replace_once_named,
    source::{read_rewrite_source, Source},
};
use std::{
    fs,
    path::{Path, PathBuf},
};

pub(crate) fn rewrite_connection_module(out_dir: &Path, source: &Path) -> PathBuf {
    let destination = out_dir.join("agent_browser_connection.rs");
    let contents = read_rewrite_source(source, "connection file").feature("namespace");
    let contents = rewrite_connection_namespace(contents);
    fs::write(destination.as_path(), contents).expect("failed to write generated connection file");
    destination
}

pub(crate) fn rewrite_connection_namespace(contents: Source) -> Source {
    let rewritten = replace_once_named(
        contents,
        "connection namespace socket dir signature",
        "pub fn get_socket_dir() -> PathBuf {\n",
        r#"pub fn get_socket_dir() -> PathBuf {
    let namespace = env::var("AGENT_BROWSER_NAMESPACE").ok();
    get_socket_dir_for_namespace(namespace.as_deref())
}

pub fn get_socket_dir_for_namespace(namespace: Option<&str>) -> PathBuf {
"#,
    );
    replace_once_named(
        rewritten,
        "connection namespace socket dir selection",
        r#"    if let Ok(namespace) = env::var("AGENT_BROWSER_NAMESPACE") {
        let namespace = sanitize_session_component(&namespace);
        if !namespace.is_empty() {
            return base.join("namespaces").join(namespace).join("run");"#,
        r#"    if let Some(namespace) = namespace {
        let namespace = sanitize_session_component(namespace);
        if !namespace.is_empty() {
            return base.join("namespaces").join(namespace).join("run");"#,
    )
}
