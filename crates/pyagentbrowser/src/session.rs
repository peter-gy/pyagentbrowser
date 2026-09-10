use std::sync::{Arc, Mutex as StdMutex};
use std::time::Duration;

use agent_browser::{Engine, INTERNAL_SHUTDOWN_ACTION};
use serde_json::{Value, json};
use tokio::{
    runtime::{Builder, Runtime},
    sync::Mutex,
};

use crate::{
    cancellation::CancellationState,
    dashboard::{DashboardConfig, DashboardSidecar, start_dashboard},
    maintenance::MaintenanceTask,
};

pub(crate) struct Session {
    state: Arc<Mutex<Engine>>,
    runtime: Runtime,
    dashboard: StdMutex<Option<DashboardSidecar>>,
    maintenance: MaintenanceTask,
}

impl Session {
    pub(crate) fn new(
        mut engine: Engine,
        autosave_interval_ms: u64,
        dashboard: Option<(DashboardConfig, String)>,
    ) -> Result<Self, String> {
        let runtime = Builder::new_multi_thread()
            .enable_all()
            .thread_name("pyagentbrowser")
            .build()
            .map_err(|error| format!("failed to create tokio runtime: {error}"))?;
        let dashboard = match dashboard {
            Some((config, executable)) => {
                Some(start_dashboard(&executable, &runtime, &mut engine, config)?)
            }
            None => None,
        };
        let state = Arc::new(Mutex::new(engine));
        let maintenance =
            MaintenanceTask::start(&runtime, Arc::clone(&state), autosave_interval_ms);
        Ok(Self {
            state,
            runtime,
            dashboard: StdMutex::new(dashboard),
            maintenance,
        })
    }

    pub(crate) fn execute(
        &self,
        command: &Value,
        cancellation: Option<Arc<CancellationState>>,
    ) -> Result<Value, String> {
        let response = self.runtime.block_on(async {
                let interruption = async {
                    tokio::select! {
                        biased;
                        () = async {
                            match cancellation.as_ref() {
                                Some(token) => token.cancelled().await,
                                None => std::future::pending().await,
                            }
                        } => "execution_cancelled",
                        () = async {
                            match command.get("_timeoutMs").and_then(Value::as_u64) {
                                Some(timeout_ms) => tokio::time::sleep(Duration::from_millis(timeout_ms)).await,
                                None => std::future::pending().await,
                            }
                        } => "execution_timeout",
                    }
                };
                tokio::pin!(interruption);
                let interrupted = |code: &str| json!({
                    "id": command.get("id"),
                    "success": false,
                    "code": code,
                    "error": if code == "execution_cancelled" {
                        "Browser dispatch cancelled. Page effects already sent may have completed. Inspect current state before retrying."
                    } else {
                        "Agent host deadline reached. Browser dispatch stopped, but page effects already sent may have completed. Inspect current state before retrying."
                    }
                });
                let mut state = tokio::select! {
                    biased;
                    code = &mut interruption => return interrupted(code),
                    state = self.state.lock() => state,
                };
                tokio::select! {
                    biased;
                    code = &mut interruption => {
                        let generation = state.invalidate_refs();
                        let mut response = interrupted(code);
                        response["refGeneration"] = json!(generation);
                        response
                    }
                    response = state.execute(command) => response,
                }
            });
        let should_shutdown_dashboard = matches!(
            command.get("action").and_then(Value::as_str),
            Some("close" | INTERNAL_SHUTDOWN_ACTION | "stream_disable")
        ) && response
            .get("success")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        if should_shutdown_dashboard {
            self.shutdown_dashboard()?;
        }
        Ok(response)
    }
}

impl Session {
    fn shutdown_dashboard(&self) -> Result<(), String> {
        let sidecar = self
            .dashboard
            .lock()
            .map_err(|_| "dashboard sidecar lock is poisoned".to_string())?
            .take();
        let Some(mut sidecar) = sidecar else {
            return Ok(());
        };

        self.runtime.block_on(async {
            let mut state = self.state.lock().await;
            state.disable_stream().await;
        });
        sidecar.cleanup();
        Ok(())
    }

    fn shutdown_native(&self) {
        self.runtime.block_on(async {
            let mut state = self.state.lock().await;
            state.shutdown().await;
        });
    }
}

impl Drop for Session {
    fn drop(&mut self) {
        self.maintenance.stop(&self.runtime);
        let _ = self.shutdown_dashboard();
        self.shutdown_native();
    }
}
