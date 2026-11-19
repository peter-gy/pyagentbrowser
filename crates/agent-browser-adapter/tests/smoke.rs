use std::{
    env,
    ffi::OsString,
    path::Path,
    sync::{Mutex, MutexGuard},
    time::Duration,
};

use agent_browser::{Engine, EngineOptions};
use futures_util::StreamExt;
use serde_json::{json, Value};
use tempfile::{NamedTempFile, TempDir};
use tokio::time::timeout;

fn engine(options: EngineOptions) -> Engine {
    Engine::new(&options).expect("engine options should be valid")
}

async fn run(state: &mut Engine, command: Value) -> Value {
    state.execute(&command).await
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

static ENV_MUTEX: Mutex<()> = Mutex::new(());

struct EnvVarGuard {
    _lock: MutexGuard<'static, ()>,
    key: &'static str,
    previous: Option<OsString>,
}

impl EnvVarGuard {
    fn set_path(key: &'static str, value: &Path) -> Self {
        let lock = ENV_MUTEX
            .lock()
            .expect("environment lock should be available");
        let previous = env::var_os(key);
        env::set_var(key, value);
        Self {
            _lock: lock,
            key,
            previous,
        }
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
    let mut state = engine(EngineOptions {
        confirm_actions: Some(vec!["stream_status".to_string()]),
        ..EngineOptions::default()
    });

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
    let mut state = engine(EngineOptions {
        confirm_actions: Some(vec!["stream_status".to_string()]),
        ..EngineOptions::default()
    });

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
async fn semantic_locator_command_asks_about_the_action_it_performs() {
    let mut state = engine(EngineOptions {
        confirm_actions: Some(vec!["click".to_string(), "gettext".to_string()]),
        ..EngineOptions::default()
    });

    let click = run(
        &mut state,
        json!({"id": "role", "action": "getbyrole", "role": "button"}),
    )
    .await;
    let click_data = assert_success(&click);
    assert_eq!(click_data["confirmation_required"], true);
    assert_eq!(click_data["action"], "click");
    run(
        &mut state,
        json!({"id": "deny", "action": "deny", "confirmation_id": "role"}),
    )
    .await;

    let text = run(
        &mut state,
        json!({"id": "text", "action": "getbytext", "text": "Save", "subaction": "text"}),
    )
    .await;
    let text_data = assert_success(&text);
    assert_eq!(text_data["confirmation_required"], true);
    assert_eq!(text_data["action"], "gettext");
}

#[tokio::test]
async fn policy_denies_semantic_locator_command_by_the_action_it_performs() {
    let policy = NamedTempFile::new().expect("policy file should be created");
    std::fs::write(policy.path(), r#"{"default":"allow","deny":["fill"]}"#).unwrap();
    let mut state = engine(EngineOptions {
        action_policy: Some(policy.path().to_str().unwrap().to_string()),
        ..EngineOptions::default()
    });

    let denied = run(
        &mut state,
        json!({
            "id": "label",
            "action": "getbylabel",
            "label": "Email",
            "subaction": "fill",
            "value": "ada@example.com"
        }),
    )
    .await;
    assert_error_contains(&denied, "Action 'fill' denied by policy");
}

#[tokio::test]
async fn confirmation_replay_reloads_policy_and_denies_newly_blocked_action() {
    let policy = NamedTempFile::new().expect("policy file should be created");
    std::fs::write(policy.path(), r#"{"confirm":["stream_status"]}"#).unwrap();
    let mut state = engine(EngineOptions {
        action_policy: Some(policy.path().to_str().unwrap().to_string()),
        ..EngineOptions::default()
    });

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
    let mut state = engine(EngineOptions {
        action_policy: Some(policy.path().to_str().unwrap().to_string()),
        ..EngineOptions::default()
    });

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
    let mut state = engine(EngineOptions {
        confirm_actions: Some(vec!["tab_new".to_string(), "cookies_set".to_string()]),
        allowed_domains: Some("example.com".to_string()),
        ..EngineOptions::default()
    });

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
    let mut state = engine(EngineOptions {
        confirm_actions: Some(vec!["state_load".to_string()]),
        allowed_domains: Some("example.com".to_string()),
        ..EngineOptions::default()
    });

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
async fn commands_cannot_replace_session_security_settings() {
    let mut state = engine(EngineOptions {
        session: Some("adapter-security-settings".to_string()),
        allowed_domains: Some("Example.com, *.example.org".to_string()),
        confirm_actions: Some(vec!["session_info".to_string()]),
        ..EngineOptions::default()
    });

    for command in [
        json!({"action": "session_info", "settings": {"confirm-actions": ""}}),
        json!({"action": "session_info", "settings": {"action-policy": "/tmp/permissive.json"}}),
        json!({"action": "session_info", "settings": {"allowed-domains": []}}),
        json!({"action": "launch", "allowedDomains": []}),
        json!({"action": "launch", "allowedDomains": "example.com,evil.example"}),
    ] {
        let response = run(&mut state, command.clone()).await;
        assert_error_contains(&response, "a session keeps the allowed domains");
        assert_eq!(
            response["code"], "security_settings",
            "{command}: {response}"
        );
    }

    let gated = run(&mut state, json!({"id": "info", "action": "session_info"})).await;
    assert_eq!(
        assert_success(&gated)["confirmation_required"],
        true,
        "{gated}"
    );
}

#[tokio::test]
async fn engines_in_one_process_keep_their_own_namespace() {
    let socket_dir = TempDir::new().expect("socket dir should be created");
    let _socket_dir_guard = EnvVarGuard::set_path("AGENT_BROWSER_SOCKET_DIR", socket_dir.path());
    let mut engines: Vec<Engine> = [Some("Team A"), None, Some("team-b")]
        .into_iter()
        .map(|namespace| {
            engine(EngineOptions {
                session: Some("shared".to_string()),
                namespace: namespace.map(str::to_string),
                ..EngineOptions::default()
            })
        })
        .collect();

    let mut socket_dirs = Vec::new();
    for state in &mut engines {
        let info = run(state, json!({"id": "info", "action": "session_info"})).await;
        let data = assert_success(&info);
        assert_eq!(data["namespace"], json!(state.identity().namespace));
        socket_dirs.push(data["socketDir"].as_str().unwrap().to_string());
    }

    let base = socket_dir.path();
    assert_eq!(
        socket_dirs,
        [
            base.join("namespaces/team-a/run"),
            base.to_path_buf(),
            base.join("namespaces/team-b/run"),
        ]
        .map(|dir| dir.to_string_lossy().into_owned())
    );
}

#[tokio::test]
async fn new_namespace_holds_the_stream_file_of_its_session() {
    let socket_dir = TempDir::new().expect("socket dir should be created");
    let _socket_dir_guard = EnvVarGuard::set_path("AGENT_BROWSER_SOCKET_DIR", socket_dir.path());
    let mut state = engine(EngineOptions {
        session: Some("streamed".to_string()),
        namespace: Some("Team A".to_string()),
        ..EngineOptions::default()
    });

    let enabled = run(
        &mut state,
        json!({"id": "enable", "action": "stream_enable", "port": 0}),
    )
    .await;
    assert_success(&enabled);

    let stream_file = socket_dir
        .path()
        .join("namespaces/team-a/run/streamed.stream");
    assert!(stream_file.is_file(), "missing {}", stream_file.display());
    assert_success(&run(&mut state, json!({"id": "off", "action": "stream_disable"})).await);
}

#[test]
fn session_name_that_is_not_a_file_name_is_rejected() {
    for session in ["../escape", "a/b", ""] {
        let rejected = Engine::new(&EngineOptions {
            session: Some(session.to_string()),
            ..EngineOptions::default()
        });
        assert!(
            rejected.is_err_and(|error| error.contains("Invalid session name")),
            "session {session:?} was accepted"
        );
    }
}

#[tokio::test]
async fn environment_cdp_target_is_the_default_connection() {
    let _cdp_guard = EnvVarGuard::set_path("AGENT_BROWSER_CDP", Path::new("http://127.0.0.1:9"));
    let mut state = engine(EngineOptions {
        session: Some("adapter-env-cdp".to_string()),
        ..EngineOptions::default()
    });

    let response = run(&mut state, json!({"id": "url", "action": "url"})).await;

    assert_error_contains(&response, "CDP connection failed");
}

#[tokio::test]
async fn stream_result_messages_report_success() {
    let socket_dir = TempDir::new().expect("stream socket dir should be created");
    let _socket_dir_guard = EnvVarGuard::set_path("AGENT_BROWSER_SOCKET_DIR", socket_dir.path());
    let mut state = engine(EngineOptions {
        session: Some("adapter-stream-result".to_string()),
        ..EngineOptions::default()
    });

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
