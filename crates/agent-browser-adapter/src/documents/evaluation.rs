use crate::native::browser::BrowserManager;
use crate::native::cdp::client::CdpClient;
use serde_json::{json, Value};
use std::collections::HashMap;

pub(crate) async fn evaluate_body(
    manager: &BrowserManager,
    frame: Option<&str>,
    top_session: &str,
    iframe_sessions: &HashMap<String, String>,
    body: &str,
) -> Result<Value, String> {
    let expression = format!("({body})(document)");
    match frame {
        Some(frame) => {
            evaluate(
                &manager.client,
                top_session,
                iframe_sessions,
                frame,
                &expression,
            )
            .await
        }
        None => manager.evaluate(&expression, None).await,
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
        if client.documents.context(session, frame).is_some() {
            return Ok(session);
        }
    }
    for session in sessions {
        // A detached session for another iframe must not hide this frame's owner.
        if client
            .send_command_no_params("Runtime.enable", Some(session))
            .await
            .is_ok()
            && client.documents.context(session, frame).is_some()
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
        .documents
        .context(session, frame)
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
