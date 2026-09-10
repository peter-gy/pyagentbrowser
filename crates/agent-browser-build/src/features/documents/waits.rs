use super::super::super::{patch::replace_once_named, source::Source};

pub(crate) fn rewrite_scoped_waits(contents: Source) -> Source {
    const UPSTREAM_WAIT_TEXT: &str = r#"    if let Some(text) = cmd.get("text").and_then(|v| v.as_str()) {
        wait_for_text(&mgr.client, &session_id, text, timeout_ms).await?;
        return Ok(json!({ "waited": "text", "text": text }));
    }"#;
    const SCOPED_WAIT_TEXT: &str = r#"    if let Some(text) = cmd.get("text").and_then(|v| v.as_str()) {
        if state.active_frame_id.is_some() {
            let text_json = serde_json::to_string(text).unwrap_or_default();
            let body = format!("(root) => (root.body?.innerText || '').includes({text_json})");
            crate::documents::poll_active_frame(
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
            crate::documents::poll_active_frame(
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
            crate::documents::poll_active_frame(
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
            crate::documents::poll_active_frame(
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
