use std::{env, ffi::OsString, path::Path, sync::Arc, time::Duration};

use agent_browser::native::{
    actions::{execute_command, DaemonState},
    network::DomainFilter,
    policy::{ActionPolicy, ConfirmActions},
};
use futures_util::StreamExt;
use serde_json::{json, Value};
use tempfile::{NamedTempFile, TempDir};
use tokio::{sync::RwLock, time::timeout};

fn confirm_actions(actions: &[&str]) -> ConfirmActions {
    ConfirmActions {
        categories: actions.iter().map(|action| (*action).to_string()).collect(),
    }
}

async fn run(state: &mut DaemonState, command: Value) -> Value {
    execute_command(&command, state).await
}

fn assert_success(response: &Value) -> &Value {
    assert_eq!(response["success"], true, "{response}");
    &response["data"]
}

fn assert_error_contains(response: &Value, expected: &str) {
    assert_eq!(response["success"], false, "{response}");
    let error = response["error"]
        .as_str()
        .expect("error response should include a string error");
    assert!(
        error.contains(expected),
        "expected error to contain {expected:?}, got {error:?}"
    );
}

#[test]
fn accessibility_audit_engine_is_embedded() {
    let source = agent_browser::native::a11y::AXE_JS;

    assert!(source.len() > 100_000);
    assert!(source.contains("axe.version="));
}

struct EnvVarGuard {
    key: &'static str,
    previous: Option<OsString>,
}

impl EnvVarGuard {
    fn set_path(key: &'static str, value: &Path) -> Self {
        let previous = env::var_os(key);
        env::set_var(key, value);
        Self { key, previous }
    }
}

impl Drop for EnvVarGuard {
    fn drop(&mut self) {
        if let Some(previous) = self.previous.take() {
            env::set_var(self.key, previous);
        } else {
            env::remove_var(self.key);
        }
    }
}

#[tokio::test]
async fn confirm_requires_matching_confirmation_id_without_consuming_pending_action() {
    let mut state = DaemonState::new();
    state.confirm_actions = Some(confirm_actions(&["stream_status"]));

    let pending = run(
        &mut state,
        json!({"id": "need-confirm", "action": "stream_status"}),
    )
    .await;
    let pending_data = assert_success(&pending);
    assert_eq!(pending_data["confirmation_required"], true);
    assert_eq!(pending_data["confirmation_id"], "need-confirm");

    let wrong_id = run(
        &mut state,
        json!({"id": "wrong-confirm", "action": "confirm", "confirmation_id": "other"}),
    )
    .await;
    assert_error_contains(&wrong_id, "confirmation_id does not match");

    let confirmed = run(
        &mut state,
        json!({"id": "confirm", "action": "confirm", "confirmation_id": "need-confirm"}),
    )
    .await;
    let confirmed_data = assert_success(&confirmed);
    assert_eq!(confirmed_data["action"], "stream_status");
    assert_eq!(confirmed_data["result"]["success"], true);
}

#[tokio::test]
async fn deny_requires_present_matching_confirmation_id() {
    let mut state = DaemonState::new();
    state.confirm_actions = Some(confirm_actions(&["stream_status"]));

    assert_success(
        &run(
            &mut state,
            json!({"id": "pending", "action": "stream_status"}),
        )
        .await,
    );

    let missing = run(&mut state, json!({"id": "missing", "action": "deny"})).await;
    assert_error_contains(&missing, "Missing confirmation_id");

    let wrong = run(
        &mut state,
        json!({"id": "wrong", "action": "deny", "confirmation_id": "other"}),
    )
    .await;
    assert_error_contains(&wrong, "confirmation_id does not match");

    let denied = run(
        &mut state,
        json!({"id": "deny", "action": "deny", "confirmation_id": "pending"}),
    )
    .await;
    assert_eq!(assert_success(&denied)["denied"], true);
}

#[tokio::test]
async fn confirmation_replay_reloads_policy_and_denies_newly_blocked_action() {
    let policy = NamedTempFile::new().expect("policy file should be created");
    std::fs::write(policy.path(), r#"{"confirm":["stream_status"]}"#).unwrap();
    let mut state = DaemonState::new();
    state.policy = Some(ActionPolicy::load(policy.path().to_str().unwrap()).unwrap());

    assert_success(
        &run(
            &mut state,
            json!({"id": "pending", "action": "stream_status"}),
        )
        .await,
    );
    std::fs::write(policy.path(), r#"{"deny":["stream_status"]}"#).unwrap();

    let denied = run(
        &mut state,
        json!({"id": "confirm", "action": "confirm", "confirmation_id": "pending"}),
    )
    .await;
    assert_error_contains(&denied, "denied by policy during confirmation");
}

#[tokio::test]
async fn confirmation_replay_fails_closed_when_policy_file_is_invalid_or_deleted() {
    let policy = NamedTempFile::new().expect("policy file should be created");
    std::fs::write(policy.path(), r#"{"confirm":["stream_status"]}"#).unwrap();
    let mut state = DaemonState::new();
    state.policy = Some(ActionPolicy::load(policy.path().to_str().unwrap()).unwrap());

    assert_success(
        &run(
            &mut state,
            json!({"id": "invalid", "action": "stream_status"}),
        )
        .await,
    );
    std::fs::write(policy.path(), "{not-json").unwrap();
    let invalid = run(
        &mut state,
        json!({"id": "confirm-invalid", "action": "confirm", "confirmation_id": "invalid"}),
    )
    .await;
    assert_error_contains(&invalid, "Invalid policy JSON");

    std::fs::write(policy.path(), r#"{"confirm":["stream_status"]}"#).unwrap();
    assert_success(
        &run(
            &mut state,
            json!({"id": "deleted", "action": "stream_status"}),
        )
        .await,
    );
    std::fs::remove_file(policy.path()).unwrap();
    let deleted = run(
        &mut state,
        json!({"id": "confirm-deleted", "action": "confirm", "confirmation_id": "deleted"}),
    )
    .await;
    assert_error_contains(&deleted, "Failed to read policy file");
}

#[tokio::test]
async fn confirmation_replay_rechecks_top_level_url_and_cookie_allowlists() {
    let mut state = DaemonState::new();
    state.confirm_actions = Some(confirm_actions(&["tab_new", "cookies_set"]));
    state.domain_filter = Arc::new(RwLock::new(Some(DomainFilter::new("example.com"))));

    assert_success(
        &run(
            &mut state,
            json!({"id": "tab", "action": "tab_new", "url": "https://evil.example"}),
        )
        .await,
    );
    let tab_denied = run(
        &mut state,
        json!({"id": "confirm-tab", "action": "confirm", "confirmation_id": "tab"}),
    )
    .await;
    assert_error_contains(&tab_denied, "denied by allowed domains during confirmation");

    assert_success(
        &run(
            &mut state,
            json!({
                "id": "cookie",
                "action": "cookies_set",
                "name": "session",
                "value": "abc",
                "domain": "evil.example"
            }),
        )
        .await,
    );
    let cookie_denied = run(
        &mut state,
        json!({"id": "confirm-cookie", "action": "confirm", "confirmation_id": "cookie"}),
    )
    .await;
    assert_error_contains(&cookie_denied, "Cookie domain 'evil.example'");
}

#[tokio::test]
async fn confirmation_replay_fails_closed_for_unvalidated_allowlist_targets() {
    let state_file = NamedTempFile::new().expect("state file should be created");
    std::fs::write(state_file.path(), r#"{"cookies":[],"origins":[]}"#).unwrap();
    let mut state = DaemonState::new();
    state.confirm_actions = Some(confirm_actions(&["state_load"]));
    state.domain_filter = Arc::new(RwLock::new(Some(DomainFilter::new("example.com"))));

    assert_success(
        &run(
            &mut state,
            json!({
                "id": "state-load",
                "action": "state_load",
                "path": state_file.path().to_str().unwrap()
            }),
        )
        .await,
    );
    let denied = run(
        &mut state,
        json!({"id": "confirm-state", "action": "confirm", "confirmation_id": "state-load"}),
    )
    .await;
    assert_error_contains(
        &denied,
        "target cannot be validated against allowed domains",
    );
}

#[tokio::test]
async fn stream_result_messages_report_success() {
    let socket_dir = TempDir::new().expect("stream socket dir should be created");
    let _socket_dir_guard = EnvVarGuard::set_path("AGENT_BROWSER_SOCKET_DIR", socket_dir.path());
    let mut state = DaemonState::new();
    state.session_id = "adapter-stream-result".to_string();

    let enabled = run(
        &mut state,
        json!({"id": "enable", "action": "stream_enable", "port": 0}),
    )
    .await;
    let port = assert_success(&enabled)["port"]
        .as_u64()
        .expect("stream_enable should report a port");

    let (mut websocket, _) = tokio_tungstenite::connect_async(format!("ws://127.0.0.1:{port}"))
        .await
        .expect("stream websocket should accept connections");

    let status_message = timeout(Duration::from_secs(10), websocket.next())
        .await
        .expect("timed out waiting for stream status")
        .expect("stream should remain open")
        .expect("stream status should be readable");
    assert!(status_message.is_text(), "{status_message:?}");
    let status_event: Value = serde_json::from_str(status_message.to_text().unwrap()).unwrap();
    assert_eq!(status_event["type"], "status", "{status_event}");

    assert_success(
        &run(
            &mut state,
            json!({"id": "status", "action": "stream_status"}),
        )
        .await,
    );

    let result = loop {
        let message = timeout(Duration::from_secs(10), websocket.next())
            .await
            .expect("timed out waiting for stream result")
            .expect("stream should remain open")
            .expect("stream message should be readable");
        if !message.is_text() {
            continue;
        }
        let event: Value = serde_json::from_str(message.to_text().unwrap()).unwrap();
        if event["type"] == "result" && event["action"] == "stream_status" {
            break event;
        }
    };

    assert_eq!(result["success"], true);
    assert_success(
        &run(
            &mut state,
            json!({"id": "disable", "action": "stream_disable"}),
        )
        .await,
    );
}
