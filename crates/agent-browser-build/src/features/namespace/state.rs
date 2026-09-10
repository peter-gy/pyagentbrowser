use super::super::super::{
    patch::{replace_n_named, replace_once_named},
    source::{read_rewrite_source, Source},
};
use std::{
    fs,
    path::{Path, PathBuf},
};

pub(crate) fn rewrite_state_module(out_dir: &Path, source: &Path) -> PathBuf {
    let destination = out_dir.join("agent_browser_state.rs");
    let contents = read_rewrite_source(source, "state file").feature("namespace");
    let contents = rewrite_state_namespace(contents);
    fs::write(destination.as_path(), contents).expect("failed to write generated state file");
    destination
}

pub(crate) fn rewrite_state_namespace(contents: Source) -> Source {
    const UPSTREAM_SAVE_STATE_SIG: &str = r#"pub async fn save_state(
    client: &CdpClient,
    session_id: &str,
    path: Option<&str>,
    session_name: Option<&str>,
    session_id_str: &str,
    visited_origins: &HashSet<String>,
) -> Result<String, String> {"#;
    const REWRITTEN_SAVE_STATE_SIG: &str = r#"pub async fn save_state(
    client: &CdpClient,
    session_id: &str,
    path: Option<&str>,
    session_name: Option<&str>,
    session_id_str: &str,
    visited_origins: &HashSet<String>,
) -> Result<String, String> {
    save_state_for_namespace(
        client,
        session_id,
        path,
        session_name,
        session_id_str,
        visited_origins,
        None,
    )
    .await
}

pub async fn save_state_for_namespace(
    client: &CdpClient,
    session_id: &str,
    path: Option<&str>,
    session_name: Option<&str>,
    session_id_str: &str,
    visited_origins: &HashSet<String>,
    namespace: Option<&str>,
) -> Result<String, String> {"#;
    const UPSTREAM_SAVE_AUTO_SIG: &str = r#"pub async fn save_auto_state_transactional(
    client: &CdpClient,
    session_id: &str,
    session_name: &str,
    session_id_str: &str,
    visited_origins: &HashSet<String>,
) -> Result<String, String> {"#;
    const REWRITTEN_SAVE_AUTO_SIG: &str = r#"pub async fn save_auto_state_transactional(
    client: &CdpClient,
    session_id: &str,
    session_name: &str,
    session_id_str: &str,
    visited_origins: &HashSet<String>,
) -> Result<String, String> {
    save_auto_state_transactional_for_namespace(
        client,
        session_id,
        session_name,
        session_id_str,
        visited_origins,
        None,
    )
    .await
}

pub async fn save_auto_state_transactional_for_namespace(
    client: &CdpClient,
    session_id: &str,
    session_name: &str,
    session_id_str: &str,
    visited_origins: &HashSet<String>,
    namespace: Option<&str>,
) -> Result<String, String> {"#;
    const UPSTREAM_STATE_LIST_SIG: &str = r#"pub fn state_list() -> Result<Value, String> {"#;
    const REWRITTEN_STATE_LIST_SIG: &str = r#"pub fn state_list() -> Result<Value, String> {
    state_list_for_namespace(None)
}

pub fn state_list_for_namespace(namespace: Option<&str>) -> Result<Value, String> {"#;
    const UPSTREAM_STATE_CLEAR_SIG: &str =
        r#"pub fn state_clear(path: Option<&str>) -> Result<Value, String> {"#;
    const REWRITTEN_STATE_CLEAR_SIG: &str = r#"pub fn state_clear(path: Option<&str>) -> Result<Value, String> {
    state_clear_for_namespace(path, None)
}

pub fn state_clear_for_namespace(
    path: Option<&str>,
    namespace: Option<&str>,
) -> Result<Value, String> {"#;
    const UPSTREAM_STATE_CLEAN_SIG: &str =
        r#"pub fn state_clean(max_age_days: u64) -> Result<Value, String> {"#;
    const REWRITTEN_STATE_CLEAN_SIG: &str = r#"pub fn state_clean(max_age_days: u64) -> Result<Value, String> {
    state_clean_for_namespace(max_age_days, None)
}

pub fn state_clean_for_namespace(
    max_age_days: u64,
    namespace: Option<&str>,
) -> Result<Value, String> {"#;
    const UPSTREAM_FIND_AUTO_SIG: &str =
        r#"pub fn find_auto_state_file(session_name: &str) -> Option<String> {"#;
    const REWRITTEN_FIND_AUTO_SIG: &str = r#"pub fn find_auto_state_file(session_name: &str) -> Option<String> {
    find_auto_state_file_for_namespace(session_name, None)
}

pub fn find_auto_state_file_for_namespace(
    session_name: &str,
    namespace: Option<&str>,
) -> Option<String> {"#;
    const UPSTREAM_DISPATCH_SIG: &str =
        r#"pub fn dispatch_state_command(cmd: &Value) -> Option<Result<Value, String>> {"#;
    const REWRITTEN_DISPATCH_SIG: &str = r#"pub fn dispatch_state_command(cmd: &Value) -> Option<Result<Value, String>> {
    dispatch_state_command_for_namespace(cmd, None)
}

pub fn dispatch_state_command_for_namespace(
    cmd: &Value,
    namespace: Option<&str>,
) -> Option<Result<Value, String>> {"#;
    const UPSTREAM_STATE_DIR: &str = r#"pub fn get_state_dir() -> PathBuf {
    let base = if let Some(home) = dirs::home_dir() {
        home.join(".agent-browser")
    } else {
        std::env::temp_dir().join("agent-browser")
    };

    if let Ok(namespace) = std::env::var("AGENT_BROWSER_NAMESPACE") {
        let namespace = sanitize_session_component(&namespace);
        if !namespace.is_empty() {
            return base.join("namespaces").join(namespace).join("state");
        }
    }

    base
}

pub fn get_sessions_dir() -> PathBuf {
    get_state_dir().join("sessions")
}"#;
    const REWRITTEN_STATE_DIR: &str = r#"pub fn get_state_dir() -> PathBuf {
    let namespace = std::env::var("AGENT_BROWSER_NAMESPACE").ok();
    get_state_dir_for_namespace(namespace.as_deref())
}

pub fn get_state_dir_for_namespace(namespace: Option<&str>) -> PathBuf {
    let base = if let Some(home) = dirs::home_dir() {
        home.join(".agent-browser")
    } else {
        std::env::temp_dir().join("agent-browser")
    };

    if let Some(namespace) = namespace {
        let namespace = sanitize_session_component(namespace);
        if !namespace.is_empty() {
            return base.join("namespaces").join(namespace).join("state");
        }
    }

    base
}

pub fn get_sessions_dir() -> PathBuf {
    let namespace = std::env::var("AGENT_BROWSER_NAMESPACE").ok();
    get_sessions_dir_for_namespace(namespace.as_deref())
}

pub fn get_sessions_dir_for_namespace(namespace: Option<&str>) -> PathBuf {
    get_state_dir_for_namespace(namespace).join("sessions")
}"#;

    let mut rewritten = replace_once_named(
        contents,
        "state save namespace signature",
        UPSTREAM_SAVE_STATE_SIG,
        REWRITTEN_SAVE_STATE_SIG,
    );
    rewritten = replace_once_named(
        rewritten,
        "state auto-save namespace signature",
        UPSTREAM_SAVE_AUTO_SIG,
        REWRITTEN_SAVE_AUTO_SIG,
    );
    rewritten = replace_once_named(
        rewritten,
        "state list namespace signature",
        UPSTREAM_STATE_LIST_SIG,
        REWRITTEN_STATE_LIST_SIG,
    );
    rewritten = replace_once_named(
        rewritten,
        "state clear namespace signature",
        UPSTREAM_STATE_CLEAR_SIG,
        REWRITTEN_STATE_CLEAR_SIG,
    );
    rewritten = replace_once_named(
        rewritten,
        "state clean namespace signature",
        UPSTREAM_STATE_CLEAN_SIG,
        REWRITTEN_STATE_CLEAN_SIG,
    );
    rewritten = replace_once_named(
        rewritten,
        "state auto-restore namespace signature",
        UPSTREAM_FIND_AUTO_SIG,
        REWRITTEN_FIND_AUTO_SIG,
    );
    rewritten = replace_once_named(
        rewritten,
        "state dispatch namespace signature",
        UPSTREAM_DISPATCH_SIG,
        REWRITTEN_DISPATCH_SIG,
    );
    rewritten = replace_n_named(
        rewritten,
        "state namespace sessions dir",
        "\n    let dir = get_sessions_dir();",
        "\n    let dir = get_sessions_dir_for_namespace(namespace);",
        5,
    );
    rewritten = replace_once_named(
        rewritten,
        "state namespace implicit save sessions dir",
        "\n            let dir = get_sessions_dir();",
        "\n            let dir = get_sessions_dir_for_namespace(namespace);",
    );
    rewritten = replace_once_named(
        rewritten,
        "state transactional save namespace call",
        r#"    let candidate_path = save_state(
        client,
        session_id,
        Some(&candidate_arg),
        Some(session_name),
        session_id_str,
        visited_origins,
    )
    .await?;"#,
        r#"    let candidate_path = save_state_for_namespace(
        client,
        session_id,
        Some(&candidate_arg),
        Some(session_name),
        session_id_str,
        visited_origins,
        namespace,
    )
    .await?;"#,
    );
    rewritten = replace_once_named(
        rewritten,
        "state list dispatch namespace",
        r#""state_list" => Some(state_list()),"#,
        r#""state_list" => Some(state_list_for_namespace(namespace)),"#,
    );
    rewritten = replace_once_named(
        rewritten,
        "state clear dispatch namespace",
        r#"            Some(state_clear(path))"#,
        r#"            Some(state_clear_for_namespace(path, namespace))"#,
    );
    rewritten = replace_once_named(
        rewritten,
        "state clean dispatch namespace",
        r#"            Some(state_clean(days))"#,
        r#"            Some(state_clean_for_namespace(days, namespace))"#,
    );
    rewritten = replace_once_named(
        rewritten,
        "state directory namespace helpers",
        UPSTREAM_STATE_DIR,
        REWRITTEN_STATE_DIR,
    );
    assert!(
        rewritten.contains("pub fn get_state_dir_for_namespace("),
        "upstream state directory helper changed"
    );
    assert!(
        rewritten.contains("pub async fn save_auto_state_transactional_for_namespace("),
        "upstream transactional state save changed"
    );
    rewritten
}
