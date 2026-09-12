use crate::native::{
    actions::{execute_command, DaemonState, PendingConfirmation},
    network::DomainFilter,
    policy::PolicyResult,
};
use serde_json::{json, Value};

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

fn validate_confirmation_url(
    pending: &PendingConfirmation,
    filter: &DomainFilter,
    url: &str,
) -> Result<(), String> {
    filter.check_url(url).map_err(|reason| {
        format!(
            "Action '{}' denied by allowed domains during confirmation: {}",
            pending.action, reason
        )
    })
}

fn validate_confirmation_cookie_domain(
    pending: &PendingConfirmation,
    filter: &DomainFilter,
    domain: &str,
) -> Result<(), String> {
    let hostname = domain.trim_start_matches('.');
    if hostname.is_empty() {
        return Err(format!(
            "Action '{}' denied by allowed domains during confirmation: empty cookie domain",
            pending.action
        ));
    }
    if filter.is_allowed(hostname) {
        return Ok(());
    }
    Err(format!(
        "Action '{}' denied by allowed domains during confirmation: Cookie domain '{}' is not in the allowed domains list",
        pending.action, domain
    ))
}

fn validate_confirmation_cookie(
    pending: &PendingConfirmation,
    filter: &DomainFilter,
    cookie: &Value,
) -> Result<bool, String> {
    if let Some(url) = cookie.get("url").and_then(|v| v.as_str()) {
        validate_confirmation_url(pending, filter, url)?;
        return Ok(true);
    }
    if let Some(domain) = cookie.get("domain").and_then(|v| v.as_str()) {
        validate_confirmation_cookie_domain(pending, filter, domain)?;
        return Ok(true);
    }
    Ok(false)
}

fn action_requires_validated_confirmation_target(action: &str) -> bool {
    matches!(
        action,
        "cookies_set" | "state_load" | "state_save" | "tab_switch" | "tab_close"
    )
}

fn validate_confirmation_allowed_domains(
    pending: &PendingConfirmation,
    filter: &DomainFilter,
) -> Result<(), String> {
    if filter.allowed_domains.is_empty() {
        return Ok(());
    }

    if let Some(url) = pending.cmd.get("url").and_then(|v| v.as_str()) {
        validate_confirmation_url(pending, filter, url)?;
        return Ok(());
    }

    if pending.action == "cookies_set" {
        let mut validated_any = false;
        if let Some(cookies) = pending.cmd.get("cookies").and_then(|v| v.as_array()) {
            for cookie in cookies {
                validated_any |= validate_confirmation_cookie(pending, filter, cookie)?;
            }
        } else {
            validated_any = validate_confirmation_cookie(pending, filter, &pending.cmd)?;
        }
        if validated_any {
            return Ok(());
        }
    }

    if action_requires_validated_confirmation_target(&pending.action) {
        return Err(format!(
            "Action '{}' denied by allowed domains during confirmation: target cannot be validated against allowed domains",
            pending.action
        ));
    }

    Ok(())
}

async fn ensure_confirmation_still_allowed(
    pending: &PendingConfirmation,
    state: &mut DaemonState,
) -> Result<(), String> {
    if let Some(ref mut policy) = state.policy {
        policy.reload().map_err(|reason| {
            format!(
                "Action '{}' denied by policy during confirmation: {}",
                pending.action, reason
            )
        })?;
        if let PolicyResult::Deny(reason) = policy.check(&pending.action) {
            return Err(format!(
                "Action '{}' denied by policy during confirmation: {}",
                pending.action, reason
            ));
        }
    }
    let filter = state.domain_filter.read().await;
    if let Some(ref filter) = *filter {
        validate_confirmation_allowed_domains(pending, filter)?;
    }
    Ok(())
}

pub(crate) async fn handle_confirm(cmd: &Value, state: &mut DaemonState) -> Result<Value, String> {
    let pending_for_validation = {
        let pending_ref = state
            .pending_confirmation
            .as_ref()
            .ok_or("No pending confirmation")?;
        validate_pending_confirmation_id(cmd, pending_ref)?;
        PendingConfirmation {
            id: pending_ref.id.clone(),
            action: pending_ref.action.clone(),
            cmd: pending_ref.cmd.clone(),
            approved_actions: pending_ref.approved_actions.clone(),
        }
    };
    ensure_confirmation_still_allowed(&pending_for_validation, state).await?;
    let pending = state
        .pending_confirmation
        .take()
        .expect("pending confirmation was just validated");

    let mut approved_actions = pending.approved_actions.clone();
    if !approved_actions.iter().any(|a| a == &pending.action) {
        approved_actions.push(pending.action.clone());
    }
    let previous_confirmed = std::mem::replace(
        &mut state.confirmed_policy_actions,
        approved_actions.into_iter().collect(),
    );
    let result = Box::pin(execute_command(&pending.cmd, state)).await;
    state.confirmed_policy_actions = previous_confirmed;

    Ok(json!({ "confirmed": true, "action": pending.action, "result": result }))
}

pub(crate) async fn handle_deny(cmd: &Value, state: &mut DaemonState) -> Result<Value, String> {
    let pending_ref = state
        .pending_confirmation
        .as_ref()
        .ok_or("No pending confirmation")?;
    validate_pending_confirmation_id(cmd, pending_ref)?;
    let pending = state
        .pending_confirmation
        .take()
        .expect("pending confirmation was just validated");

    Ok(json!({ "denied": true, "action": pending.action }))
}
