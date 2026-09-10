use super::super::super::{
    patch::{replace_n_named, replace_once_named},
    source::{read_rewrite_source, Source},
};
use std::{
    fs,
    path::{Path, PathBuf},
};

pub(crate) fn rewrite_element_module(out_dir: &Path, source: &Path) -> PathBuf {
    let contents = read_rewrite_source(source, "element file").feature("documents");
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

pub(crate) fn rewrite_element_scope(contents: Source) -> Source {
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
        "client.documents.frame()",
        2,
    );
    let contents = replace_n_named(
        contents,
        "element owning session",
        "    if let Some(ref_id) = parse_ref(selector_or_ref) {",
        r#"    let frame = parse_ref(selector_or_ref)
        .and_then(|reference| ref_map.get(&reference))
        .and_then(|entry| entry.frame_id.clone())
        .or_else(|| client.documents.frame());
    let session_id = match frame.as_deref() {
        Some(frame) => crate::documents::session_for_frame(client, session_id, iframe_sessions, frame).await?,
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
    let (_, result) = crate::documents::evaluate_remote(
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
        "        if client.documents.strict_refs() {\n            return Err(format!(\"stale_ref: Captured node for {} is detached\", selector_or_ref));\n        }\n\n        // Fallback: re-query the accessibility tree to find a fresh node by role/name",
        2,
    );
    let contents = replace_once_named(
        contents,
        "typed ref object connectivity",
        r#"                if let Some(object_id) = r.object.object_id {
                    return Ok((object_id, effective_session_id.to_string()));
                }"#,
        r#"                if let Some(object_id) = r.object.object_id {
                    if client.documents.strict_refs() {
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
