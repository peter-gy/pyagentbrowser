use crate::{
    native::{
        actions::{execute_command, DaemonState, PendingConfirmation},
        network::DomainFilter,
        policy::PolicyResult,
    },
    session_settings::{spec, Key, Persist, Running},
};
use serde_json::Value;

struct Dispatch<'a>(&'a mut DaemonState);

impl Drop for Dispatch<'_> {
    fn drop(&mut self) {
        self.0.confirmed_policy_actions.clear();
    }
}

pub(crate) async fn dispatch(command: &Value, state: &mut DaemonState) -> Value {
    let scope = Dispatch(state);
    execute_command(command, scope.0).await
}

/// Ends the error for a command that tried to change a security setting.
pub(crate) const SECURITY_SETTINGS_ERROR: &str =
    "a session keeps the allowed domains, action policy, and confirm actions it started with";

/// Refuses a settings change that would replace the session's security
/// settings. Upstream applies settings before its policy gates and from every
/// command source: the `settings` patch, the `launch` envelope, and each step
/// a saved flow replays. The check therefore runs where a planned change is
/// applied. A session that started without allowed domains may adopt a list.
pub(crate) fn authorize_settings(
    running: &Running,
    changed: impl IntoIterator<Item = Key>,
) -> Result<(), String> {
    let contained = running
        .security()
        .allowed_domains
        .is_some_and(|domains| !domains.is_empty());
    for key in changed {
        let spec = spec(key);
        let adopts_allowlist = key == Key::AllowedDomains && !contained;
        if spec.persist == Persist::Secured && !adopts_allowlist {
            return Err(format!(
                "cannot change {}: {SECURITY_SETTINGS_ERROR}",
                spec.name
            ));
        }
    }
    Ok(())
}

fn confirmation_id_from_command(cmd: &Value) -> Result<&str, String> {
    cmd.get("confirmation_id")
        .or_else(|| cmd.get("confirmationId"))
        .and_then(|v| v.as_str())
        .ok_or_else(|| "Missing confirmation_id".to_string())
}

fn validate_pending_confirmation_id(
    cmd: &Value,
    pending: &PendingConfirmation,
) -> Result<(), String> {
    let requested_id = confirmation_id_from_command(cmd)?;
    if requested_id != pending.id {
        return Err(format!(
            "confirmation_id does not match pending confirmation: expected '{}', got '{}'",
            pending.id, requested_id
        ));
    }
    Ok(())
}

/// The parked action and command a confirmation replays.
struct Parked {
    action: String,
    cmd: Value,
}

impl Parked {
    fn denied(&self, reason: impl std::fmt::Display) -> String {
        format!(
            "Action '{}' denied by allowed domains during confirmation: {}",
            self.action, reason
        )
    }

    fn check_url(&self, filter: &DomainFilter, url: &str) -> Result<(), String> {
        filter.check_url(url).map_err(|reason| self.denied(reason))
    }

    fn check_cookie_domain(&self, filter: &DomainFilter, domain: &str) -> Result<(), String> {
        let hostname = domain.trim_start_matches('.');
        if hostname.is_empty() {
            return Err(self.denied("empty cookie domain"));
        }
        if filter.is_allowed(hostname) {
            return Ok(());
        }
        Err(self.denied(format_args!(
            "Cookie domain '{domain}' is not in the allowed domains list"
        )))
    }

    /// Returns whether the cookie named a target that the filter could check.
    fn check_cookie(&self, filter: &DomainFilter, cookie: &Value) -> Result<bool, String> {
        if let Some(url) = cookie.get("url").and_then(|v| v.as_str()) {
            self.check_url(filter, url)?;
            return Ok(true);
        }
        if let Some(domain) = cookie.get("domain").and_then(|v| v.as_str()) {
            self.check_cookie_domain(filter, domain)?;
            return Ok(true);
        }
        Ok(false)
    }

    fn check_allowed_domains(&self, filter: &DomainFilter) -> Result<(), String> {
        if filter.allowed_domains.is_empty() {
            return Ok(());
        }

        if let Some(url) = self.cmd.get("url").and_then(|v| v.as_str()) {
            return self.check_url(filter, url);
        }

        if self.action == "cookies_set" {
            let mut validated_any = false;
            if let Some(cookies) = self.cmd.get("cookies").and_then(|v| v.as_array()) {
                for cookie in cookies {
                    validated_any |= self.check_cookie(filter, cookie)?;
                }
            } else {
                validated_any = self.check_cookie(filter, &self.cmd)?;
            }
            if validated_any {
                return Ok(());
            }
        }

        if matches!(
            self.action.as_str(),
            "cookies_set" | "state_load" | "state_save" | "tab_switch" | "tab_close"
        ) {
            return Err(self.denied("target cannot be validated against allowed domains"));
        }

        Ok(())
    }
}

/// Accepts a `confirm` only for the pending confirmation it names, and only
/// while the current policy and allowed domains still permit the parked action.
/// The pending confirmation stays in place when the check fails.
pub(crate) async fn authorize_confirm(cmd: &Value, state: &mut DaemonState) -> Result<(), String> {
    let parked = {
        let pending = state
            .pending_confirmation
            .as_ref()
            .ok_or("No pending confirmation")?;
        validate_pending_confirmation_id(cmd, pending)?;
        Parked {
            action: pending.action.clone(),
            cmd: pending.cmd.clone(),
        }
    };
    if let Some(ref mut policy) = state.policy {
        policy.reload();
        if let PolicyResult::Deny(reason) = policy.check(&parked.action) {
            return Err(format!(
                "Action '{}' denied by policy during confirmation: {}",
                parked.action, reason
            ));
        }
    }
    let filter = state.domain_filter.read().await;
    if let Some(ref filter) = *filter {
        parked.check_allowed_domains(filter)?;
    }
    Ok(())
}

/// Accepts a `deny` only for the pending confirmation it names.
pub(crate) fn authorize_deny(cmd: &Value, state: &DaemonState) -> Result<(), String> {
    let pending = state
        .pending_confirmation
        .as_ref()
        .ok_or("No pending confirmation")?;
    validate_pending_confirmation_id(cmd, pending)
}
