use std::{
    collections::HashSet,
    env,
    fmt::{Arguments, Write as _},
    fs,
    path::{Path, PathBuf},
};

const ROOT_MODULES: &[(&str, &str)] = &[
    ("ca_bundle", "ca_bundle.rs"),
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
    ("a11y", "a11y/mod.rs"),
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
    ("tab_binding", "tab_binding.rs"),
    ("tracing", "tracing.rs"),
    ("webdriver", "webdriver/mod.rs"),
    ("webmcp", "webmcp.rs"),
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
            "cdp" => rewrite_cdp_module(out_dir, &path),
            "element" => rewrite_element_module(out_dir, &path),
            "screenshot" => rewrite_screenshot_module(out_dir, &path),
            "snapshot" => rewrite_snapshot_module(out_dir, &path),
            "state" => rewrite_state_module(out_dir, &path),
            "stream" => rewrite_stream_module(out_dir, &path),
            "tab_binding" => rewrite_tab_binding_module(out_dir, &path),
            _ => path,
        };
        line(
            &mut output,
            format_args!(
                "#[allow(dead_code, clippy::new_without_default, clippy::should_implement_trait)]"
            ),
        );
        if matches!(*name, "actions" | "stream") {
            line(&mut output, format_args!("#[allow(private_interfaces)]"));
        }
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

fn rewrite_cdp_module(out_dir: &Path, source: &Path) -> PathBuf {
    let root = source.parent().expect("CDP module directory");
    let client_source = root.join("client.rs");
    require_file(&client_source);
    let contents = read_rewrite_source(&client_source, "CDP client");
    let contents = replace_once_named(
        contents, "context index field", "    next_id: AtomicU64,",
        "    contexts: Arc<std::sync::Mutex<crate::contexts::Contexts>>,\n    active_frame: std::sync::Mutex<Option<String>>,\n    strict_refs: std::sync::atomic::AtomicBool,\n    next_id: AtomicU64,",
    );
    let contents = replace_once_named(
        contents, "context index construction", "        let pending_clone = pending.clone();",
        "        let contexts = Arc::new(std::sync::Mutex::new(crate::contexts::Contexts::default()));\n        let reader_contexts = contexts.clone();\n        let pending_clone = pending.clone();",
    );
    let contents = replace_once_named(
        contents, "context event indexing", "                    let routed = event.session_id.as_deref().is_some_and(|sid| {",
        "                    reader_contexts.lock().unwrap_or_else(|e| e.into_inner()).apply(&event);\n                    let routed = event.session_id.as_deref().is_some_and(|sid| {",
    );
    let contents = replace_once_named(
        contents, "context client initialization", "            next_id: AtomicU64::new(1),",
        "            contexts,\n            active_frame: std::sync::Mutex::new(None),\n            strict_refs: std::sync::atomic::AtomicBool::new(false),\n            next_id: AtomicU64::new(1),",
    );
    let contents = replace_once_named(
        contents, "context lookup", "    pub fn subscribe(&self) -> broadcast::Receiver<CdpEvent> {",
        "    pub(crate) fn document_context(&self, session: &str, frame: &str) -> Option<crate::contexts::DocumentContext> {\n        self.contexts.lock().unwrap_or_else(|e| e.into_inner()).document(session, frame)\n    }\n\n    pub(crate) fn set_active_frame(&self, frame: Option<&str>) {\n        *self.active_frame.lock().unwrap_or_else(|e| e.into_inner()) = frame.map(str::to_owned);\n    }\n\n    pub(crate) fn active_frame(&self) -> Option<String> {\n        self.active_frame.lock().unwrap_or_else(|e| e.into_inner()).clone()\n    }\n\n    pub(crate) fn set_strict_refs(&self, strict: bool) {\n        self.strict_refs.store(strict, std::sync::atomic::Ordering::Relaxed);\n    }\n\n    pub(crate) fn strict_refs(&self) -> bool {\n        self.strict_refs.load(std::sync::atomic::Ordering::Relaxed)\n    }\n\n    pub fn subscribe(&self) -> broadcast::Receiver<CdpEvent> {",
    );
    let client = out_dir.join("agent_browser_cdp_client.rs");
    fs::write(&client, contents).expect("write CDP client");
    let mut module = String::new();
    for name in [
        "chrome",
        "client",
        "discovery",
        "lightpanda",
        "types",
        "windows_process",
    ] {
        let path = if name == "client" {
            client.clone()
        } else {
            root.join(format!("{name}.rs"))
        };
        require_file(&path);
        if name == "windows_process" {
            module.push_str("#[cfg(windows)]\n");
        }
        line(
            &mut module,
            format_args!("#[path = \"{}\"] pub mod {name};", path_literal(&path)),
        );
    }
    let destination = out_dir.join("agent_browser_cdp.rs");
    fs::write(&destination, module).expect("write CDP module");
    destination
}

fn rewrite_element_module(out_dir: &Path, source: &Path) -> PathBuf {
    let contents = read_rewrite_source(source, "element file");
    let contents = replace_once_named(contents, "ref map generation field",
        "pub struct RefMap {\n    map: HashMap<String, RefEntry>,",
        "static REF_GENERATION: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(1);\n\npub struct RefMap {\n    pub generation: u64,\n    map: HashMap<String, RefEntry>,");
    let contents = replace_once_named(contents, "ref map generation initialization",
        "            map: HashMap::new(),\n            next_ref: 1,",
        "            generation: REF_GENERATION.fetch_add(1, std::sync::atomic::Ordering::Relaxed),\n            map: HashMap::new(),\n            next_ref: 1,");
    let contents = replace_once_named(contents, "ref map generation invalidation",
        "    pub fn clear(&mut self) {\n        self.map.clear();",
        "    pub fn clear(&mut self) {\n        self.generation = REF_GENERATION.fetch_add(1, std::sync::atomic::Ordering::Relaxed);\n        self.map.clear();");
    let contents = rewrite_element_scope(contents);
    let destination = out_dir.join("agent_browser_element.rs");
    fs::write(&destination, contents).expect("write element module");
    destination
}

fn rewrite_element_scope(contents: String) -> String {
    let contents = replace_once_named(
        contents,
        "per-client frame scope",
        r###"/// Mirror of DaemonState.active_frame_id, refreshed before every command
/// (commands are serialized by the daemon's state lock, so this cannot
/// race). It lets CSS-selector resolution honor `frame <sel>` without
/// threading a parameter through every interaction signature; snapshot refs
/// already carry their frame through the ref map.
static ACTIVE_FRAME: std::sync::OnceLock<std::sync::Mutex<Option<String>>> =
    std::sync::OnceLock::new();

pub fn set_active_frame(frame_id: Option<&str>) {
    *ACTIVE_FRAME
        .get_or_init(|| std::sync::Mutex::new(None))
        .lock()
        .unwrap() = frame_id.map(String::from);
}

fn active_frame() -> Option<String> {
    ACTIVE_FRAME.get().and_then(|m| m.lock().unwrap().clone())
}

"###,
        "",
    );
    let contents = replace_n_named(
        contents,
        "client frame lookup",
        "active_frame()",
        "client.active_frame()",
        2,
    );
    let contents = replace_n_named(
        contents,
        "element owning session",
        "    if let Some(ref_id) = parse_ref(selector_or_ref) {",
        r#"    let frame = parse_ref(selector_or_ref)
        .and_then(|reference| ref_map.get(&reference))
        .and_then(|entry| entry.frame_id.clone())
        .or_else(|| client.active_frame());
    let session_id = match frame.as_deref() {
        Some(frame) => crate::contexts::session_for_frame(client, session_id, iframe_sessions, frame).await?,
        None => session_id,
    };
    if let Some(ref_id) = parse_ref(selector_or_ref) {"#,
        2,
    );
    let contents = replace_once_named(
        contents,
        "default world element lookup",
        r###"/// Find a selector inside a same-process iframe and return its center in
/// top-level viewport coordinates (input events dispatch in that space).
/// Same-origin access to contentDocument is what makes this possible; a
/// cross-origin frame never takes this path because it has its own session.
async fn resolve_center_in_same_process_frame(
    client: &CdpClient,
    session_id: &str,
    frame_id: &str,
    selector: &str,
) -> Result<(f64, f64), String> {
    let owner_object_id = frame_owner_object_id(client, session_id, frame_id).await?;
    let find_expr = build_find_element_js_in("doc", selector);
    let function = format!(
        r#"function() {{
            const doc = this.contentDocument;
            if (!doc) return null;
            const el = {find_expr};
            if (!el) return null;
            if (el.scrollIntoViewIfNeeded) el.scrollIntoViewIfNeeded(true);
            else el.scrollIntoView({{ block: 'center', inline: 'center' }});
            const rect = el.getBoundingClientRect();
            let x = rect.x + rect.width / 2;
            let y = rect.y + rect.height / 2;
            let win = doc.defaultView;
            while (win && win.frameElement) {{
                const frameRect = win.frameElement.getBoundingClientRect();
                x += frameRect.x + win.frameElement.clientLeft;
                y += frameRect.y + win.frameElement.clientTop;
                win = win.parent;
            }}
            const blockerAt = {BLOCKER_AT_JS};
            const topDoc = win ? win.document : doc;
            return {{ x: x, y: y, blocker: blockerAt(topDoc, el, x, y) }};
        }}"#,
    );
    let result = client
        .send_command(
            "Runtime.callFunctionOn",
            Some(serde_json::json!({
                "objectId": owner_object_id,
                "functionDeclaration": function,
                "returnByValue": true,
            })),
            Some(session_id),
        )
        .await?;
    let value = result.get("result").and_then(|r| r.get("value"));
    if let Some(blocker) = value
        .and_then(|v| v.get("blocker"))
        .and_then(|v| v.as_str())
    {
        return Err(intercepted_error(selector, blocker));
    }
    let x = value.and_then(|v| v.get("x")).and_then(|v| v.as_f64());
    let y = value.and_then(|v| v.get("y")).and_then(|v| v.as_f64());
    match (x, y) {
        (Some(x), Some(y)) => Ok((x, y)),
        _ => Err(format!(
            "Element not found in the selected frame: {}",
            selector
        )),
    }
}

/// Find a selector inside a same-process iframe and return its object handle.
async fn resolve_object_in_same_process_frame(
    client: &CdpClient,
    session_id: &str,
    frame_id: &str,
    selector: &str,
) -> Result<String, String> {
    let owner_object_id = frame_owner_object_id(client, session_id, frame_id).await?;
    let find_expr = build_find_element_js_in("doc", selector);
    let function = format!(
        "function() {{ const doc = this.contentDocument; if (!doc) return null; return {find_expr}; }}",
    );
    let result = client
        .send_command(
            "Runtime.callFunctionOn",
            Some(serde_json::json!({
                "objectId": owner_object_id,
                "functionDeclaration": function,
                "returnByValue": false,
            })),
            Some(session_id),
        )
        .await?;
    result
        .get("result")
        .and_then(|r| r.get("objectId"))
        .and_then(|v| v.as_str())
        .map(String::from)
        .ok_or_else(|| format!("Element not found in the selected frame: {}", selector))
}

"###,
        r###"async fn resolve_object_in_same_process_frame(
    client: &CdpClient,
    session_id: &str,
    frame_id: &str,
    selector: &str,
) -> Result<String, String> {
    let (_, result) = crate::contexts::evaluate_remote(
        client, session_id, &HashMap::new(), frame_id,
        &build_find_element_js(selector), false,
    ).await?;
    result.pointer("/result/objectId").and_then(Value::as_str).map(str::to_owned)
        .ok_or_else(|| format!("Element not found in the selected frame: {}", selector))
}

async fn resolve_center_in_same_process_frame(
    client: &CdpClient,
    session_id: &str,
    frame_id: &str,
    selector: &str,
) -> Result<(f64, f64), String> {
    let object = resolve_object_in_same_process_frame(client, session_id, frame_id, selector).await?;
    let node = client.send_command("DOM.describeNode", Some(serde_json::json!({"objectId": object})), Some(session_id)).await?;
    let backend = node.pointer("/node/backendNodeId").and_then(Value::as_i64)
        .ok_or_else(|| format!("Element is not a DOM node: {}", selector))?;
    scroll_node_into_view(client, session_id, backend).await;
    let result: DomGetBoxModelResult = client.send_command_typed(
        "DOM.getBoxModel", &DomGetBoxModelParams {
            backend_node_id: Some(backend), node_id: None, object_id: None,
        }, Some(session_id),
    ).await?;
    let (x, y) = box_model_center(&result.model);
    check_node_interception(client, session_id, backend, selector, x, y).await?;
    Ok((x, y))
}

"###,
    );
    let contents = replace_n_named(
        contents,
        "typed refs retain captured node identity",
        "        // Fallback: re-query the accessibility tree to find a fresh node by role/name",
        "        if client.strict_refs() {\n            return Err(format!(\"stale_ref: Captured node for {} is detached\", selector_or_ref));\n        }\n\n        // Fallback: re-query the accessibility tree to find a fresh node by role/name",
        2,
    );
    let contents = replace_once_named(
        contents,
        "typed ref object connectivity",
        r#"                if let Some(object_id) = r.object.object_id {
                    return Ok((object_id, effective_session_id.to_string()));
                }"#,
        r#"                if let Some(object_id) = r.object.object_id {
                    if client.strict_refs() {
                        let connected = client.send_command("Runtime.callFunctionOn", Some(serde_json::json!({
                            "objectId": object_id,
                            "functionDeclaration": "function() { return this.isConnected; }",
                            "returnByValue": true,
                        })), Some(effective_session_id)).await?;
                        if connected.pointer("/result/value").and_then(Value::as_bool) != Some(true) {
                            return Err(format!("stale_ref: Captured node for {} is detached", selector_or_ref));
                        }
                    }
                    return Ok((object_id, effective_session_id.to_string()));
                }"#,
    );
    replace_once_named(
        contents,
        "frame geometry owner access",
        "pub(super) async fn frame_owner_object_id(",
        "pub(crate) async fn frame_owner_object_id(",
    )
}

fn rewrite_browser_module(out_dir: &Path, source: &Path) -> PathBuf {
    let destination = out_dir.join("agent_browser_browser.rs");
    let contents = read_rewrite_source(source, "browser file");
    assert!(
        contents.contains("\"targetId\": p.target_id"),
        "upstream tab_list target id contract changed"
    );
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

fn rewrite_actions_module(out_dir: &Path, source: &Path) -> PathBuf {
    let destination = out_dir.join("agent_browser_actions.rs");
    let contents = read_rewrite_source(source, "actions file");
    let contents = rewrite_confirmation_handling(contents);
    let contents = rewrite_actions_namespace(contents);
    let contents = rewrite_scoped_page_commands(contents);
    let contents = rewrite_frame_commands(contents);
    let contents = rewrite_scoped_waits(contents);
    let contents = rewrite_frame_capture(contents);
    let contents = rewrite_dashboard_streaming(contents);
    let contents = rewrite_stream_result_success(contents);
    fs::write(destination.as_path(), contents).expect("failed to write generated actions file");
    destination
}

fn rewrite_frame_capture(contents: String) -> String {
    const UPSTREAM_OPTIONS_END: &str = r#"        output_dir: cmd
            .get("screenshotDir")
            .and_then(|v| v.as_str())
            .map(String::from),
    };

    if annotate {"#;
    const FRAME_OPTIONS_END: &str = r#"        output_dir: cmd
            .get("screenshotDir")
            .and_then(|v| v.as_str())
            .map(String::from),
        frame_id: state.active_frame_id.clone(),
    };

    if options.frame_id.is_some() && options.full_page {
        return Err("Frame screenshots capture the rendered frame rectangle. fullPage is a page capture option".to_string());
    }
    if options.frame_id.is_some() && annotate {
        return Err("Annotated frame screenshots require selector-scoped page capture".to_string());
    }

    if annotate {"#;
    const UPSTREAM_DIFF_OPTIONS: &str = r#"        annotate: false,
        output_dir: None,
    };

    let result = screenshot::take_screenshot("#;
    const FRAME_DIFF_OPTIONS: &str = r#"        annotate: false,
        output_dir: None,
        frame_id: state.active_frame_id.clone(),
    };

    let result = screenshot::take_screenshot("#;
    const UPSTREAM_SCREENSHOT_RESULT: &str =
        r#"    let mut response = json!({ "path": result.path });"#;
    const SCOPED_SCREENSHOT_RESULT: &str = r#"    let origin = eval_body_in_active_frame(
        mgr,
        state.active_frame_id.as_deref(),
        &session_id,
        &state.iframe_sessions,
        "(root) => root.defaultView.location.href",
    )
    .await?
    .as_str()
    .unwrap_or_default()
    .to_string();
    let target_id = mgr.active_target_id().ok();
    let mut response = json!({
        "path": result.path,
        "origin": origin,
        "targetId": target_id,
        "frameId": state.active_frame_id.clone(),
    });"#;
    let rewritten = replace_once_named(
        contents,
        "frame screenshot options",
        UPSTREAM_OPTIONS_END,
        FRAME_OPTIONS_END,
    );
    let rewritten = replace_once_named(
        rewritten,
        "frame diff screenshot options",
        UPSTREAM_DIFF_OPTIONS,
        FRAME_DIFF_OPTIONS,
    );
    replace_once_named(
        rewritten,
        "screenshot document identity",
        UPSTREAM_SCREENSHOT_RESULT,
        SCOPED_SCREENSHOT_RESULT,
    )
}

fn rewrite_screenshot_module(out_dir: &Path, source: &Path) -> PathBuf {
    let destination = out_dir.join("agent_browser_screenshot.rs");
    let contents = read_rewrite_source(source, "screenshot file");
    const UPSTREAM_OPTIONS: &str = r#"    pub annotate: bool,
    pub output_dir: Option<String>,
}"#;
    const FRAME_OPTIONS: &str = r#"    pub annotate: bool,
    pub output_dir: Option<String>,
    pub frame_id: Option<String>,
}"#;
    const UPSTREAM_DEFAULT: &str = r#"            annotate: false,
            output_dir: None,
        }"#;
    const FRAME_DEFAULT: &str = r#"            annotate: false,
            output_dir: None,
            frame_id: None,
        }"#;
    const UPSTREAM_CAPTURE_BRANCH: &str = r#"    if options.full_page {
        let metrics: Value = client"#;
    const FRAME_CAPTURE_BRANCH: &str = r#"    if let Some(frame_id) = options.frame_id.as_deref() {
        let rect = crate::contexts::frame_rect(client, session_id, iframe_sessions, frame_id).await?;
        params.clip = Some(Viewport {
            x: rect.x,
            y: rect.y,
            width: rect.width,
            height: rect.height,
            scale: 1.0,
        });
    } else if options.full_page {
        let metrics: Value = client"#;

    let rewritten = replace_once_named(
        contents,
        "frame screenshot option",
        UPSTREAM_OPTIONS,
        FRAME_OPTIONS,
    );
    let rewritten = replace_once_named(
        rewritten,
        "frame screenshot default",
        UPSTREAM_DEFAULT,
        FRAME_DEFAULT,
    );
    let rewritten = replace_once_named(
        rewritten,
        "frame screenshot clip",
        UPSTREAM_CAPTURE_BRANCH,
        FRAME_CAPTURE_BRANCH,
    );
    fs::write(destination.as_path(), rewritten).expect("failed to write generated screenshot file");
    destination
}

fn rewrite_snapshot_module(out_dir: &Path, source: &Path) -> PathBuf {
    let destination = out_dir.join("agent_browser_snapshot.rs");
    let contents = read_rewrite_source(source, "snapshot file");
    const UPSTREAM_AX_SCOPE: &str = r#"    let (ax_params, effective_session_id) =
        resolve_ax_session(frame_id, session_id, iframe_sessions);"#;
    const NESTED_AX_SCOPE: &str = r#"    let parent_session_id = match frame_id {
        Some(frame) => crate::contexts::session_for_frame(client, session_id, iframe_sessions, frame).await?,
        None => session_id,
    };
    let (ax_params, effective_session_id) =
        resolve_ax_session(frame_id, parent_session_id, iframe_sessions);"#;

    let rewritten = replace_once_named(
        contents,
        "nested frame accessibility session",
        UPSTREAM_AX_SCOPE,
        NESTED_AX_SCOPE,
    );
    fs::write(destination.as_path(), rewritten).expect("failed to write generated snapshot file");
    destination
}

fn rewrite_scoped_page_commands(contents: String) -> String {
    const UPSTREAM_SCOPE_SYNC: &str = r#"    // Keep element resolution in sync with the `frame` selection (see
    // element::set_active_frame for why this is mirrored).
    super::element::set_active_frame(state.active_frame_id.as_deref());"#;
    const SCOPED_SYNC: &str =
        r#"    // Explicit page and frame scope is applied after policy admission."#;
    const UPSTREAM_POLICY_ACTIONS: &str =
        r#"    let policy_actions = policy_actions_for_command(cmd, action, needs_launch);"#;
    const SCOPED_POLICY_ACTIONS: &str = r#"    let needs_scope_switch = cmd
        .get("_targetId")
        .and_then(Value::as_str)
        .is_some_and(|target_id| {
            needs_launch
                || state
                    .browser
                    .as_ref()
                    .and_then(|manager| manager.active_target_id().ok())
                    != Some(target_id)
        });
    let mut policy_actions = policy_actions_for_command(cmd, action, needs_launch);
    if needs_scope_switch {
        policy_actions.insert(0, "tab_switch".to_string());
    }"#;
    const UPSTREAM_ACTION_DISPATCH: &str = r#"    let result = match action {"#;
    const SCOPED_ACTION_DISPATCH: &str = r#"    if let Some(expected) = cmd.get("_refGeneration").and_then(Value::as_u64) {
        if expected != state.ref_map.generation {
            return json!({ "id": id, "success": false, "code": "stale_ref", "error": "Snapshot ref generation expired" });
        }
    }

    if let Some(target_id) = cmd.get("_targetId").and_then(Value::as_str) {
        let current_target = state
            .browser
            .as_ref()
            .and_then(|manager| manager.active_target_id().ok());
        if current_target != Some(target_id) {
            let tab_id = state.browser.as_ref()
                .and_then(|manager| manager.tab_list().into_iter().find(|tab| tab["targetId"].as_str() == Some(target_id)))
                .and_then(|tab| tab["tabId"].as_str().map(str::to_owned));
            let Some(tab_id) = tab_id else {
                let mut response = error_response(&id, &format!("No tab with target id: {}", target_id));
                response["code"] = json!("frame_scope");
                return response;
            };
            let switch = json!({ "tabId": tab_id });
            if let Err(error) = handle_tab_switch(&switch, state).await {
                return error_response(&id, &super::browser::to_ai_friendly_error(&error));
            }
        }
    }

    if let Some(frame_id) = cmd.get("_frameId").and_then(Value::as_str) {
        state.active_frame_id = (!frame_id.is_empty()).then(|| frame_id.to_string());
    }

    // Element resolution belongs to this native session's client.
    if let Some(manager) = state.browser.as_ref() {
        manager.client.set_active_frame(state.active_frame_id.as_deref());
        manager.client.set_strict_refs(cmd.get("_refGeneration").is_some());
    }

    let result = match action {"#;
    const UPSTREAM_INTERNAL_FIELDS: &str = r#"            || cmd.get("restoreCheckFn").is_some();"#;
    const SCOPED_INTERNAL_FIELDS: &str = r#"            || cmd.get("restoreCheckFn").is_some()
            || cmd.get("_targetId").is_some()
            || cmd.get("_frameId").is_some()
            || cmd.get("_refGeneration").is_some();"#;
    const UPSTREAM_REMOVE_INTERNAL: &str = r#"                obj.remove("restoreCheckFn");"#;
    const SCOPED_REMOVE_INTERNAL: &str = r#"                obj.remove("restoreCheckFn");
                obj.remove("_targetId");
                obj.remove("_frameId");
                obj.remove("_refGeneration");"#;
    const UPSTREAM_SAME_PROCESS_EVALUATE: &str = r#"        Some(fid) if !iframe_sessions.contains_key(fid) => {
            let owner =
                super::element::frame_owner_object_id(&mgr.client, top_session, fid).await?;
            let func = format!(
                "function() {{ const d = this.contentDocument; if (!d) return null; return ({body})(d); }}"
            );
            let res = mgr
                .client
                .send_command(
                    "Runtime.callFunctionOn",
                    Some(serde_json::json!({
                        "objectId": owner,
                        "functionDeclaration": func,
                        "returnByValue": true,
                    })),
                    Some(top_session),
                )
                .await?;
            Ok(res
                .get("result")
                .and_then(|r| r.get("value"))
                .cloned()
                .unwrap_or(Value::Null))
        }"#;
    const AWAITED_SAME_PROCESS_EVALUATE: &str = r#"        Some(fid) if !iframe_sessions.contains_key(fid) => {
            crate::contexts::evaluate(&mgr.client, top_session, iframe_sessions, fid, &format!("({body})(document)")).await
        }"#;
    const UPSTREAM_OOPIF_EVALUATE: &str = r#"                        expression: format!("({body})(document)"),
                        return_by_value: Some(true),
                        await_promise: Some(false),"#;
    const AWAITED_OOPIF_EVALUATE: &str = r#"                        expression: format!("({body})(document)"),
                        return_by_value: Some(true),
                        await_promise: Some(true),"#;
    const UPSTREAM_OOPIF_RESULT: &str =
        r#"            Ok(res.result.value.unwrap_or(Value::Null))"#;
    const CHECKED_OOPIF_RESULT: &str = r#"            if let Some(details) = res.exception_details {
                let message = details
                    .exception
                    .as_ref()
                    .and_then(|value| value.description.as_deref())
                    .unwrap_or(&details.text);
                return Err(format!("Evaluation error: {}", message));
            }
            Ok(res.result.value.unwrap_or(Value::Null))"#;
    const UPSTREAM_EVALUATE: &str = r#"    let result = mgr.evaluate(script, None).await?;
    let url = mgr.get_url().await.unwrap_or_default();
    Ok(json!({ "result": result, "origin": url }))"#;
    const SCOPED_EVALUATE: &str = r#"    let target_id = mgr.active_target_id().ok();
    let (result, origin) = if let Some(frame) = state.active_frame_id.as_deref() {
        let session = mgr.active_session_id()?;
        let result = crate::contexts::evaluate(&mgr.client, session, &state.iframe_sessions, frame, script).await?;
        let origin = crate::contexts::evaluate(&mgr.client, session, &state.iframe_sessions, frame, "location.href").await?;
        (result, origin)
    } else {
        (mgr.evaluate(script, None).await?, json!(mgr.get_url().await?))
    };
    Ok(json!({ "result": result, "origin": origin, "targetId": target_id }))"#;

    let rewritten = replace_once_named(
        contents,
        "explicit page and frame command scope",
        UPSTREAM_SCOPE_SYNC,
        SCOPED_SYNC,
    );
    let rewritten = replace_once_named(
        rewritten,
        "conditional scoped tab policy action",
        UPSTREAM_POLICY_ACTIONS,
        SCOPED_POLICY_ACTIONS,
    );
    let rewritten = replace_once_named(
        rewritten,
        "post-policy command scope",
        UPSTREAM_ACTION_DISPATCH,
        SCOPED_ACTION_DISPATCH,
    );
    let rewritten = replace_once_named(
        rewritten,
        "scope switching through blocked dialogs",
        "        let safe_during_dialog = (skip_launch && !read_touches_active_tab)",
        "        let safe_during_dialog = needs_scope_switch || (skip_launch && !read_touches_active_tab)",
    );
    let rewritten = replace_once_named(
        rewritten,
        "native evidence and target metadata",
        "    attach_webmcp_availability(&mut resp, action, state).await;",
        "    attach_webmcp_availability(&mut resp, action, state).await;\n    resp[\"refGeneration\"] = json!(state.ref_map.generation);\n    resp[\"scopeSwitched\"] = json!(needs_scope_switch);\n    let current_target = state.browser.as_ref().and_then(|manager| manager.active_target_id().ok());\n    resp[\"targetId\"] = json!(current_target);\n    if let Some(data) = resp.get_mut(\"data\").and_then(Value::as_object_mut) {\n        data.insert(\"refGeneration\".to_string(), json!(state.ref_map.generation));\n        data.entry(\"targetId\".to_string()).or_insert_with(|| json!(current_target));\n    }",
    );
    let rewritten = replace_once_named(
        rewritten,
        "navigation invalidates snapshot refs",
        "                    let session_matches = if let Some(ref browser) = self.browser {",
        "                    if matches!(event.method.as_str(), \"Page.frameNavigated\" | \"Page.frameDetached\") {\n                        self.ref_map.clear();\n                    }\n\n                    let session_matches = if let Some(ref browser) = self.browser {",
    );
    let rewritten = replace_once_named(
        rewritten,
        "process detach invalidates snapshot refs",
        "                                detached_iframe_sessions.push(sid.to_string());",
        "                                self.ref_map.clear();\n                                detached_iframe_sessions.push(sid.to_string());",
    );
    let rewritten = replace_once_named(
        rewritten,
        "typed document scope errors",
        r#"    let mut resp = match result {
        Ok(data) => success_response(&id, data),
        Err(e) => error_response(&id, &super::browser::to_ai_friendly_error(&e)),
    };"#,
        r#"    let mut resp = match result {
        Ok(data) => success_response(&id, data),
        Err(e) => {
            let mut response = error_response(&id, &super::browser::to_ai_friendly_error(&e));
            if e.starts_with("Frame execution context detached:") || e.starts_with("Frame parent detached:")
                || (e.starts_with("CDP error (") && (e.contains("Frame with the given frameId is not found")
                    || e.contains("Cannot find context with specified id")
                    || e.contains("Cannot find context with specified unique id")))
            {
                response["code"] = json!("frame_detached");
            } else if e.starts_with("stale_ref:") {
                response["code"] = json!("stale_ref");
            }
            response
        }
    };"#,
    );
    let rewritten = replace_once_named(
        rewritten,
        "frame-scoped evaluation",
        UPSTREAM_EVALUATE,
        SCOPED_EVALUATE,
    );
    let rewritten = replace_once_named(
        rewritten,
        "semantic role owning session",
        r#"    let (ax_params, effective_session_id) = super::element::resolve_ax_session(
        state.active_frame_id.as_deref(),
        &session_id,
        &state.iframe_sessions,
    );"#,
        r#"    let owner_session = match state.active_frame_id.as_deref() {
        Some(frame) => crate::contexts::session_for_frame(&mgr.client, &session_id, &state.iframe_sessions, frame).await?,
        None => &session_id,
    };
    let (ax_params, effective_session_id) = super::element::resolve_ax_session(
        state.active_frame_id.as_deref(),
        owner_session,
        &state.iframe_sessions,
    );"#,
    );
    let rewritten = replace_once_named(
        rewritten,
        "scoped command broadcast detection",
        UPSTREAM_INTERNAL_FIELDS,
        SCOPED_INTERNAL_FIELDS,
    );
    let rewritten = replace_once_named(
        rewritten,
        "scoped command broadcast filtering",
        UPSTREAM_REMOVE_INTERNAL,
        SCOPED_REMOVE_INTERNAL,
    );
    let rewritten = replace_once_named(
        rewritten,
        "awaited same-process frame evaluation",
        UPSTREAM_SAME_PROCESS_EVALUATE,
        AWAITED_SAME_PROCESS_EVALUATE,
    );
    let rewritten = replace_once_named(
        rewritten,
        "awaited out-of-process frame evaluation",
        UPSTREAM_OOPIF_EVALUATE,
        AWAITED_OOPIF_EVALUATE,
    );
    replace_once_named(
        rewritten,
        "out-of-process frame evaluation errors",
        UPSTREAM_OOPIF_RESULT,
        CHECKED_OOPIF_RESULT,
    )
}

fn rewrite_frame_commands(contents: String) -> String {
    const UPSTREAM_REQUIRE_SELECTOR: &str = r#"    if selector.is_none() && name.is_none() && url.is_none() {
        return Err("At least one of 'selector', 'name', or 'url' is required".to_string());
    }

    let tree_result = mgr
        .client
        .send_command_no_params("Page.getFrameTree", Some(&session_id))
        .await?;"#;
    const FRAME_TREE_SUPPORT: &str = r#"    let tree_result = mgr
        .client
        .send_command_no_params("Page.getFrameTree", Some(&session_id))
        .await?;

    if cmd.get("list").and_then(Value::as_bool) == Some(true) {
        let mut oopif_frame_trees = Vec::new();
        for (frame_id, frame_session) in &state.iframe_sessions {
            let result = mgr
                .client
                .send_command_no_params("Page.getFrameTree", Some(frame_session))
                .await?;
            if let Some(frame_tree) = result.get("frameTree").cloned() {
                oopif_frame_trees.push(json!({
                    "rootFrameId": frame_id,
                    "frameTree": frame_tree,
                }));
            }
        }
        return Ok(json!({
            "frameTree": tree_result.get("frameTree").cloned().unwrap_or(Value::Null),
            "oopifFrameTrees": oopif_frame_trees,
        }));
    }

    if selector.is_none() && name.is_none() && url.is_none() {
        return Err("Pass selector, name, or url to resolve one frame".to_string());
    }"#;
    const UPSTREAM_FRAME_TREE: &str = r#"    let frame_tree = &tree_result["frameTree"];

    // If selector is a ref (@e1), resolve the iframe element from the ref map"#;
    const SCOPED_FRAME_TREE: &str = r#"    let frame_tree = &tree_result["frameTree"];
    fn frame_subtree<'a>(tree: &'a Value, frame_id: &str) -> Option<&'a Value> {
        if tree
            .get("frame")
            .and_then(|frame| frame.get("id"))
            .and_then(Value::as_str)
            == Some(frame_id)
        {
            return Some(tree);
        }
        tree.get("childFrames")
            .and_then(Value::as_array)
            .and_then(|children| children.iter().find_map(|child| frame_subtree(child, frame_id)))
    }
    let search_tree = state
        .active_frame_id
        .as_deref()
        .and_then(|frame_id| frame_subtree(frame_tree, frame_id))
        .unwrap_or(frame_tree);

    // If selector is a ref (@e1), resolve the iframe element from the ref map"#;
    const UPSTREAM_FRAME_RESOLVER_END: &str = r#"        None
    }

    let frame_tree = &tree_result["frameTree"];"#;
    const OOPIF_RESOLVER: &str = r#"        None
    }

    async fn find_oopif(
        mgr: &BrowserManager,
        sessions: &HashMap<String, String>,
        name: Option<&str>,
        url: Option<&str>,
    ) -> Result<Option<String>, String> {
        for (frame_id, session_id) in sessions {
            let result = mgr
                .client
                .send_command_no_params("Page.getFrameTree", Some(session_id))
                .await?;
            let frame = &result["frameTree"]["frame"];
            let frame_name = frame.get("name").and_then(Value::as_str).unwrap_or("");
            let frame_url = frame.get("url").and_then(Value::as_str).unwrap_or("");
            if name.is_some_and(|value| value == frame_name)
                || url.is_some_and(|value| frame_url.contains(value))
            {
                return Ok(Some(frame_id.clone()));
            }
        }
        Ok(None)
    }

    let frame_tree = &tree_result["frameTree"];"#;
    const UPSTREAM_SELECTOR_EVALUATE: &str = r##"        let js = format!(
            r#"(() => {{
                const el = document.querySelector({});
                if (!el) return null;
                if (el.tagName === 'IFRAME' || el.tagName === 'FRAME') {{
                    return el.name || el.id || el.src || null;
                }}
                return null;
            }})()"#,
            serde_json::to_string(sel).unwrap_or_default()
        );
        let result = mgr.evaluate(&js, None).await?;
        let frame_name = result.as_str().ok_or("Could not find frame for selector")?;
        if let Some(frame_id) = find_frame(frame_tree, Some(frame_name), None) {
            state.active_frame_id = Some(frame_id);
            return Ok(json!({ "frame": frame_name }));
        }"##;
    const SCOPED_SELECTOR_EVALUATE: &str = r##"        let (object_id, effective_session) =
            super::element::resolve_element_object_id(
                &mgr.client,
                &session_id,
                &state.ref_map,
                sel,
                &state.iframe_sessions,
            )
            .await?;
        let described = mgr
            .client
            .send_command(
                "DOM.describeNode",
                Some(json!({ "objectId": object_id, "depth": 1 })),
                Some(&effective_session),
            )
            .await?;
        let node = &described["node"];
        let node_name = node.get("nodeName").and_then(Value::as_str).unwrap_or("");
        if node_name != "IFRAME" && node_name != "FRAME" {
            return Err(format!("Selector {} does not point to an iframe element", sel));
        }
        let frame_id = node
            .get("contentDocument")
            .and_then(|document| document.get("frameId"))
            .or_else(|| node.get("frameId"))
            .and_then(Value::as_str)
            .ok_or_else(|| format!("Could not resolve frame ID for selector {}", sel))?
            .to_string();
        state.active_frame_id = Some(frame_id.clone());
        return Ok(json!({ "frame": sel, "frameId": frame_id }));"##;

    let mut rewritten = replace_once_named(
        contents,
        "native frame tree inspection",
        UPSTREAM_REQUIRE_SELECTOR,
        FRAME_TREE_SUPPORT,
    );
    rewritten = replace_once_named(
        rewritten,
        "parent-scoped frame tree",
        UPSTREAM_FRAME_TREE,
        SCOPED_FRAME_TREE,
    );
    rewritten = replace_once_named(
        rewritten,
        "out-of-process frame resolver",
        UPSTREAM_FRAME_RESOLVER_END,
        OOPIF_RESOLVER,
    );
    rewritten = replace_once_named(
        rewritten,
        "parent-scoped frame selector",
        UPSTREAM_SELECTOR_EVALUATE,
        SCOPED_SELECTOR_EVALUATE,
    );
    rewritten = replace_once_named(
        rewritten,
        "ref frame identity",
        "state.active_frame_id = Some(frame_id.to_string());\n            return Ok(json!({ \"frame\": label }));",
        "state.active_frame_id = Some(frame_id.to_string());\n            return Ok(json!({ \"frame\": label, \"frameId\": frame_id }));",
    );
    rewritten = replace_once_named(
        rewritten,
        "named frame identity",
        "return Ok(json!({ \"frame\": label }));\n    }\n\n    Err(\"Frame not found\".to_string())",
        "return Ok(json!({ \"frame\": label, \"frameId\": frame_id }));\n    }\n\n    Err(\"Frame not found; inspect the frame tree and choose one exact frame\".to_string())",
    );
    rewritten = replace_n_named(
        rewritten,
        "retained resolved frame identity",
        "state.active_frame_id = Some(frame_id);",
        "state.active_frame_id = Some(frame_id.clone());",
        1,
    );
    rewritten = replace_once_named(
        rewritten,
        "named OOPIF fallback",
        "    if let Some(frame_id) = find_frame(frame_tree, name, url) {\n        let label = name.or(url).unwrap_or(\"frame\");\n        state.active_frame_id = Some(frame_id.clone());\n        return Ok(json!({ \"frame\": label, \"frameId\": frame_id }));\n    }",
        "    if let Some(frame_id) = find_frame(search_tree, name, url) {\n        let label = name.or(url).unwrap_or(\"frame\");\n        state.active_frame_id = Some(frame_id.clone());\n        return Ok(json!({ \"frame\": label, \"frameId\": frame_id }));\n    }\n    if let Some(frame_id) = find_oopif(mgr, &state.iframe_sessions, name, url).await? {\n        let label = name.or(url).unwrap_or(\"frame\");\n        state.active_frame_id = Some(frame_id.clone());\n        return Ok(json!({ \"frame\": label, \"frameId\": frame_id }));\n    }",
    );
    rewritten
}

fn rewrite_scoped_waits(contents: String) -> String {
    const UPSTREAM_WAIT_TEXT: &str = r#"    if let Some(text) = cmd.get("text").and_then(|v| v.as_str()) {
        wait_for_text(&mgr.client, &session_id, text, timeout_ms).await?;
        return Ok(json!({ "waited": "text", "text": text }));
    }"#;
    const SCOPED_WAIT_TEXT: &str = r#"    if let Some(text) = cmd.get("text").and_then(|v| v.as_str()) {
        if state.active_frame_id.is_some() {
            let text_json = serde_json::to_string(text).unwrap_or_default();
            let body = format!("(root) => (root.body?.innerText || '').includes({text_json})");
            poll_active_frame(
                mgr,
                state.active_frame_id.as_deref(),
                &session_id,
                &state.iframe_sessions,
                &body,
                timeout_ms,
                |value| value.as_bool() == Some(true),
            )
            .await?;
        } else {
            wait_for_text(&mgr.client, &session_id, text, timeout_ms).await?;
        }
        return Ok(json!({ "waited": "text", "text": text }));
    }"#;
    const UPSTREAM_WAIT_URL: &str = r#"    if let Some(url_pattern) = cmd.get("url").and_then(|v| v.as_str()) {
        wait_for_url(mgr, url_pattern, timeout_ms).await?;
        return Ok(json!({ "waited": "url", "url": url_pattern }));
    }"#;
    const SCOPED_WAIT_URL: &str = r#"    if let Some(url_pattern) = cmd.get("url").and_then(|v| v.as_str()) {
        if state.active_frame_id.is_some() {
            poll_active_frame(
                mgr,
                state.active_frame_id.as_deref(),
                &session_id,
                &state.iframe_sessions,
                "(root) => root.defaultView.location.href",
                timeout_ms,
                |value| value.as_str().is_some_and(|url| route_url_matches(url_pattern, url)),
            )
            .await?;
        } else {
            wait_for_url(mgr, url_pattern, timeout_ms).await?;
        }
        return Ok(json!({ "waited": "url", "url": url_pattern }));
    }"#;
    const UPSTREAM_WAIT_FUNCTION: &str = r#"    if let Some(fn_str) = cmd.get("function").and_then(|v| v.as_str()) {
        wait_for_function(&mgr.client, &session_id, fn_str, timeout_ms).await?;
        return Ok(json!({ "waited": "function" }));
    }"#;
    const SCOPED_WAIT_FUNCTION: &str = r#"    if let Some(fn_str) = cmd.get("function").and_then(|v| v.as_str()) {
        if state.active_frame_id.is_some() {
            let expression = serde_json::to_string(fn_str).unwrap_or_default();
            let body = format!("(root) => !!root.defaultView.eval({expression})");
            poll_active_frame(
                mgr,
                state.active_frame_id.as_deref(),
                &session_id,
                &state.iframe_sessions,
                &body,
                timeout_ms,
                |value| value.as_bool() == Some(true),
            )
            .await?;
        } else {
            wait_for_function(&mgr.client, &session_id, fn_str, timeout_ms).await?;
        }
        return Ok(json!({ "waited": "function" }));
    }"#;
    const UPSTREAM_WAIT_LOAD: &str = r#"    if let Some(load_state) = cmd.get("loadState").and_then(|v| v.as_str()) {
        let wait_until = WaitUntil::from_str(load_state);
        mgr.wait_for_lifecycle_external(wait_until, &session_id)
            .await?;
        return Ok(json!({ "waited": "load", "state": load_state }));
    }"#;
    const SCOPED_WAIT_LOAD: &str = r#"    if let Some(load_state) = cmd.get("loadState").and_then(|v| v.as_str()) {
        if state.active_frame_id.is_some() {
            let body = match load_state {
                "none" => "(root) => true",
                "domcontentloaded" => "(root) => ['interactive', 'complete'].includes(root.readyState)",
                "load" => "(root) => root.readyState === 'complete'",
                "networkidle" => {
                    return Err("Frame load waits support none, domcontentloaded, and load".to_string())
                }
                _ => return Err(format!("Unknown load state: {}", load_state)),
            };
            poll_active_frame(
                mgr,
                state.active_frame_id.as_deref(),
                &session_id,
                &state.iframe_sessions,
                body,
                timeout_ms,
                |value| value.as_bool() == Some(true),
            )
            .await?;
        } else {
            let wait_until = WaitUntil::from_str(load_state);
            mgr.wait_for_lifecycle_external(wait_until, &session_id).await?;
        }
        return Ok(json!({ "waited": "load", "state": load_state }));
    }"#;
    const EVAL_HELPER_ANCHOR: &str = r#"async fn eval_body_in_active_frame(
    mgr: &BrowserManager,"#;
    const POLL_HELPER: &str = r#"async fn poll_active_frame<F>(
    mgr: &BrowserManager,
    frame_id: Option<&str>,
    top_session: &str,
    iframe_sessions: &HashMap<String, String>,
    body: &str,
    timeout_ms: u64,
    matches: F,
) -> Result<(), String>
where
    F: Fn(&Value) -> bool,
{
    let deadline = tokio::time::Instant::now() + tokio::time::Duration::from_millis(timeout_ms);
    loop {
        let value = eval_body_in_active_frame(mgr, frame_id, top_session, iframe_sessions, body).await?;
        if matches(&value) {
            return Ok(());
        }
        if tokio::time::Instant::now() >= deadline {
            return Err(format!("Wait timed out after {}ms", timeout_ms));
        }
        tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;
    }
}

async fn eval_body_in_active_frame(
    mgr: &BrowserManager,"#;
    const UPSTREAM_SNAPSHOT_ORIGIN: &str = r#"    let url = mgr.get_url().await.unwrap_or_default();

    let refs: serde_json::Map<String, Value> = state"#;
    const SCOPED_SNAPSHOT_ORIGIN: &str = r#"    let url = if state.active_frame_id.is_some() {
        eval_body_in_active_frame(
            mgr,
            state.active_frame_id.as_deref(),
            &session_id,
            &state.iframe_sessions,
            "(root) => root.defaultView.location.href",
        )
        .await?
        .as_str()
        .unwrap_or_default()
        .to_string()
    } else {
        mgr.get_url().await.unwrap_or_default()
    };

    let refs: serde_json::Map<String, Value> = state"#;
    const UPSTREAM_SNAPSHOT_RESULT: &str =
        r#"    Ok(json!({ "snapshot": tree, "origin": url, "refs": refs }))"#;
    const SCOPED_SNAPSHOT_RESULT: &str = r#"    let target_id = mgr.active_target_id().ok();
    Ok(json!({
        "snapshot": tree,
        "origin": url,
        "refs": refs,
        "targetId": target_id,
    }))"#;

    let rewritten = replace_once_named(
        contents,
        "frame-scoped text wait",
        UPSTREAM_WAIT_TEXT,
        SCOPED_WAIT_TEXT,
    );
    let rewritten = replace_once_named(
        rewritten,
        "frame-scoped URL wait",
        UPSTREAM_WAIT_URL,
        SCOPED_WAIT_URL,
    );
    let rewritten = replace_once_named(
        rewritten,
        "frame-scoped function wait",
        UPSTREAM_WAIT_FUNCTION,
        SCOPED_WAIT_FUNCTION,
    );
    let rewritten = replace_once_named(
        rewritten,
        "frame-scoped load wait",
        UPSTREAM_WAIT_LOAD,
        SCOPED_WAIT_LOAD,
    );
    let rewritten = replace_once_named(
        rewritten,
        "frame wait polling helper",
        EVAL_HELPER_ANCHOR,
        POLL_HELPER,
    );
    let rewritten = replace_once_named(
        rewritten,
        "frame snapshot origin",
        UPSTREAM_SNAPSHOT_ORIGIN,
        SCOPED_SNAPSHOT_ORIGIN,
    );
    replace_once_named(
        rewritten,
        "snapshot target identity",
        UPSTREAM_SNAPSHOT_RESULT,
        SCOPED_SNAPSHOT_RESULT,
    )
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

fn rewrite_dashboard_streaming(contents: String) -> String {
    assert!(
        contents.contains("use super::stream::{self, IdleActivity, StreamServer};"),
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

fn rewrite_tab_binding_module(out_dir: &Path, source: &Path) -> PathBuf {
    let destination = out_dir.join("agent_browser_tab_binding.rs");
    let contents = read_rewrite_source(source, "tab binding file");
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
        "pub use dashboard::{\n    is_valid_dashboard_access_token, normalize_dashboard_allowed_origins, run_dashboard_server,\n};\n",
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
    contents: String,
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
    contents.replace(expected, replacement)
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
