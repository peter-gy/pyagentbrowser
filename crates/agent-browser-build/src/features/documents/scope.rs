use super::super::super::{patch::replace_once_named, source::Source};

pub(crate) fn rewrite_scoped_page_commands(contents: Source) -> Source {
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
        manager.client.documents.set_frame(state.active_frame_id.as_deref());
        manager.client.documents.set_strict_refs(cmd.get("_refGeneration").is_some());
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
    const UPSTREAM_BODY_EVALUATION: &str = r###"async fn eval_body_in_active_frame(
    mgr: &BrowserManager,
    frame_id: Option<&str>,
    top_session: &str,
    iframe_sessions: &HashMap<String, String>,
    body: &str,
) -> Result<Value, String> {
    match frame_id {
        Some(fid) if !iframe_sessions.contains_key(fid) => {
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
        }
        _ => {
            let session = frame_id
                .and_then(|f| iframe_sessions.get(f))
                .map(|s| s.as_str())
                .unwrap_or(top_session);
            let res: super::cdp::types::EvaluateResult = mgr
                .client
                .send_command_typed(
                    "Runtime.evaluate",
                    &super::cdp::types::EvaluateParams {
                        expression: format!("({body})(document)"),
                        return_by_value: Some(true),
                        await_promise: Some(false),
                    },
                    Some(session),
                )
                .await?;
            Ok(res.result.value.unwrap_or(Value::Null))
        }
    }
}"###;
    const UPSTREAM_EVALUATE: &str = r#"    let result = mgr.evaluate(script, None).await?;
    let url = mgr.get_url().await.unwrap_or_default();
    Ok(json!({ "result": result, "origin": url }))"#;
    const SCOPED_EVALUATE: &str = r#"    let target_id = mgr.active_target_id().ok();
    let (result, origin) = if let Some(frame) = state.active_frame_id.as_deref() {
        let session = mgr.active_session_id()?;
        let result = crate::documents::evaluate(&mgr.client, session, &state.iframe_sessions, frame, script).await?;
        let origin = crate::documents::evaluate(&mgr.client, session, &state.iframe_sessions, frame, "location.href").await?;
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
        Some(frame) => crate::documents::session_for_frame(&mgr.client, &session_id, &state.iframe_sessions, frame).await?,
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
    replace_once_named(
        rewritten,
        "document body evaluation",
        UPSTREAM_BODY_EVALUATION,
        "use crate::documents::evaluate_body as eval_body_in_active_frame;",
    )
}
