use std::{
    collections::HashSet,
    env,
    fmt::{Arguments, Write as _},
    fs,
    path::{Path, PathBuf},
};

const ROOT_MODULES: &[(&str, &str)] = &[
    ("color", "color.rs"),
    ("commands", "commands.rs"),
    ("connection", "connection.rs"),
    ("flags", "flags.rs"),
    ("install", "install.rs"),
    ("plugins", "plugins.rs"),
    ("read", "read.rs"),
    ("validation", "validation.rs"),
];

const NATIVE_MODULES: &[(&str, &str)] = &[
    ("actions", "actions.rs"),
    ("auth", "auth.rs"),
    ("browser", "browser.rs"),
    ("cdp", "cdp/mod.rs"),
    ("cookies", "cookies.rs"),
    ("diff", "diff.rs"),
    ("element", "element.rs"),
    ("inspect_server", "inspect_server.rs"),
    ("interaction", "interaction.rs"),
    ("network", "network.rs"),
    ("policy", "policy.rs"),
    ("providers", "providers.rs"),
    ("react", "react/mod.rs"),
    ("recording", "recording.rs"),
    ("screenshot", "screenshot.rs"),
    ("snapshot", "snapshot.rs"),
    ("state", "state.rs"),
    ("storage", "storage.rs"),
    ("stream", "stream/mod.rs"),
    ("tracing", "tracing.rs"),
    ("webdriver", "webdriver/mod.rs"),
];

fn manifest_dir() -> PathBuf {
    PathBuf::from(env::var("CARGO_MANIFEST_DIR").expect("CARGO_MANIFEST_DIR must be set"))
}

fn main() {
    let out_dir = PathBuf::from(env::var("OUT_DIR").expect("OUT_DIR must be set"));
    write_upstream_modules(&out_dir);

    let protocol_dir = upstream_protocol_dir();
    let out_path = out_dir.join("cdp_generated.rs");

    let browser_path = protocol_dir.join("browser_protocol.json");
    let js_path = protocol_dir.join("js_protocol.json");

    require_file(&browser_path);
    require_file(&js_path);

    let mut all_domains: Vec<Domain> = Vec::new();

    for path in [&browser_path, &js_path] {
        if !path.exists() {
            continue;
        }
        println!("cargo:rerun-if-changed={}", path.display());
        let content = fs::read_to_string(path).unwrap();
        let protocol: ProtocolSpec = match serde_json::from_str(&content) {
            Ok(p) => p,
            Err(e) => {
                eprintln!("cargo:warning=Failed to parse {}: {}", path.display(), e);
                continue;
            }
        };
        all_domains.extend(protocol.domains);
    }

    // Collect all known type IDs per domain for cross-domain resolution
    let mut domain_types: std::collections::HashMap<String, HashSet<String>> =
        std::collections::HashMap::new();
    for domain in &all_domains {
        let mut types = HashSet::new();
        for td in &domain.types {
            types.insert(td.id.clone());
        }
        domain_types.insert(domain.name.clone(), types);
    }

    // Known recursive struct fields that need Box wrapping
    let recursive_fields: HashSet<(&str, &str, &str)> = [
        ("DOM", "Node", "contentDocument"),
        ("DOM", "Node", "templateContent"),
        ("DOM", "Node", "importedDocument"),
        ("Accessibility", "AXNode", "sources"),
        ("Runtime", "StackTrace", "parent"),
    ]
    .into_iter()
    .collect();

    let mut output = String::new();
    output.push_str("use serde::{Deserialize, Serialize};\n\n");

    for domain in &all_domains {
        generate_domain(domain, &domain_types, &recursive_fields, &mut output);
    }

    fs::write(&out_path, &output).unwrap();
}

fn write_upstream_modules(out_dir: &Path) {
    let native_module = write_native_module(out_dir);
    let upstream_root = upstream_cli_src_dir();
    let root_module = out_dir.join("agent_browser_upstream.rs");
    let mut output = String::new();

    for (name, relative_path) in ROOT_MODULES {
        let path = upstream_root.join(relative_path);
        require_file(&path);
        let module_path = match *name {
            "connection" => rewrite_connection_module(out_dir, &path),
            _ => path,
        };
        line(
            &mut output,
            format_args!(
                "#[allow(dead_code, clippy::new_without_default, clippy::should_implement_trait)]"
            ),
        );
        line(
            &mut output,
            format_args!("#[path = \"{}\"]", path_literal(&module_path)),
        );
        line(&mut output, format_args!("pub(crate) mod {name};"));
    }

    let test_utils = upstream_root.join("test_utils.rs");
    require_file(&test_utils);
    line(&mut output, format_args!("#[cfg(test)]"));
    line(
        &mut output,
        format_args!(
            "#[allow(dead_code, clippy::new_without_default, clippy::should_implement_trait)]"
        ),
    );
    line(
        &mut output,
        format_args!("#[path = \"{}\"]", path_literal(&test_utils)),
    );
    line(&mut output, format_args!("pub(crate) mod test_utils;"));

    line(
        &mut output,
        format_args!(
            "#[allow(dead_code, clippy::new_without_default, clippy::should_implement_trait)]"
        ),
    );
    line(
        &mut output,
        format_args!("#[path = \"{}\"]", path_literal(&native_module)),
    );
    line(&mut output, format_args!("pub mod native;"));
    line(
        &mut output,
        format_args!("pub const VERSION: &str = env!(\"CARGO_PKG_VERSION\");"),
    );

    fs::write(&root_module, output).expect("failed to write generated upstream module");
}

fn write_native_module(out_dir: &Path) -> PathBuf {
    let upstream_native = upstream_native_dir();
    let native_module = out_dir.join("agent_browser_native.rs");
    let mut output = String::new();

    for (name, relative_path) in NATIVE_MODULES {
        let path = upstream_native.join(relative_path);
        require_file(&path);
        let module_path = match *name {
            "actions" => rewrite_actions_module(out_dir, &path),
            "browser" => rewrite_browser_module(out_dir, &path),
            "state" => rewrite_state_module(out_dir, &path),
            "stream" => rewrite_stream_module(out_dir, &path),
            _ => path,
        };
        line(
            &mut output,
            format_args!(
                "#[allow(dead_code, clippy::new_without_default, clippy::should_implement_trait)]"
            ),
        );
        if *name == "snapshot" {
            line(
                &mut output,
                format_args!("#[allow(unknown_lints, clippy::useless_borrows_in_formatting)]"),
            );
        }
        line(
            &mut output,
            format_args!("#[path = \"{}\"]", path_literal(&module_path)),
        );
        line(&mut output, format_args!("pub mod {name};"));
    }

    fs::write(&native_module, output).expect("failed to write generated native module");
    native_module
}

fn read_rewrite_source(source: &Path, module: &str) -> String {
    fs::read_to_string(source)
        .unwrap_or_else(|err| panic!("failed to read upstream {module}: {err}"))
        .replace("\r\n", "\n")
}

fn rewrite_browser_module(out_dir: &Path, source: &Path) -> PathBuf {
    let destination = out_dir.join("agent_browser_browser.rs");
    let contents = read_rewrite_source(source, "browser file");
    let contents = rewrite_tab_list_target_id(contents);
    fs::write(destination.as_path(), contents).expect("failed to write generated browser file");
    destination
}

fn rewrite_connection_module(out_dir: &Path, source: &Path) -> PathBuf {
    let destination = out_dir.join("agent_browser_connection.rs");
    let contents = read_rewrite_source(source, "connection file");
    let contents = rewrite_connection_namespace(contents);
    fs::write(destination.as_path(), contents).expect("failed to write generated connection file");
    destination
}

fn rewrite_connection_namespace(contents: String) -> String {
    const UPSTREAM_SOCKET_DIR: &str = r#"pub fn get_socket_dir() -> PathBuf {
    // 1. Explicit override (ignore empty string)
    let base = if let Ok(dir) = env::var("AGENT_BROWSER_SOCKET_DIR") {
        if !dir.is_empty() {
            PathBuf::from(dir)
        } else if let Ok(runtime_dir) = env::var("XDG_RUNTIME_DIR") {
            if !runtime_dir.is_empty() {
                PathBuf::from(runtime_dir).join("agent-browser")
            } else if let Some(home) = dirs::home_dir() {
                home.join(".agent-browser")
            } else {
                env::temp_dir().join("agent-browser")
            }
        } else if let Some(home) = dirs::home_dir() {
            home.join(".agent-browser")
        } else {
            env::temp_dir().join("agent-browser")
        }
    } else if let Ok(runtime_dir) = env::var("XDG_RUNTIME_DIR") {
        if !runtime_dir.is_empty() {
            PathBuf::from(runtime_dir).join("agent-browser")
        } else if let Some(home) = dirs::home_dir() {
            home.join(".agent-browser")
        } else {
            env::temp_dir().join("agent-browser")
        }
    } else if let Some(home) = dirs::home_dir() {
        home.join(".agent-browser")
    } else {
        env::temp_dir().join("agent-browser")
    };

    if let Ok(namespace) = env::var("AGENT_BROWSER_NAMESPACE") {
        let namespace = sanitize_session_component(&namespace);
        if !namespace.is_empty() {
            return base.join("namespaces").join(namespace).join("run");
        }
    }

    base
}"#;
    const REWRITTEN_SOCKET_DIR: &str = r#"pub fn get_socket_dir() -> PathBuf {
    let namespace = env::var("AGENT_BROWSER_NAMESPACE").ok();
    get_socket_dir_for_namespace(namespace.as_deref())
}

pub fn get_socket_dir_for_namespace(namespace: Option<&str>) -> PathBuf {
    // 1. Explicit override (ignore empty string)
    let base = if let Ok(dir) = env::var("AGENT_BROWSER_SOCKET_DIR") {
        if !dir.is_empty() {
            PathBuf::from(dir)
        } else if let Ok(runtime_dir) = env::var("XDG_RUNTIME_DIR") {
            if !runtime_dir.is_empty() {
                PathBuf::from(runtime_dir).join("agent-browser")
            } else if let Some(home) = dirs::home_dir() {
                home.join(".agent-browser")
            } else {
                env::temp_dir().join("agent-browser")
            }
        } else if let Some(home) = dirs::home_dir() {
            home.join(".agent-browser")
        } else {
            env::temp_dir().join("agent-browser")
        }
    } else if let Ok(runtime_dir) = env::var("XDG_RUNTIME_DIR") {
        if !runtime_dir.is_empty() {
            PathBuf::from(runtime_dir).join("agent-browser")
        } else if let Some(home) = dirs::home_dir() {
            home.join(".agent-browser")
        } else {
            env::temp_dir().join("agent-browser")
        }
    } else if let Some(home) = dirs::home_dir() {
        home.join(".agent-browser")
    } else {
        env::temp_dir().join("agent-browser")
    };

    if let Some(namespace) = namespace {
        let namespace = sanitize_session_component(namespace);
        if !namespace.is_empty() {
            return base.join("namespaces").join(namespace).join("run");
        }
    }

    base
}"#;

    let rewritten = replace_once_named(
        contents,
        "connection namespace socket dir",
        UPSTREAM_SOCKET_DIR,
        REWRITTEN_SOCKET_DIR,
    );
    assert!(
        rewritten.contains("pub fn get_socket_dir_for_namespace("),
        "upstream socket directory helper changed"
    );
    rewritten
}

fn rewrite_tab_list_target_id(contents: String) -> String {
    const UPSTREAM_TAB_LIST_FIELDS: &str = r#"                    "tabId": format_tab_id(p.tab_id),
                    "label": p.label,
                    "title": p.title,"#;
    const REWRITTEN_TAB_LIST_FIELDS: &str = r#"                    "tabId": format_tab_id(p.tab_id),
                    "targetId": p.target_id,
                    "label": p.label,
                    "title": p.title,"#;

    let rewritten = replace_once_named(
        contents,
        "tab_list target id",
        UPSTREAM_TAB_LIST_FIELDS,
        REWRITTEN_TAB_LIST_FIELDS,
    );
    assert!(
        rewritten.contains("\"targetId\": p.target_id"),
        "upstream tab_list target id patch changed"
    );
    rewritten
}

fn rewrite_actions_module(out_dir: &Path, source: &Path) -> PathBuf {
    let destination = out_dir.join("agent_browser_actions.rs");
    let contents = read_rewrite_source(source, "actions file");
    let contents = rewrite_confirmation_handling(contents);
    let contents = rewrite_actions_namespace(contents);
    let contents = rewrite_dashboard_streaming(contents);
    let contents = rewrite_stream_result_success(contents);
    fs::write(destination.as_path(), contents).expect("failed to write generated actions file");
    destination
}

fn rewrite_confirmation_handling(contents: String) -> String {
    const UPSTREAM_PENDING_CONFIRMATION: &str = r#"pub struct PendingConfirmation {
    pub action: String,
    pub cmd: Value,
    approved_actions: Vec<String>,
}"#;
    const REWRITTEN_PENDING_CONFIRMATION: &str = r#"pub struct PendingConfirmation {
    pub id: String,
    pub action: String,
    pub cmd: Value,
    approved_actions: Vec<String>,
}"#;
    const UPSTREAM_POLICY_CONFIRM_RESPONSE: &str = r#"state.pending_confirmation = Some(PendingConfirmation {
                action: policy_action.clone(),
                cmd: cmd.clone(),
                approved_actions: state.confirmed_policy_actions.iter().cloned().collect(),
            });
            return json!({
                "id": id,
                "success": true,
                "data": {
                    "confirmation_required": true,
                    "confirmation_id": id,
                    "action": policy_action
                },
            });"#;
    const REWRITTEN_POLICY_CONFIRM_RESPONSE: &str = r#"state.pending_confirmation = Some(PendingConfirmation {
                id: id.clone(),
                action: policy_action.clone(),
                cmd: cmd.clone(),
                approved_actions: state.confirmed_policy_actions.iter().cloned().collect(),
            });
            return json!({
                "id": id,
                "success": true,
                "data": {
                    "confirmation_required": true,
                    "confirmation_id": id,
                    "action": policy_action
                },
            });"#;
    const UPSTREAM_CONFIRM_ACTIONS_RESPONSE: &str = r#"state.pending_confirmation = Some(PendingConfirmation {
                        action: policy_action.to_string(),
                        cmd: cmd.clone(),
                        approved_actions: state.confirmed_policy_actions.iter().cloned().collect(),
                    });
                    return json!({
                        "id": id,
                        "success": true,
                        "data": {
                            "confirmation_required": true,
                            "confirmation_id": id,
                            "action": policy_action,
                        },
                    });"#;
    const REWRITTEN_CONFIRM_ACTIONS_RESPONSE: &str = r#"state.pending_confirmation = Some(PendingConfirmation {
                        id: id.clone(),
                        action: policy_action.to_string(),
                        cmd: cmd.clone(),
                        approved_actions: state.confirmed_policy_actions.iter().cloned().collect(),
                    });
                    return json!({
                        "id": id,
                        "success": true,
                        "data": {
                            "confirmation_required": true,
                            "confirmation_id": id,
                            "action": policy_action,
                        },
                    });"#;
    const UPSTREAM_CONFIRM_HANDLERS: &str = r#"async fn handle_confirm(_cmd: &Value, state: &mut DaemonState) -> Result<Value, String> {
    let pending = state
        .pending_confirmation
        .take()
        .ok_or("No pending confirmation")?;

    let mut approved_actions = pending.approved_actions.clone();
    if !approved_actions.iter().any(|a| a == &pending.action) {
        approved_actions.push(pending.action.clone());
    }
    let previous_confirmed = std::mem::replace(
        &mut state.confirmed_policy_actions,
        approved_actions.into_iter().collect(),
    );
    let result = Box::pin(execute_command(&pending.cmd, state)).await;
    state.confirmed_policy_actions = previous_confirmed;

    Ok(json!({ "confirmed": true, "action": pending.action, "result": result }))
}

async fn handle_deny(_cmd: &Value, state: &mut DaemonState) -> Result<Value, String> {
    let pending = state
        .pending_confirmation
        .take()
        .ok_or("No pending confirmation")?;

    Ok(json!({ "denied": true, "action": pending.action }))
}"#;
    const REWRITTEN_CONFIRM_HANDLERS: &str = r#"fn confirmation_id_from_command(cmd: &Value) -> Result<&str, String> {
    cmd.get("confirmation_id")
        .or_else(|| cmd.get("confirmationId"))
        .and_then(|v| v.as_str())
        .ok_or_else(|| "Missing confirmation_id".to_string())
}

fn validate_pending_confirmation_id(cmd: &Value, pending: &PendingConfirmation) -> Result<(), String> {
    let requested_id = confirmation_id_from_command(cmd)?;
    if requested_id != pending.id {
        return Err(format!(
            "confirmation_id does not match pending confirmation: expected '{}', got '{}'",
            pending.id, requested_id
        ));
    }
    Ok(())
}

fn validate_confirmation_url(
    pending: &PendingConfirmation,
    filter: &DomainFilter,
    url: &str,
) -> Result<(), String> {
    filter.check_url(url).map_err(|reason| {
        format!(
            "Action '{}' denied by allowed domains during confirmation: {}",
            pending.action, reason
        )
    })
}

fn validate_confirmation_cookie_domain(
    pending: &PendingConfirmation,
    filter: &DomainFilter,
    domain: &str,
) -> Result<(), String> {
    let hostname = domain.trim_start_matches('.');
    if hostname.is_empty() {
        return Err(format!(
            "Action '{}' denied by allowed domains during confirmation: empty cookie domain",
            pending.action
        ));
    }
    if filter.is_allowed(hostname) {
        return Ok(());
    }
    Err(format!(
        "Action '{}' denied by allowed domains during confirmation: Cookie domain '{}' is not in the allowed domains list",
        pending.action, domain
    ))
}

fn validate_confirmation_cookie(
    pending: &PendingConfirmation,
    filter: &DomainFilter,
    cookie: &Value,
) -> Result<bool, String> {
    if let Some(url) = cookie.get("url").and_then(|v| v.as_str()) {
        validate_confirmation_url(pending, filter, url)?;
        return Ok(true);
    }
    if let Some(domain) = cookie.get("domain").and_then(|v| v.as_str()) {
        validate_confirmation_cookie_domain(pending, filter, domain)?;
        return Ok(true);
    }
    Ok(false)
}

fn action_requires_validated_confirmation_target(action: &str) -> bool {
    matches!(
        action,
        "cookies_set" | "state_load" | "state_save" | "tab_switch" | "tab_close"
    )
}

fn validate_confirmation_allowed_domains(
    pending: &PendingConfirmation,
    filter: &DomainFilter,
) -> Result<(), String> {
    if filter.allowed_domains.is_empty() {
        return Ok(());
    }

    if let Some(url) = pending.cmd.get("url").and_then(|v| v.as_str()) {
        validate_confirmation_url(pending, filter, url)?;
        return Ok(());
    }

    if pending.action == "cookies_set" {
        let mut validated_any = false;
        if let Some(cookies) = pending.cmd.get("cookies").and_then(|v| v.as_array()) {
            for cookie in cookies {
                validated_any |= validate_confirmation_cookie(pending, filter, cookie)?;
            }
        } else {
            validated_any = validate_confirmation_cookie(pending, filter, &pending.cmd)?;
        }
        if validated_any {
            return Ok(());
        }
    }

    if action_requires_validated_confirmation_target(&pending.action) {
        return Err(format!(
            "Action '{}' denied by allowed domains during confirmation: target cannot be validated against allowed domains",
            pending.action
        ));
    }

    Ok(())
}

async fn ensure_confirmation_still_allowed(
    pending: &PendingConfirmation,
    state: &mut DaemonState,
) -> Result<(), String> {
    if let Some(ref mut policy) = state.policy {
        policy.reload().map_err(|reason| {
            format!(
                "Action '{}' denied by policy during confirmation: {}",
                pending.action, reason
            )
        })?;
        if let PolicyResult::Deny(reason) = policy.check(&pending.action) {
            return Err(format!(
                "Action '{}' denied by policy during confirmation: {}",
                pending.action, reason
            ));
        }
    }
    let filter = state.domain_filter.read().await;
    if let Some(ref filter) = *filter {
        validate_confirmation_allowed_domains(pending, filter)?;
    }
    Ok(())
}

async fn handle_confirm(cmd: &Value, state: &mut DaemonState) -> Result<Value, String> {
    let pending_for_validation = {
        let pending_ref = state
            .pending_confirmation
            .as_ref()
            .ok_or("No pending confirmation")?;
        validate_pending_confirmation_id(cmd, pending_ref)?;
        PendingConfirmation {
            id: pending_ref.id.clone(),
            action: pending_ref.action.clone(),
            cmd: pending_ref.cmd.clone(),
            approved_actions: pending_ref.approved_actions.clone(),
        }
    };
    ensure_confirmation_still_allowed(&pending_for_validation, state).await?;
    let pending = state
        .pending_confirmation
        .take()
        .expect("pending confirmation was just validated");

    let mut approved_actions = pending.approved_actions.clone();
    if !approved_actions.iter().any(|a| a == &pending.action) {
        approved_actions.push(pending.action.clone());
    }
    let previous_confirmed = std::mem::replace(
        &mut state.confirmed_policy_actions,
        approved_actions.into_iter().collect(),
    );
    let result = Box::pin(execute_command(&pending.cmd, state)).await;
    state.confirmed_policy_actions = previous_confirmed;

    Ok(json!({ "confirmed": true, "action": pending.action, "result": result }))
}

async fn handle_deny(cmd: &Value, state: &mut DaemonState) -> Result<Value, String> {
    let pending_ref = state
        .pending_confirmation
        .as_ref()
        .ok_or("No pending confirmation")?;
    validate_pending_confirmation_id(cmd, pending_ref)?;
    let pending = state
        .pending_confirmation
        .take()
        .expect("pending confirmation was just validated");

    Ok(json!({ "denied": true, "action": pending.action }))
}"#;

    let mut rewritten = replace_once_named(
        contents,
        "PendingConfirmation",
        UPSTREAM_PENDING_CONFIRMATION,
        REWRITTEN_PENDING_CONFIRMATION,
    );
    rewritten = replace_once_named(
        rewritten,
        "policy confirmation response",
        UPSTREAM_POLICY_CONFIRM_RESPONSE,
        REWRITTEN_POLICY_CONFIRM_RESPONSE,
    );
    rewritten = replace_once_named(
        rewritten,
        "confirm_actions confirmation response",
        UPSTREAM_CONFIRM_ACTIONS_RESPONSE,
        REWRITTEN_CONFIRM_ACTIONS_RESPONSE,
    );
    rewritten = replace_once_named(
        rewritten,
        "confirm/deny handlers",
        UPSTREAM_CONFIRM_HANDLERS,
        REWRITTEN_CONFIRM_HANDLERS,
    );
    assert!(
        rewritten.contains("pub id: String"),
        "upstream PendingConfirmation shape changed"
    );
    assert!(
        rewritten.contains("fn validate_pending_confirmation_id("),
        "upstream confirm handlers changed"
    );
    assert!(
        rewritten.contains("fn validate_confirmation_allowed_domains("),
        "upstream confirmation allowlist guard changed"
    );
    rewritten
}

fn rewrite_actions_namespace(contents: String) -> String {
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
    const UPSTREAM_SESSION_INIT: &str = r#"            session_id: env::var("AGENT_BROWSER_SESSION").unwrap_or_else(|_| "default".to_string()),"#;
    const REWRITTEN_SESSION_INIT: &str = r#"            session_id: env::var("AGENT_BROWSER_SESSION").unwrap_or_else(|_| "default".to_string()),
            namespace: env::var("AGENT_BROWSER_NAMESPACE").ok(),"#;
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

fn rewrite_dashboard_streaming(contents: String) -> String {
    assert!(
        contents.contains("use super::stream::{self, StreamServer};"),
        "upstream dashboard stream import moved"
    );
    assert!(
        contents.contains("pub fn new_with_stream("),
        "upstream DaemonState stream constructor moved"
    );
    assert!(
        contents.contains("server.broadcast_command(action, &id, cmd_for_broadcast);"),
        "upstream command stream broadcast moved"
    );
    assert!(
        contents.contains("\"stream_enable\" => handle_stream_enable(cmd, state).await,")
            && contents.contains("\"stream_disable\" => handle_stream_disable(state).await,")
            && contents.contains("\"stream_status\" => handle_stream_status(state).await,"),
        "upstream stream command dispatch moved"
    );
    contents
}

fn rewrite_stream_result_success(contents: String) -> String {
    const UPSTREAM_SUCCESS_CHECK: &str = r#"        let success = resp
            .get("status")
            .and_then(|v| v.as_str())
            .is_some_and(|s| s == "success");"#;
    const REWRITTEN_SUCCESS_CHECK: &str = r#"        let success = resp
            .get("success")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);"#;

    let rewritten = replace_once_named(
        contents,
        "stream result success field",
        UPSTREAM_SUCCESS_CHECK,
        REWRITTEN_SUCCESS_CHECK,
    );
    assert!(
        rewritten.contains(".get(\"success\")"),
        "upstream stream result success handling changed"
    );
    rewritten
}

fn rewrite_state_module(out_dir: &Path, source: &Path) -> PathBuf {
    let destination = out_dir.join("agent_browser_state.rs");
    let contents = read_rewrite_source(source, "state file");
    let contents = rewrite_state_namespace(contents);
    fs::write(destination.as_path(), contents).expect("failed to write generated state file");
    destination
}

fn rewrite_state_namespace(contents: String) -> String {
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

fn rewrite_stream_module(out_dir: &Path, source: &Path) -> PathBuf {
    let destination = out_dir.join("agent_browser_stream.rs");
    let stream_dir = source.parent().expect("stream module must have a parent");
    let http_path = rewrite_stream_http_module(out_dir, &stream_dir.join("http.rs"));
    let mut contents = read_rewrite_source(source, "stream module");

    contents = replace_once_named(
        contents,
        "stream cdp_loop module",
        "mod cdp_loop;\n",
        &format!(
            "#[path = \"{}\"]\nmod cdp_loop;\n",
            path_literal(&stream_dir.join("cdp_loop.rs"))
        ),
    );
    contents = replace_once_named(
        contents,
        "stream chat module",
        "pub(crate) mod chat;\n",
        &format!(
            "#[path = \"{}\"]\npub(crate) mod chat;\n",
            path_literal(&stream_dir.join("chat.rs"))
        ),
    );
    contents = replace_once_named(contents, "stream dashboard module", "mod dashboard;\n", "");
    contents = replace_once_named(
        contents,
        "stream discovery module",
        "mod discovery;\n",
        &format!(
            "#[path = \"{}\"]\nmod discovery;\n",
            path_literal(&stream_dir.join("discovery.rs"))
        ),
    );
    contents = replace_once_named(
        contents,
        "stream http module",
        "mod http;\n",
        &format!("#[path = \"{}\"]\nmod http;\n", path_literal(&http_path)),
    );
    contents = replace_once_named(
        contents,
        "stream websocket module",
        "mod websocket;\n",
        &format!(
            "#[path = \"{}\"]\nmod websocket;\n",
            path_literal(&stream_dir.join("websocket.rs"))
        ),
    );
    contents = replace_once_named(
        contents,
        "stream dashboard export",
        "pub use dashboard::run_dashboard_server;\n",
        "",
    );

    fs::write(destination.as_path(), contents).expect("failed to write generated stream module");
    destination
}

fn rewrite_stream_http_module(out_dir: &Path, source: &Path) -> PathBuf {
    let destination = out_dir.join("agent_browser_stream_http.rs");
    let contents = read_rewrite_source(source, "stream http module");
    let contents = replace_once_named(
        contents,
        "rust_embed import",
        "use rust_embed::Embed;\n",
        "",
    );
    let contents = replace_once_named(
        contents,
        "dashboard spawn_session import",
        "use super::dashboard::spawn_session;\n",
        "",
    );
    let contents = replace_once_named(
        contents,
        "dashboard assets embed",
        "#[derive(Embed)]\n#[folder = \"../packages/dashboard/out/\"]\nstruct DashboardAssets;\n\n",
        "",
    );
    let contents = replace_once_named(
        contents,
        "stream server session spawning",
        r##"        if path == "/api/sessions" {
            let result = spawn_session(body_str).await;
            let (status, resp_body) = match result {
                Ok(msg) => ("200 OK", msg),
                Err(e) => (
                    "400 Bad Request",
                    format!(
                        r#"{{"success":false,"error":{}}}"#,
                        serde_json::to_string(&e).unwrap_or_else(|_| format!("\"{}\"", e))
                    ),
                ),
            };
            let response = format!(
                "HTTP/1.1 {status}\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: {}\r\nConnection: close\r\n{CORS_HEADERS}\r\n",
                resp_body.len()
            );
            let _ = stream.write_all(response.as_bytes()).await;
            let _ = stream.write_all(resp_body.as_bytes()).await;
            return;
        }
"##,
        r##"        if path == "/api/sessions" {
            let resp_body = r#"{"success":false,"error":"Session creation is not available from the pyagentbrowser SDK stream server"}"#;
            let response = format!(
                "HTTP/1.1 400 Bad Request\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: {}\r\nConnection: close\r\n{CORS_HEADERS}\r\n",
                resp_body.len()
            );
            let _ = stream.write_all(response.as_bytes()).await;
            let _ = stream.write_all(resp_body.as_bytes()).await;
            return;
        }
"##,
    );
    let contents = replace_tail_named(
        contents,
        "dashboard asset serving",
        "pub(super) fn serve_embedded_file(url_path: &str) -> (&'static str, &'static str, Vec<u8>) {",
        r##"pub(super) fn serve_embedded_file(_url_path: &str) -> (&'static str, &'static str, Vec<u8>) {
    (
        "404 Not Found",
        "application/json; charset=utf-8",
        br#"{"success":false,"error":"Dashboard assets are not embedded in pyagentbrowser"}"#.to_vec(),
    )
}
"##,
    );
    fs::write(destination.as_path(), contents)
        .expect("failed to write generated stream http module");
    destination
}

fn replace_tail_named(
    contents: String,
    patch_name: &str,
    start: &str,
    replacement: &str,
) -> String {
    let occurrences = contents.matches(start).count();
    assert!(
        occurrences == 1,
        "generated upstream rewrite expected exactly one {patch_name} block, found {occurrences}"
    );
    let start_index = contents
        .find(start)
        .expect("rewrite anchor count was checked before replacement");
    let mut rewritten = contents;
    rewritten.replace_range(start_index.., replacement);
    rewritten
}

fn replace_once_named(
    contents: String,
    patch_name: &str,
    expected: &str,
    replacement: &str,
) -> String {
    let occurrences = contents.matches(expected).count();
    assert!(
        occurrences == 1,
        "generated upstream rewrite expected exactly one {patch_name} block, found {occurrences}"
    );
    contents.replacen(expected, replacement, 1)
}

fn replace_n_named(
    mut contents: String,
    patch_name: &str,
    expected: &str,
    replacement: &str,
    expected_count: usize,
) -> String {
    let occurrences = contents.matches(expected).count();
    assert!(
        occurrences == expected_count,
        "generated upstream rewrite expected exactly {expected_count} {patch_name} blocks, found {occurrences}"
    );
    for _ in 0..expected_count {
        contents = contents.replacen(expected, replacement, 1);
    }
    contents
}

fn upstream_cli_src_dir() -> PathBuf {
    manifest_dir().join("../../third_party/agent-browser/cli/src")
}

fn upstream_protocol_dir() -> PathBuf {
    manifest_dir().join("../../third_party/agent-browser/cli/cdp-protocol")
}

fn upstream_native_dir() -> PathBuf {
    upstream_cli_src_dir().join("native")
}

fn require_file(path: &Path) {
    println!("cargo:rerun-if-changed={}", path.display());
    assert!(
        path.exists(),
        "required upstream agent-browser file is missing: {}",
        path.display()
    );
}

fn path_literal(path: &Path) -> String {
    path.to_string_lossy().replace('\\', "\\\\")
}

fn line(output: &mut String, args: Arguments<'_>) {
    writeln!(output, "{args}").expect("failed to write generated module source");
}

#[allow(dead_code)]
#[derive(serde::Deserialize)]
struct ProtocolSpec {
    domains: Vec<Domain>,
}

#[allow(dead_code)]
#[derive(serde::Deserialize, Clone)]
struct Domain {
    #[serde(rename = "domain")]
    name: String,
    #[serde(default)]
    types: Vec<TypeDef>,
    #[serde(default)]
    commands: Vec<Command>,
    #[serde(default)]
    events: Vec<Event>,
}

#[allow(dead_code)]
#[derive(serde::Deserialize, Clone)]
struct TypeDef {
    id: String,
    #[serde(rename = "type", default)]
    type_kind: String,
    #[serde(default)]
    properties: Vec<Property>,
    #[serde(rename = "enum", default)]
    enum_values: Vec<String>,
    #[serde(default)]
    description: Option<String>,
}

#[allow(dead_code)]
#[derive(serde::Deserialize, Clone)]
struct Command {
    name: String,
    #[serde(default)]
    parameters: Vec<Property>,
    #[serde(default)]
    returns: Vec<Property>,
    #[serde(default)]
    description: Option<String>,
}

#[allow(dead_code)]
#[derive(serde::Deserialize, Clone)]
struct Event {
    name: String,
    #[serde(default)]
    parameters: Vec<Property>,
    #[serde(default)]
    description: Option<String>,
}

#[allow(dead_code)]
#[derive(serde::Deserialize, Clone)]
struct Property {
    name: String,
    #[serde(rename = "type", default)]
    type_kind: Option<String>,
    #[serde(rename = "$ref", default)]
    ref_type: Option<String>,
    #[serde(default)]
    optional: bool,
    #[serde(default)]
    description: Option<String>,
    #[serde(default)]
    items: Option<Box<ItemType>>,
    #[serde(rename = "enum", default)]
    enum_values: Vec<String>,
}

#[allow(dead_code)]
#[derive(serde::Deserialize, Clone)]
struct ItemType {
    #[serde(rename = "type", default)]
    type_kind: Option<String>,
    #[serde(rename = "$ref", default)]
    ref_type: Option<String>,
}

fn to_pascal_case(s: &str) -> String {
    let mut result = String::new();
    let mut capitalize = true;
    for c in s.chars() {
        if c == '_' || c == '-' || c == '.' {
            capitalize = true;
        } else if capitalize {
            result.push(c.to_ascii_uppercase());
            capitalize = false;
        } else {
            result.push(c);
        }
    }
    result
}

fn to_snake_case(s: &str) -> String {
    let mut result = String::new();
    let chars: Vec<char> = s.chars().collect();
    for (i, &c) in chars.iter().enumerate() {
        if c.is_uppercase() && i > 0 {
            // Only insert underscore at transitions from lowercase to uppercase,
            // or when an uppercase sequence ends (e.g. "DOM" -> "dom", not "d_o_m")
            let prev_upper = chars[i - 1].is_uppercase();
            let next_lower = chars.get(i + 1).is_some_and(|n| n.is_lowercase());
            if !prev_upper || next_lower {
                result.push('_');
            }
        }
        result.push(c.to_ascii_lowercase());
    }
    result
}

/// Resolve a $ref type reference. Cross-domain refs like "Page.FrameId" become
/// `super::cdp_page::FrameId`. Same-domain refs are used directly.
fn resolve_ref(
    r: &str,
    current_domain: &str,
    domain_types: &std::collections::HashMap<String, HashSet<String>>,
) -> String {
    let parts: Vec<&str> = r.split('.').collect();
    if parts.len() == 2 {
        let ref_domain = parts[0];
        let ref_type = parts[1];
        if ref_domain == current_domain {
            to_pascal_case(ref_type)
        } else {
            if domain_types
                .get(ref_domain)
                .is_some_and(|t| t.contains(ref_type))
            {
                format!(
                    "super::cdp_{}::{}",
                    to_snake_case(ref_domain),
                    to_pascal_case(ref_type)
                )
            } else {
                // Fall back to serde_json::Value for unknown cross-domain refs
                "serde_json::Value".to_string()
            }
        }
    } else {
        to_pascal_case(r)
    }
}

fn map_type_in_domain(
    prop: &Property,
    current_domain: &str,
    domain_types: &std::collections::HashMap<String, HashSet<String>>,
) -> String {
    if let Some(ref r) = prop.ref_type {
        let type_name = resolve_ref(r, current_domain, domain_types);
        if prop.optional {
            format!("Option<{}>", type_name)
        } else {
            type_name
        }
    } else if let Some(ref t) = prop.type_kind {
        let base = match t.as_str() {
            "string" => "String".to_string(),
            "integer" => "i64".to_string(),
            "number" => "f64".to_string(),
            "boolean" => "bool".to_string(),
            "object" => "serde_json::Value".to_string(),
            "any" => "serde_json::Value".to_string(),
            "array" => {
                if let Some(ref items) = prop.items {
                    let inner = if let Some(ref r) = items.ref_type {
                        resolve_ref(r, current_domain, domain_types)
                    } else {
                        match items.type_kind.as_deref().unwrap_or("any") {
                            "string" => "String".to_string(),
                            "integer" => "i64".to_string(),
                            "number" => "f64".to_string(),
                            "boolean" => "bool".to_string(),
                            _ => "serde_json::Value".to_string(),
                        }
                    };
                    format!("Vec<{}>", inner)
                } else {
                    "Vec<serde_json::Value>".to_string()
                }
            }
            _ => "serde_json::Value".to_string(),
        };
        if prop.optional {
            format!("Option<{}>", base)
        } else {
            base
        }
    } else if prop.optional {
        "Option<serde_json::Value>".to_string()
    } else {
        "serde_json::Value".to_string()
    }
}

fn is_rust_keyword(s: &str) -> bool {
    matches!(
        s,
        "type"
            | "self"
            | "Self"
            | "super"
            | "move"
            | "ref"
            | "fn"
            | "mod"
            | "use"
            | "pub"
            | "let"
            | "mut"
            | "const"
            | "static"
            | "if"
            | "else"
            | "for"
            | "while"
            | "loop"
            | "match"
            | "return"
            | "break"
            | "continue"
            | "as"
            | "in"
            | "impl"
            | "trait"
            | "struct"
            | "enum"
            | "where"
            | "async"
            | "await"
            | "dyn"
            | "box"
            | "yield"
            | "override"
            | "crate"
            | "extern"
    )
}

fn write_generated(output: &mut String, args: Arguments<'_>) {
    output
        .write_fmt(args)
        .expect("writing generated Rust to String should not fail");
}

fn generate_domain(
    domain: &Domain,
    domain_types: &std::collections::HashMap<String, HashSet<String>>,
    recursive_fields: &HashSet<(&str, &str, &str)>,
    output: &mut String,
) {
    let mod_name = to_snake_case(&domain.name);
    write_generated(
        output,
        format_args!(
            "#[allow(dead_code, non_snake_case, non_camel_case_types, clippy::enum_variant_names)]\npub mod cdp_{mod_name} {{\n"
        ),
    );
    output.push_str("    use super::*;\n\n");

    for type_def in &domain.types {
        if !type_def.enum_values.is_empty() {
            // Deduplicate enum variants (some CDP enums have duplicated PascalCase forms)
            let mut seen_variants = HashSet::new();
            output.push_str("    #[derive(Debug, Clone, Serialize, Deserialize)]\n");
            write_generated(output, format_args!("    pub enum {} {{\n", type_def.id));
            for val in &type_def.enum_values {
                let mut variant = to_pascal_case(val);
                if variant == "Self" {
                    variant = "SelfValue".to_string();
                }
                if variant.chars().next().is_some_and(|c| c.is_ascii_digit()) {
                    variant = format!("V{}", variant);
                }
                if seen_variants.insert(variant.clone()) {
                    write_generated(
                        output,
                        format_args!("        #[serde(rename = \"{val}\")]\n        {variant},\n"),
                    );
                }
            }
            output.push_str("    }\n\n");
        } else if type_def.type_kind == "object" && !type_def.properties.is_empty() {
            output.push_str(
                "    #[derive(Debug, Clone, Serialize, Deserialize)]\n    #[serde(rename_all = \"camelCase\")]\n",
            );
            write_generated(output, format_args!("    pub struct {} {{\n", type_def.id));
            for prop in &type_def.properties {
                let field_name = to_snake_case(&prop.name);
                let field_name = if is_rust_keyword(&field_name) {
                    format!("r#{}", field_name)
                } else {
                    field_name
                };
                let mut rust_type = map_type_in_domain(prop, &domain.name, domain_types);

                // Wrap recursive fields in Box
                if recursive_fields.contains(&(
                    domain.name.as_str(),
                    type_def.id.as_str(),
                    prop.name.as_str(),
                )) {
                    if rust_type.starts_with("Option<") {
                        let inner = &rust_type[7..rust_type.len() - 1];
                        rust_type = format!("Option<Box<{}>>", inner);
                    } else {
                        rust_type = format!("Box<{}>", rust_type);
                    }
                }

                if prop.optional {
                    output
                        .push_str("        #[serde(skip_serializing_if = \"Option::is_none\")]\n");
                }
                write_generated(
                    output,
                    format_args!("        pub {field_name}: {rust_type},\n"),
                );
            }
            output.push_str("    }\n\n");
        } else if type_def.type_kind == "object" && type_def.properties.is_empty() {
            write_generated(
                output,
                format_args!("    pub type {} = serde_json::Value;\n\n", type_def.id),
            );
        } else if type_def.type_kind == "array" {
            write_generated(
                output,
                format_args!("    pub type {} = Vec<serde_json::Value>;\n\n", type_def.id),
            );
        } else if type_def.type_kind == "string" && type_def.enum_values.is_empty() {
            write_generated(
                output,
                format_args!("    pub type {} = String;\n\n", type_def.id),
            );
        } else if type_def.type_kind == "integer" {
            write_generated(
                output,
                format_args!("    pub type {} = i64;\n\n", type_def.id),
            );
        } else if type_def.type_kind == "number" {
            write_generated(
                output,
                format_args!("    pub type {} = f64;\n\n", type_def.id),
            );
        }
    }

    for cmd in &domain.commands {
        let pascal_name = to_pascal_case(&cmd.name);

        if !cmd.parameters.is_empty() {
            output.push_str(
                "    #[derive(Debug, Clone, Serialize, Deserialize)]\n    #[serde(rename_all = \"camelCase\")]\n",
            );
            write_generated(
                output,
                format_args!("    pub struct {pascal_name}Params {{\n"),
            );
            for param in &cmd.parameters {
                let field_name = to_snake_case(&param.name);
                let field_name = if is_rust_keyword(&field_name) {
                    format!("r#{}", field_name)
                } else {
                    field_name
                };
                let rust_type = map_type_in_domain(param, &domain.name, domain_types);
                if param.optional {
                    output
                        .push_str("        #[serde(skip_serializing_if = \"Option::is_none\")]\n");
                }
                write_generated(
                    output,
                    format_args!("        pub {field_name}: {rust_type},\n"),
                );
            }
            output.push_str("    }\n\n");
        }

        if !cmd.returns.is_empty() {
            output.push_str(
                "    #[derive(Debug, Clone, Serialize, Deserialize)]\n    #[serde(rename_all = \"camelCase\")]\n",
            );
            write_generated(
                output,
                format_args!("    pub struct {pascal_name}Result {{\n"),
            );
            for ret in &cmd.returns {
                let field_name = to_snake_case(&ret.name);
                let field_name = if is_rust_keyword(&field_name) {
                    format!("r#{}", field_name)
                } else {
                    field_name
                };
                let rust_type = map_type_in_domain(ret, &domain.name, domain_types);
                if ret.optional {
                    output
                        .push_str("        #[serde(skip_serializing_if = \"Option::is_none\")]\n");
                }
                write_generated(
                    output,
                    format_args!("        pub {field_name}: {rust_type},\n"),
                );
            }
            output.push_str("    }\n\n");
        }
    }

    for event in &domain.events {
        if !event.parameters.is_empty() {
            let pascal_name = to_pascal_case(&event.name);
            output.push_str(
                "    #[derive(Debug, Clone, Serialize, Deserialize)]\n    #[serde(rename_all = \"camelCase\")]\n",
            );
            write_generated(
                output,
                format_args!("    pub struct {pascal_name}Event {{\n"),
            );
            for param in &event.parameters {
                let field_name = to_snake_case(&param.name);
                let field_name = if is_rust_keyword(&field_name) {
                    format!("r#{}", field_name)
                } else {
                    field_name
                };
                let rust_type = map_type_in_domain(param, &domain.name, domain_types);
                if param.optional {
                    output
                        .push_str("        #[serde(skip_serializing_if = \"Option::is_none\")]\n");
                }
                write_generated(
                    output,
                    format_args!("        pub {field_name}: {rust_type},\n"),
                );
            }
            output.push_str("    }\n\n");
        }
    }

    output.push_str("}\n\n");
}
