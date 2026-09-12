use super::super::super::{
    patch::{replace_after_named, replace_n_named, replace_once_named},
    source::Source,
};

pub(crate) fn rewrite_frame_commands(contents: Source) -> Source {
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
    rewritten = replace_after_named(
        rewritten,
        "out-of-process frame resolver",
        UPSTREAM_FRAME_RESOLVER_END,
        OOPIF_RESOLVER,
        &["parent-scoped frame tree"],
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
    rewritten = replace_after_named(
        rewritten,
        "named OOPIF fallback",
        "    if let Some(frame_id) = find_frame(frame_tree, name, url) {\n        let label = name.or(url).unwrap_or(\"frame\");\n        state.active_frame_id = Some(frame_id.clone());\n        return Ok(json!({ \"frame\": label, \"frameId\": frame_id }));\n    }",
        "    if let Some(frame_id) = find_frame(search_tree, name, url) {\n        let label = name.or(url).unwrap_or(\"frame\");\n        state.active_frame_id = Some(frame_id.clone());\n        return Ok(json!({ \"frame\": label, \"frameId\": frame_id }));\n    }\n    if let Some(frame_id) = find_oopif(mgr, &state.iframe_sessions, name, url).await? {\n        let label = name.or(url).unwrap_or(\"frame\");\n        state.active_frame_id = Some(frame_id.clone());\n        return Ok(json!({ \"frame\": label, \"frameId\": frame_id }));\n    }",
        &["named frame identity", "retained resolved frame identity"],
    );
    rewritten
}
