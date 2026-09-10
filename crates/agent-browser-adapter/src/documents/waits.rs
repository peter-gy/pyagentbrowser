use std::collections::HashMap;

use serde_json::Value;
use tokio::time::{Duration, Instant};

use super::evaluation::evaluate_body;
use crate::native::browser::BrowserManager;

pub(crate) async fn poll_active_frame<F>(
    manager: &BrowserManager,
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
    let deadline = Instant::now() + Duration::from_millis(timeout_ms);
    loop {
        let value = evaluate_body(manager, frame_id, top_session, iframe_sessions, body).await?;
        if matches(&value) {
            return Ok(());
        }
        if Instant::now() >= deadline {
            return Err(format!("Wait timed out after {timeout_ms}ms"));
        }
        tokio::time::sleep(Duration::from_millis(100)).await;
    }
}
