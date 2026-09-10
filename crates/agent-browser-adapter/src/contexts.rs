use std::collections::HashMap;

use serde_json::{json, Value};

use crate::native::cdp::client::CdpClient;
use crate::native::cdp::types::CdpEvent;

#[derive(Clone)]
pub(crate) struct DocumentContext {
    pub id: i64,
    pub unique_id: Option<String>,
}

#[derive(Default)]
pub(crate) struct Contexts {
    documents: HashMap<(String, String), DocumentContext>,
}

impl Contexts {
    pub fn document(&self, session: &str, frame: &str) -> Option<DocumentContext> {
        self.documents
            .get(&(session.to_owned(), frame.to_owned()))
            .cloned()
    }

    pub fn apply(&mut self, event: &CdpEvent) {
        let session = event.session_id.as_deref().unwrap_or("");
        match event.method.as_str() {
            "Runtime.executionContextCreated" => {
                let context = &event.params["context"];
                let aux = &context["auxData"];
                if aux["isDefault"].as_bool() != Some(true) {
                    return;
                }
                if let (Some(frame), Some(id)) = (aux["frameId"].as_str(), context["id"].as_i64()) {
                    self.documents.insert(
                        (session.to_owned(), frame.to_owned()),
                        DocumentContext {
                            id,
                            unique_id: context["uniqueId"].as_str().map(str::to_owned),
                        },
                    );
                }
            }
            "Runtime.executionContextDestroyed" => {
                let id = event.params["executionContextId"].as_i64();
                self.documents
                    .retain(|(owner, _), context| owner != session || Some(context.id) != id);
            }
            "Runtime.executionContextsCleared" => {
                self.documents.retain(|(owner, _), _| owner != session);
            }
            "Target.detachedFromTarget" => {
                if let Some(detached) = event.params.get("sessionId").and_then(Value::as_str) {
                    self.documents.retain(|(owner, _), _| owner != detached);
                }
            }
            _ => {}
        }
    }
}

pub(crate) async fn evaluate(
    client: &CdpClient,
    top_session: &str,
    iframe_sessions: &HashMap<String, String>,
    frame: &str,
    expression: &str,
) -> Result<Value, String> {
    let (_, response) = evaluate_remote(
        client,
        top_session,
        iframe_sessions,
        frame,
        expression,
        true,
    )
    .await?;
    Ok(response
        .pointer("/result/value")
        .cloned()
        .unwrap_or(Value::Null))
}

pub(crate) async fn session_for_frame<'a>(
    client: &CdpClient,
    top_session: &'a str,
    iframe_sessions: &'a HashMap<String, String>,
    frame: &str,
) -> Result<&'a str, String> {
    let mut sessions = vec![top_session];
    sessions.extend(iframe_sessions.values().map(String::as_str));
    for &session in &sessions {
        if client.document_context(session, frame).is_some() {
            return Ok(session);
        }
    }
    for session in sessions {
        // A detached session for another iframe must not hide this frame's owner.
        if client
            .send_command_no_params("Runtime.enable", Some(session))
            .await
            .is_ok()
            && client.document_context(session, frame).is_some()
        {
            return Ok(session);
        }
    }
    Err(format!("Frame execution context detached: {frame}"))
}

pub(crate) async fn evaluate_remote(
    client: &CdpClient,
    top_session: &str,
    iframe_sessions: &HashMap<String, String>,
    frame: &str,
    expression: &str,
    by_value: bool,
) -> Result<(String, Value), String> {
    let session = session_for_frame(client, top_session, iframe_sessions, frame).await?;
    let context = client
        .document_context(session, frame)
        .ok_or_else(|| format!("Frame execution context detached: {frame}"))?;
    let mut params = json!({
        "expression": expression,
        "returnByValue": by_value,
        "awaitPromise": true,
    });
    if let Some(id) = context.unique_id {
        params["uniqueContextId"] = json!(id);
    } else {
        params["contextId"] = json!(context.id);
    }
    let response = client
        .send_command("Runtime.evaluate", Some(params), Some(session))
        .await?;
    if let Some(details) = response.get("exceptionDetails") {
        let message = details
            .pointer("/exception/description")
            .or_else(|| details.get("text"))
            .and_then(Value::as_str)
            .unwrap_or("JavaScript evaluation failed");
        return Err(format!("Evaluation error: {message}"));
    }
    Ok((session.to_owned(), response))
}

pub(crate) struct Rect {
    pub x: f64,
    pub y: f64,
    pub width: f64,
    pub height: f64,
}

const FRAME_OWNER_GEOMETRY: &str = r#"function() {
    const view = this.ownerDocument.defaultView;
    const r = this.getBoundingClientRect();
    const sx = this.offsetWidth ? r.width / this.offsetWidth : 1;
    const sy = this.offsetHeight ? r.height / this.offsetHeight : 1;
    let left = 0, top = 0, right = view.innerWidth, bottom = view.innerHeight;
    for (let node = this; node; node = node.parentElement || node.getRootNode().host) {
        const style = view.getComputedStyle(node);
        if ((style.rotate !== 'none' && !/^0(?:deg|rad|turn)?$/.test(style.rotate))
            || style.perspective !== 'none'
            || (style.scale !== 'none' && style.scale.split(/\s+/).some(value => Number(value) <= 0))) {
            throw new Error('Frame screenshots require positive axis-aligned transforms');
        }
        if (style.transform !== 'none') {
            const matrix = new view.DOMMatrixReadOnly(style.transform);
            if (!matrix.is2D || Math.abs(matrix.b) > 1e-8 || Math.abs(matrix.c) > 1e-8
                || matrix.a <= 0 || matrix.d <= 0) {
                throw new Error('Frame screenshots require positive axis-aligned transforms');
            }
        }
        if (node === this) continue;
        const bounds = node.getBoundingClientRect();
        const scaleX = node.offsetWidth ? bounds.width / node.offsetWidth : 1;
        const scaleY = node.offsetHeight ? bounds.height / node.offsetHeight : 1;
        if (/^(hidden|clip|scroll|auto)$/.test(style.overflowX)) {
            left = Math.max(left, bounds.x + node.clientLeft * scaleX);
            right = Math.min(right, bounds.x + (node.clientLeft + node.clientWidth) * scaleX);
        }
        if (/^(hidden|clip|scroll|auto)$/.test(style.overflowY)) {
            top = Math.max(top, bounds.y + node.clientTop * scaleY);
            bottom = Math.min(bottom, bounds.y + (node.clientTop + node.clientHeight) * scaleY);
        }
    }
    return {x: r.x + this.clientLeft * sx, y: r.y + this.clientTop * sy,
        width: this.clientWidth * sx, height: this.clientHeight * sy, sx, sy,
        left, top, right, bottom};
}"#;

pub(crate) async fn frame_rect(
    client: &CdpClient,
    top_session: &str,
    iframe_sessions: &HashMap<String, String>,
    frame: &str,
) -> Result<Rect, String> {
    fn collect(tree: &Value, parent: Option<&str>, parents: &mut HashMap<String, String>) {
        let Some(id) = tree.pointer("/frame/id").and_then(Value::as_str) else {
            return;
        };
        if let Some(parent) =
            parent.or_else(|| tree.pointer("/frame/parentId").and_then(Value::as_str))
        {
            parents.insert(id.to_owned(), parent.to_owned());
        }
        if let Some(children) = tree.get("childFrames").and_then(Value::as_array) {
            for child in children {
                collect(child, Some(id), parents);
            }
        }
    }
    let tree = client
        .send_command_no_params("Page.getFrameTree", Some(top_session))
        .await?;
    let root = tree
        .pointer("/frameTree/frame/id")
        .and_then(Value::as_str)
        .ok_or("Page frame tree has no root")?;
    let mut parents = HashMap::new();
    collect(&tree["frameTree"], None, &mut parents);
    for session in iframe_sessions.values() {
        if let Ok(tree) = client
            .send_command_no_params("Page.getFrameTree", Some(session))
            .await
        {
            collect(&tree["frameTree"], None, &mut parents);
        }
    }
    let mut current = frame.to_owned();
    let viewport = evaluate(
        client,
        top_session,
        iframe_sessions,
        &current,
        "({width: innerWidth, height: innerHeight})",
    )
    .await?;
    let mut rect = Rect {
        x: 0.0,
        y: 0.0,
        width: number(&viewport, "width")?,
        height: number(&viewport, "height")?,
    };
    let mut seen = std::collections::HashSet::new();
    while current != root {
        if !seen.insert(current.clone()) {
            return Err("Frame ancestor cycle".to_owned());
        }
        let parent = parents
            .get(&current)
            .ok_or_else(|| format!("Frame parent detached: {current}"))?;
        let session = session_for_frame(client, top_session, iframe_sessions, parent).await?;
        let owner =
            crate::native::element::frame_owner_object_id(client, session, &current).await?;
        let response = client
            .send_command(
                "Runtime.callFunctionOn",
                Some(json!({
                    "objectId": owner,
                    "functionDeclaration": FRAME_OWNER_GEOMETRY,
                    "returnByValue": true,
                })),
                Some(session),
            )
            .await?;
        if let Some(exception) = response.get("exceptionDetails") {
            return Err(exception
                .pointer("/exception/description")
                .and_then(Value::as_str)
                .unwrap_or("Frame geometry evaluation failed")
                .to_owned());
        }
        let value = &response["result"]["value"];
        let x = number(value, "x")?;
        let y = number(value, "y")?;
        let width = number(value, "width")?;
        let height = number(value, "height")?;
        let sx = number(value, "sx")?;
        let sy = number(value, "sy")?;
        let left = (x + rect.x * sx).max(x).max(number(value, "left")?);
        let top = (y + rect.y * sy).max(y).max(number(value, "top")?);
        let right = (x + (rect.x + rect.width) * sx)
            .min(x + width)
            .min(number(value, "right")?);
        let bottom = (y + (rect.y + rect.height) * sy)
            .min(y + height)
            .min(number(value, "bottom")?);
        rect = Rect {
            x: left,
            y: top,
            width: (right - left).max(0.0),
            height: (bottom - top).max(0.0),
        };
        if rect.width <= 0.0 || rect.height <= 0.0 {
            return Err(format!("Frame is outside the visible viewport: {frame}"));
        }
        current = parent.clone();
    }
    // Page.captureScreenshot clips use page coordinates, while owners use viewport coordinates.
    let scroll = evaluate(
        client,
        top_session,
        iframe_sessions,
        root,
        "({x: scrollX, y: scrollY})",
    )
    .await?;
    rect.x += number(&scroll, "x")?;
    rect.y += number(&scroll, "y")?;
    Ok(rect)
}

fn number(value: &Value, key: &str) -> Result<f64, String> {
    value
        .get(key)
        .and_then(Value::as_f64)
        .filter(|value| value.is_finite())
        .ok_or_else(|| format!("Frame geometry missing {key}"))
}
