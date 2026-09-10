use std::{env, sync::Arc, time::Duration};

use agent_browser::Engine;
use tokio::{
    runtime::Runtime,
    sync::{Mutex, oneshot},
    task::JoinHandle,
    time::MissedTickBehavior,
};

const DEFAULT_AUTOSAVE_INTERVAL_MS: u64 = 30_000;
const MAINTENANCE_TICK_MS: u64 = 100;

pub(crate) struct MaintenanceTask {
    shutdown: Option<oneshot::Sender<()>>,
    handle: Option<JoinHandle<()>>,
}

impl MaintenanceTask {
    pub(crate) fn start(
        runtime: &Runtime,
        state: Arc<Mutex<Engine>>,
        autosave_interval_ms: u64,
    ) -> Self {
        let (shutdown, mut shutdown_rx) = oneshot::channel();
        let handle = runtime.spawn(async move {
            let mut tick = tokio::time::interval(Duration::from_millis(MAINTENANCE_TICK_MS));
            tick.set_missed_tick_behavior(MissedTickBehavior::Skip);

            loop {
                tokio::select! {
                    _ = tick.tick() => {
                        let mut state = state.lock().await;
                        state.maintain(autosave_interval_ms).await;
                    }
                    _ = &mut shutdown_rx => break,
                }
            }
        });
        Self {
            shutdown: Some(shutdown),
            handle: Some(handle),
        }
    }

    pub(crate) fn stop(&mut self, runtime: &Runtime) {
        if let Some(shutdown) = self.shutdown.take() {
            let _ = shutdown.send(());
        }
        if let Some(handle) = self.handle.take() {
            let _ = runtime.block_on(handle);
        }
    }
}

pub(crate) fn autosave_interval_ms(configured: Option<u64>) -> u64 {
    let environment = env::var("AGENT_BROWSER_AUTOSAVE_INTERVAL_MS").ok();
    resolve_autosave_interval_ms(configured, environment.as_deref())
}

fn resolve_autosave_interval_ms(configured: Option<u64>, environment: Option<&str>) -> u64 {
    configured
        .or_else(|| environment.and_then(|value| value.parse().ok()))
        .unwrap_or(DEFAULT_AUTOSAVE_INTERVAL_MS)
}

#[cfg(test)]
mod tests {
    use super::{MaintenanceTask, resolve_autosave_interval_ms};
    use agent_browser::{Engine, EngineOptions};
    use std::sync::Arc;
    use tokio::{runtime::Builder, sync::Mutex};

    #[test]
    fn configured_autosave_interval_takes_precedence() {
        assert_eq!(resolve_autosave_interval_ms(Some(0), Some("1500")), 0);
    }

    #[test]
    fn autosave_interval_uses_a_valid_environment_value() {
        assert_eq!(resolve_autosave_interval_ms(None, Some("1500")), 1500);
    }

    #[test]
    fn autosave_interval_uses_the_default_for_missing_or_invalid_environment() {
        assert_eq!(resolve_autosave_interval_ms(None, None), 30_000);
        assert_eq!(resolve_autosave_interval_ms(None, Some("invalid")), 30_000);
    }

    #[test]
    fn maintenance_stop_waits_for_the_task_to_release_browser_state() {
        let runtime = Builder::new_current_thread()
            .enable_all()
            .build()
            .expect("test runtime should start");
        let state = Arc::new(Mutex::new(
            Engine::new(&EngineOptions::default()).expect("engine should start"),
        ));
        let weak_state = Arc::downgrade(&state);
        let mut maintenance = MaintenanceTask::start(&runtime, Arc::clone(&state), 0);
        drop(state);

        assert!(weak_state.upgrade().is_some());
        maintenance.stop(&runtime);
        assert!(weak_state.upgrade().is_none());

        maintenance.stop(&runtime);
    }
}
