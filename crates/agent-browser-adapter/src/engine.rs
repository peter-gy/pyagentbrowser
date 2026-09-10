use serde_json::{json, Value};

use crate::{
    native,
    options::{configure, EngineOptions},
};

pub const INTERNAL_SHUTDOWN_ACTION: &str = "__agent_browser_internal_shutdown";

/// Owns one embedded engine and its ordered command state.
pub struct Engine {
    state: native::actions::DaemonState,
}

pub struct EngineIdentity<'a> {
    pub session: &'a str,
    pub namespace: Option<&'a str>,
    pub engine: &'a str,
}

impl Engine {
    pub fn new(options: &EngineOptions) -> Result<Self, String> {
        Ok(Self {
            state: configure(options)?,
        })
    }

    pub fn identity(&self) -> EngineIdentity<'_> {
        EngineIdentity {
            session: &self.state.session_id,
            namespace: self.state.namespace.as_deref(),
            engine: &self.state.engine,
        }
    }

    pub async fn execute(&mut self, command: &Value) -> Value {
        let mut response = crate::confirmation::dispatch(command, &mut self.state).await;
        if response
            .get("error")
            .and_then(Value::as_str)
            .is_some_and(|error| error.contains("Unknown ref:"))
        {
            response["code"] = json!("unknown_ref");
        }
        response
    }

    /// Expires refs after an interrupted dispatch whose page effects may have completed.
    pub fn invalidate_refs(&mut self) -> u64 {
        self.state.ref_map.clear();
        self.state.ref_map.generation
    }

    pub async fn maintain(&mut self, autosave_interval_ms: u64) {
        let process_exited = self
            .state
            .browser
            .as_mut()
            .map(native::browser::BrowserManager::has_process_exited)
            .unwrap_or(false);
        if process_exited {
            let _ = native::actions::close_current_browser(&mut self.state).await;
        } else if self.state.browser.is_some() {
            match self.state.drain_cdp_events_background().await {
                Ok(()) => {
                    native::actions::maybe_autosave_restore_state(
                        &mut self.state,
                        autosave_interval_ms,
                    )
                    .await
                }
                Err(error) => eprintln!("Failed to apply browser network controls: {error}"),
            }
        }
    }

    pub async fn enable_stream(&mut self, port: Option<u16>) -> Result<(), String> {
        let mut command = json!({"id": "py-dashboard-enable", "action": "stream_enable"});
        if let Some(port) = port {
            command["port"] = json!(port);
        }
        let response = self.execute(&command).await;
        if response
            .get("success")
            .and_then(Value::as_bool)
            .unwrap_or(false)
        {
            Ok(())
        } else {
            Err(response
                .get("error")
                .and_then(Value::as_str)
                .unwrap_or("failed to start dashboard stream")
                .to_string())
        }
    }

    pub async fn disable_stream(&mut self) {
        if self.state.stream_server.is_some() {
            let _ = self
                .execute(&json!({"id": "py-dashboard-disable", "action": "stream_disable"}))
                .await;
        }
    }

    pub async fn shutdown(&mut self) {
        let _ = self
            .execute(&json!({"id": "py-drop-shutdown", "action": INTERNAL_SHUTDOWN_ACTION}))
            .await;
    }
}
