use super::super::super::{patch::replace_once_named, source::Source};

pub(crate) fn rewrite_actions_namespace(contents: Source) -> Source {
    const UPSTREAM_CONNECTION_IMPORT: &str =
        r#"use crate::connection::{get_socket_dir, INTERNAL_DAEMON_SHUTDOWN_ACTION};"#;
    const REWRITTEN_CONNECTION_IMPORT: &str = r#"use crate::connection::{
    get_socket_dir,
    get_socket_dir_for_namespace,
    INTERNAL_DAEMON_SHUTDOWN_ACTION,
};"#;
    const UPSTREAM_SESSION_FIELD: &str = r#"    pub session_id: String,
    pub tracing_state: TracingState,"#;
    const REWRITTEN_SESSION_FIELD: &str = r#"    pub session_id: String,
    pub namespace: Option<String>,
    pub tracing_state: TracingState,"#;
    const UPSTREAM_SESSION_INIT: &str = r#"            session_id,
            tracing_state: TracingState::new(),"#;
    const REWRITTEN_SESSION_INIT: &str = r#"            session_id,
            namespace: env::var("AGENT_BROWSER_NAMESPACE").ok(),
            tracing_state: TracingState::new(),"#;
    const UPSTREAM_SESSION_INFO: &str = r#"async fn handle_session_info(state: &DaemonState) -> Result<Value, String> {
    Ok(json!({
        "session": state.session_id,
        "namespace": env::var("AGENT_BROWSER_NAMESPACE").ok(),
        "socketDir": get_socket_dir().to_string_lossy(),
        "backgroundPid": std::process::id(),
        "browserLaunched": state.browser.is_some(),
        "pageCount": state.browser.as_ref().map(|mgr| mgr.page_count()).unwrap_or(0),
        "engine": state.engine,
        "launchHash": state.launch_hash,
        "compatibilityStatus": "current",
        "effectiveLaunch": {
            "browserLaunched": state.browser.is_some(),
            "engine": state.engine,
            "launchHash": state.launch_hash,
        },
        "restoreKey": state.session_name,
        "restoreStatus": state.restore_status,
        "restoreStatusDetail": state.restore_status_detail,
        "restoreLoadedPath": state.restore_loaded_path,
        "restoreValidationPending": state.restore_validation_pending,
        "restoreSave": state.restore_save,
        "saveStatus": state.restore_save_status,
        "restoreSavedPath": state.restore_saved_path,
        "restoreCheckUrl": state.restore_check_url,
        "restoreCheckText": state.restore_check_text,
        "restoreCheckFn": state.restore_check_fn,
    }))
}"#;
    const REWRITTEN_SESSION_INFO: &str = r#"async fn handle_session_info(state: &DaemonState) -> Result<Value, String> {
    Ok(json!({
        "session": state.session_id,
        "namespace": state.namespace.as_deref(),
        "socketDir": get_socket_dir_for_namespace(state.namespace.as_deref()).to_string_lossy(),
        "backgroundPid": std::process::id(),
        "browserLaunched": state.browser.is_some(),
        "pageCount": state.browser.as_ref().map(|mgr| mgr.page_count()).unwrap_or(0),
        "engine": state.engine,
        "launchHash": state.launch_hash,
        "compatibilityStatus": "current",
        "effectiveLaunch": {
            "browserLaunched": state.browser.is_some(),
            "engine": state.engine,
            "launchHash": state.launch_hash,
        },
        "restoreKey": state.session_name,
        "restoreStatus": state.restore_status,
        "restoreStatusDetail": state.restore_status_detail,
        "restoreLoadedPath": state.restore_loaded_path,
        "restoreValidationPending": state.restore_validation_pending,
        "restoreSave": state.restore_save,
        "saveStatus": state.restore_save_status,
        "restoreSavedPath": state.restore_saved_path,
        "restoreCheckUrl": state.restore_check_url,
        "restoreCheckText": state.restore_check_text,
        "restoreCheckFn": state.restore_check_fn,
    }))
}"#;
    const UPSTREAM_STATE_DISPATCH: &str = r#"            state::dispatch_state_command(cmd)
                .expect("dispatch_state_command must handle all state_* actions matched here")"#;
    const REWRITTEN_STATE_DISPATCH: &str = r#"            state::dispatch_state_command_for_namespace(cmd, state.namespace.as_deref())
                .expect("dispatch_state_command must handle all state_* actions matched here")"#;
    const UPSTREAM_AUTO_STATE: &str =
        r#"    if let Some(path) = state::find_auto_state_file(&session_name) {"#;
    const REWRITTEN_AUTO_STATE: &str = r#"    if let Some(path) = state::find_auto_state_file_for_namespace(&session_name, state.namespace.as_deref()) {"#;
    const UPSTREAM_SAVE_AUTO: &str = r#"    match state::save_auto_state_transactional(
        &mgr.client,
        &active_session_id,
        &session_name,
        &state.session_id,
        mgr.visited_origins(),
    )
    .await"#;
    const REWRITTEN_SAVE_AUTO: &str = r#"    match state::save_auto_state_transactional_for_namespace(
        &mgr.client,
        &active_session_id,
        &session_name,
        &state.session_id,
        mgr.visited_origins(),
        state.namespace.as_deref(),
    )
    .await"#;
    const UPSTREAM_STATE_SAVE: &str = r#"    let saved_path = state::save_state(
        &mgr.client,
        &session_id,
        path,
        state.session_name.as_deref(),
        &state.session_id,
        mgr.visited_origins(),
    )
    .await?;"#;
    const REWRITTEN_STATE_SAVE: &str = r#"    let saved_path = state::save_state_for_namespace(
        &mgr.client,
        &session_id,
        path,
        state.session_name.as_deref(),
        &state.session_id,
        mgr.visited_origins(),
        state.namespace.as_deref(),
    )
    .await?;"#;

    let mut rewritten = replace_once_named(
        contents,
        "actions namespace connection import",
        UPSTREAM_CONNECTION_IMPORT,
        REWRITTEN_CONNECTION_IMPORT,
    );
    rewritten = replace_once_named(
        rewritten,
        "actions namespace state field",
        UPSTREAM_SESSION_FIELD,
        REWRITTEN_SESSION_FIELD,
    );
    rewritten = replace_once_named(
        rewritten,
        "actions namespace state init",
        UPSTREAM_SESSION_INIT,
        REWRITTEN_SESSION_INIT,
    );
    rewritten = replace_once_named(
        rewritten,
        "actions namespace session info",
        UPSTREAM_SESSION_INFO,
        REWRITTEN_SESSION_INFO,
    );
    rewritten = replace_once_named(
        rewritten,
        "actions namespace state dispatch",
        UPSTREAM_STATE_DISPATCH,
        REWRITTEN_STATE_DISPATCH,
    );
    rewritten = replace_once_named(
        rewritten,
        "actions namespace auto restore",
        UPSTREAM_AUTO_STATE,
        REWRITTEN_AUTO_STATE,
    );
    rewritten = replace_once_named(
        rewritten,
        "actions namespace auto save",
        UPSTREAM_SAVE_AUTO,
        REWRITTEN_SAVE_AUTO,
    );
    rewritten = replace_once_named(
        rewritten,
        "actions namespace explicit state save",
        UPSTREAM_STATE_SAVE,
        REWRITTEN_STATE_SAVE,
    );
    rewritten = replace_once_named(
        rewritten,
        "actions namespace pin preference load",
        "match tab_binding::load(&state.session_id) {",
        "match tab_binding::load_for_namespace(&state.session_id, state.namespace.as_deref()) {",
    );
    rewritten = replace_once_named(
        rewritten,
        "actions namespace pin preference save",
        "if let Err(e) = tab_binding::save(&state.session_id, &binding) {",
        "if let Err(e) = tab_binding::save_for_namespace(\n                            &state.session_id,\n                            &binding,\n                            state.namespace.as_deref(),\n                        ) {",
    );
    rewritten = replace_once_named(
        rewritten,
        "actions namespace binding save",
        "match tab_binding::save(&state.session_id, &binding) {",
        "match tab_binding::save_for_namespace(\n        &state.session_id,\n        &binding,\n        state.namespace.as_deref(),\n    ) {",
    );
    rewritten = replace_once_named(
        rewritten,
        "actions namespace binding load",
        "let binding = tab_binding::load(&session).map_err(|e| {",
        "let binding = tab_binding::load_for_namespace(&session, state.namespace.as_deref()).map_err(|e| {",
    );
    rewritten = replace_once_named(
        rewritten,
        "actions namespace binding clear",
        "tab_binding::clear(&session);",
        "tab_binding::clear_for_namespace(&session, state.namespace.as_deref());",
    );
    assert!(
        rewritten.contains("pub namespace: Option<String>"),
        "upstream DaemonState namespace layout changed"
    );
    assert!(
        rewritten.contains("dispatch_state_command_for_namespace("),
        "upstream state command dispatch changed"
    );
    rewritten
}
