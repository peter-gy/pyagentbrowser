use std::{env, sync::Arc};

use serde::Deserialize;
use serde_json::Value;

use crate::{
    native::{actions::DaemonState, policy::ActionPolicy},
    session_settings::{Key, Running, SecurityView, Store, StoreError},
};

#[derive(Default, Deserialize)]
pub struct EngineOptions {
    pub session: Option<String>,
    pub restore_key: Option<String>,
    pub restore_save: Option<String>,
    pub restore_check_url: Option<String>,
    pub restore_check_text: Option<String>,
    pub restore_check_fn: Option<String>,
    pub namespace: Option<String>,
    pub default_timeout_ms: Option<u64>,
    pub allowed_domains: Option<String>,
    pub engine: Option<String>,
    pub action_policy: Option<String>,
    pub confirm_actions: Option<Vec<String>>,
    pub no_auto_dialog: Option<bool>,
}

/// The owning process supplies an embedded session's security settings on
/// construction, so the engine keeps none of them on disk.
struct ProcessStore;

impl Store for ProcessStore {
    fn load(&self) -> Result<Option<SecurityView>, StoreError> {
        Ok(None)
    }

    fn save(&self, _view: &SecurityView) -> Result<(), StoreError> {
        Ok(())
    }

    fn clear(&self) -> Result<(), StoreError> {
        Ok(())
    }
}

/// Splits allowed domains the way upstream reads them from a `launch` command,
/// so a launch that repeats the session's list plans no change.
fn split_allowed_domains(value: &str) -> Vec<String> {
    value
        .split(',')
        .map(|domain| domain.trim().to_lowercase())
        .filter(|domain| !domain.is_empty())
        .collect()
}

/// Seeds the connection target the environment names. Upstream's CLI resends
/// the target with every command, and an embedded session has no CLI, so the
/// environment supplies the default that a `launch` target replaces.
fn seed_connection(settings: &mut Running) {
    let var = |name: &str| env::var(name).ok().filter(|value| !value.trim().is_empty());
    for (key, name) in [
        (Key::Cdp, "AGENT_BROWSER_CDP"),
        (Key::CdpHeaders, "AGENT_BROWSER_CDP_HEADERS"),
        (Key::Provider, "AGENT_BROWSER_PROVIDER"),
    ] {
        if let Some(value) = var(name) {
            settings.set(key, Value::from(value));
        }
    }
    let auto_connect = var("AGENT_BROWSER_AUTO_CONNECT")
        .is_some_and(|value| !matches!(value.to_lowercase().as_str(), "0" | "false" | "no"));
    if auto_connect {
        settings.set(Key::AutoConnect, Value::Bool(true));
    }
}

/// Environment defaults with the explicit engine options applied on top.
fn settings(options: &EngineOptions) -> Result<Running, String> {
    let mut settings = Running::from_env();
    seed_connection(&mut settings);
    for (key, value) in [
        (Key::RestoreKey, &options.restore_key),
        (Key::RestoreSave, &options.restore_save),
        (Key::RestoreCheckUrl, &options.restore_check_url),
        (Key::RestoreCheckText, &options.restore_check_text),
        (Key::RestoreCheckFn, &options.restore_check_fn),
        (Key::Engine, &options.engine),
        (Key::ActionPolicy, &options.action_policy),
    ] {
        if let Some(value) = value {
            settings.set(key, Value::from(value.as_str()));
        }
    }
    if let Some(restore_save) = &options.restore_save {
        if !matches!(restore_save.as_str(), "auto" | "always" | "never") {
            return Err(format!(
                "Invalid restore save policy '{restore_save}'. Use auto, always, or never."
            ));
        }
    }
    if let Some(action_policy) = &options.action_policy {
        ActionPolicy::load(action_policy)?;
    }
    if let Some(default_timeout_ms) = options.default_timeout_ms {
        settings.set(Key::DefaultTimeout, Value::from(default_timeout_ms));
    }
    if let Some(confirm_actions) = &options.confirm_actions {
        settings.set(Key::ConfirmActions, Value::from(confirm_actions.join(",")));
    }
    if let Some(allowed_domains) = &options.allowed_domains {
        settings.set(
            Key::AllowedDomains,
            Value::from(split_allowed_domains(allowed_domains)),
        );
    }
    if options.no_auto_dialog.unwrap_or(false) {
        settings.set(Key::NoAutoDialog, Value::Bool(true));
    }
    Ok(settings)
}

pub(crate) fn configure(options: &EngineOptions) -> Result<DaemonState, String> {
    let mut daemon = DaemonState::with_store(settings(options)?, Arc::new(ProcessStore));
    if let Some(session) = &options.session {
        daemon.session_id.clone_from(session);
    }
    daemon.namespace.clone_from(&options.namespace);
    if options.restore_key.is_some() {
        daemon.restore_status = "pending".to_string();
    }
    Ok(daemon)
}
