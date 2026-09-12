use std::{
    env, fs,
    path::{Path, PathBuf},
    process::Child,
};

use agent_browser::Engine;
use serde::Deserialize;
use serde_json::json;
use tokio::runtime::Runtime;

mod control;
mod watchdog;

use control::{ControlBridge, start_control_bridge};
use watchdog::spawn_dashboard_watchdog;

#[derive(Deserialize)]
#[serde(untagged)]
pub(crate) enum DashboardOption {
    Enabled(bool),
    Config(DashboardConfig),
}

#[derive(Default, Deserialize)]
pub(crate) struct DashboardConfig {
    enabled: Option<bool>,
    port: Option<u16>,
    cli_version: Option<String>,
}

impl DashboardOption {
    pub(crate) fn into_config(self) -> Option<DashboardConfig> {
        match self {
            Self::Enabled(true) => Some(DashboardConfig {
                enabled: Some(true),
                port: None,
                cli_version: None,
            }),
            Self::Enabled(false) => None,
            Self::Config(config) if config.enabled.unwrap_or(true) => Some(config),
            Self::Config(_) => None,
        }
    }
}

pub(crate) fn start_dashboard(
    executable: &str,
    runtime: &Runtime,
    state: &mut Engine,
    config: DashboardConfig,
) -> Result<DashboardSidecar, String> {
    let identity = state.identity();
    let socket_dir = agent_browser::socket_dir_for_namespace(identity.namespace);
    fs::create_dir_all(&socket_dir).map_err(|err| {
        format!(
            "failed to create agent-browser socket directory '{}': {err}",
            socket_dir.display()
        )
    })?;

    let mut sidecar = DashboardSidecar::new(identity.session.to_string(), socket_dir.clone());
    sidecar.control = Some(start_control_bridge(&socket_dir, identity.session)?);
    write_dashboard_text_file(
        &socket_dir,
        identity.session,
        "version",
        &dashboard_sidecar_version(config.cli_version.as_deref()),
    )?;
    let sentinel = spawn_dashboard_watchdog(executable, &socket_dir, identity.session)?;
    let sentinel_pid = sentinel.id();
    sidecar.sentinel = Some(sentinel);
    write_dashboard_text_file(
        &socket_dir,
        identity.session,
        "pid",
        &sentinel_pid.to_string(),
    )?;
    write_dashboard_text_file(&socket_dir, identity.session, "engine", identity.engine)?;
    write_dashboard_text_file(
        &socket_dir,
        identity.session,
        "metadata",
        &json!({
            "owner": "pyagentbrowser",
            "control": "observable-only",
            "pid": sentinel_pid,
        })
        .to_string(),
    )?;

    runtime.block_on(state.enable_stream(config.port))?;

    Ok(sidecar)
}

pub(crate) fn validate_dashboard_session_id(session_id: &str) -> Result<(), String> {
    if session_id.is_empty() || session_id.len() > 64 {
        return Err(String::from(
            "dashboard sessions require a 1-64 character session name",
        ));
    }
    if session_id.contains(['/', '\\', '\0']) {
        return Err(String::from(
            "dashboard session names must not contain path separators",
        ));
    }
    Ok(())
}

pub(super) fn write_dashboard_text_file(
    dir: &Path,
    session_id: &str,
    extension: &str,
    content: &str,
) -> Result<(), String> {
    let path = dir.join(format!("{session_id}.{extension}"));
    fs::write(&path, content).map_err(|err| {
        format!(
            "failed to write dashboard sidecar '{}': {err}",
            path.display()
        )
    })
}

fn dashboard_sidecar_version(configured: Option<&str>) -> String {
    configured
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned)
        .or_else(|| {
            env::var("AGENT_BROWSER_DASHBOARD_CLI_VERSION")
                .ok()
                .map(|value| value.trim().to_string())
                .filter(|value| !value.is_empty())
        })
        .unwrap_or_else(|| agent_browser::VERSION.to_string())
}

pub(crate) struct DashboardSidecar {
    session_id: String,
    socket_dir: PathBuf,
    sentinel: Option<Child>,
    control: Option<ControlBridge>,
    cleaned: bool,
}

impl DashboardSidecar {
    fn new(session_id: String, socket_dir: PathBuf) -> Self {
        Self {
            session_id,
            socket_dir,
            sentinel: None,
            control: None,
            cleaned: false,
        }
    }

    pub(crate) fn cleanup(&mut self) {
        if self.cleaned {
            return;
        }
        self.cleaned = true;
        drop(self.control.take());
        if let Some(mut sentinel) = self.sentinel.take() {
            let _ = sentinel.kill();
            let _ = sentinel.wait();
        }
        cleanup_dashboard_sidecar_files(&self.socket_dir, &self.session_id);
    }
}

impl Drop for DashboardSidecar {
    fn drop(&mut self) {
        self.cleanup();
    }
}

pub(super) fn cleanup_dashboard_sidecar_files(socket_dir: &Path, session_id: &str) {
    for extension in [
        "pid",
        "stream",
        "engine",
        "provider",
        "extensions",
        "version",
        "metadata",
        "port",
        "sock",
    ] {
        let _ = fs::remove_file(socket_dir.join(format!("{session_id}.{extension}")));
    }
}
