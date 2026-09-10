use super::super::super::{patch::replace_once_named, source::read_rewrite_source};
use std::{
    fs,
    path::{Path, PathBuf},
};

pub(crate) fn rewrite_tab_binding_module(out_dir: &Path, source: &Path) -> PathBuf {
    let destination = out_dir.join("agent_browser_tab_binding.rs");
    let contents = read_rewrite_source(source, "tab binding file").feature("namespace");
    let contents = replace_once_named(
        contents,
        "tab binding namespace path",
        r#"pub fn binding_path(session: &str) -> PathBuf {
    crate::connection::get_socket_dir().join(format!("{}.target", session))
}"#,
        r#"pub fn binding_path(session: &str) -> PathBuf {
    binding_path_for_namespace(session, None)
}

pub fn binding_path_for_namespace(session: &str, namespace: Option<&str>) -> PathBuf {
    crate::connection::get_socket_dir_for_namespace(namespace)
        .join(format!("{}.target", session))
}"#,
    );
    let contents = replace_once_named(
        contents,
        "tab binding namespace load",
        r#"pub fn load(session: &str) -> Result<Option<TabBinding>, String> {
    let path = binding_path(session);"#,
        r#"pub fn load(session: &str) -> Result<Option<TabBinding>, String> {
    load_for_namespace(session, None)
}

pub fn load_for_namespace(
    session: &str,
    namespace: Option<&str>,
) -> Result<Option<TabBinding>, String> {
    let path = binding_path_for_namespace(session, namespace);"#,
    );
    let contents = replace_once_named(
        contents,
        "tab binding namespace save",
        r#"pub fn save(session: &str, binding: &TabBinding) -> Result<(), String> {
    let path = binding_path(session);"#,
        r#"pub fn save(session: &str, binding: &TabBinding) -> Result<(), String> {
    save_for_namespace(session, binding, None)
}

pub fn save_for_namespace(
    session: &str,
    binding: &TabBinding,
    namespace: Option<&str>,
) -> Result<(), String> {
    let path = binding_path_for_namespace(session, namespace);"#,
    );
    let contents = replace_once_named(
        contents,
        "tab binding namespace clear",
        r#"pub fn clear(session: &str) {
    let _ = fs::remove_file(binding_path(session));
}"#,
        r#"pub fn clear(session: &str) {
    clear_for_namespace(session, None);
}

pub fn clear_for_namespace(session: &str, namespace: Option<&str>) {
    let _ = fs::remove_file(binding_path_for_namespace(session, namespace));
}"#,
    );
    fs::write(destination.as_path(), contents).expect("failed to write generated tab binding file");
    destination
}
