use std::{collections::HashSet, sync::Arc};

use serde::Deserialize;
use tokio::sync::RwLock;

use crate::native::{
    actions::DaemonState,
    network::DomainFilter,
    policy::{ActionPolicy, ConfirmActions},
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

pub(crate) fn configure(options: &EngineOptions) -> Result<DaemonState, String> {
    let mut daemon = DaemonState::new();
    if let Some(session) = &options.session {
        daemon.session_id.clone_from(session);
    }
    daemon.namespace.clone_from(&options.namespace);
    if let Some(restore_key) = &options.restore_key {
        daemon.session_name = Some(restore_key.clone());
        daemon.restore_status = "pending".to_string();
    }
    if let Some(restore_save) = &options.restore_save {
        if !matches!(restore_save.as_str(), "auto" | "always" | "never") {
            return Err(format!(
                "Invalid restore save policy '{}'. Use auto, always, or never.",
                restore_save
            ));
        }
        daemon.restore_save.clone_from(restore_save);
    }
    if let Some(check) = &options.restore_check_url {
        daemon.restore_check_url = Some(check.clone());
    }
    if let Some(check) = &options.restore_check_text {
        daemon.restore_check_text = Some(check.clone());
    }
    if let Some(check) = &options.restore_check_fn {
        daemon.restore_check_fn = Some(check.clone());
    }
    if let Some(default_timeout_ms) = options.default_timeout_ms {
        daemon.default_timeout_ms = default_timeout_ms;
    }
    if let Some(engine) = &options.engine {
        daemon.engine.clone_from(engine);
    }
    if let Some(action_policy) = &options.action_policy {
        daemon.policy = Some(ActionPolicy::load(action_policy)?);
    }
    if let Some(confirm_actions) = &options.confirm_actions {
        let categories: HashSet<String> = confirm_actions
            .iter()
            .map(|action| action.trim().to_lowercase())
            .filter(|action| !action.is_empty())
            .collect();
        daemon.confirm_actions = if categories.is_empty() {
            None
        } else {
            Some(ConfirmActions { categories })
        };
    }
    if let Some(allowed_domains) = &options.allowed_domains {
        daemon.domain_filter = Arc::new(RwLock::new(Some(DomainFilter::new(allowed_domains))));
    }
    if options.no_auto_dialog.unwrap_or(false) {
        daemon.auto_dialog = false;
    }
    Ok(daemon)
}
