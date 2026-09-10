use super::super::{patch::replace_once_named, source::Source};

pub(crate) fn rewrite_confirmation_handling(contents: Source) -> Source {
    let contents = replace_once_named(
        contents,
        "confirmation replay state access",
        "    confirmed_policy_actions: HashSet<String>,",
        "    pub(crate) confirmed_policy_actions: HashSet<String>,",
    );
    const UPSTREAM_PENDING_CONFIRMATION: &str = r#"pub struct PendingConfirmation {
    pub action: String,
    pub cmd: Value,
    approved_actions: Vec<String>,
}"#;
    const REWRITTEN_PENDING_CONFIRMATION: &str = r#"pub struct PendingConfirmation {
    pub id: String,
    pub action: String,
    pub cmd: Value,
    pub(crate) approved_actions: Vec<String>,
}"#;
    const UPSTREAM_POLICY_CONFIRM_RESPONSE: &str = r#"state.pending_confirmation = Some(PendingConfirmation {
                action: policy_action.clone(),
                cmd: cmd.clone(),
                approved_actions: state.confirmed_policy_actions.iter().cloned().collect(),
            });
            return json!({
                "id": id,
                "success": true,
                "data": {
                    "confirmation_required": true,
                    "confirmation_id": id,
                    "action": policy_action
                },
            });"#;
    const REWRITTEN_POLICY_CONFIRM_RESPONSE: &str = r#"state.pending_confirmation = Some(PendingConfirmation {
                id: id.clone(),
                action: policy_action.clone(),
                cmd: cmd.clone(),
                approved_actions: state.confirmed_policy_actions.iter().cloned().collect(),
            });
            return json!({
                "id": id,
                "success": true,
                "data": {
                    "confirmation_required": true,
                    "confirmation_id": id,
                    "action": policy_action
                },
            });"#;
    const UPSTREAM_CONFIRM_ACTIONS_RESPONSE: &str = r#"state.pending_confirmation = Some(PendingConfirmation {
                        action: policy_action.to_string(),
                        cmd: cmd.clone(),
                        approved_actions: state.confirmed_policy_actions.iter().cloned().collect(),
                    });
                    return json!({
                        "id": id,
                        "success": true,
                        "data": {
                            "confirmation_required": true,
                            "confirmation_id": id,
                            "action": policy_action,
                        },
                    });"#;
    const REWRITTEN_CONFIRM_ACTIONS_RESPONSE: &str = r#"state.pending_confirmation = Some(PendingConfirmation {
                        id: id.clone(),
                        action: policy_action.to_string(),
                        cmd: cmd.clone(),
                        approved_actions: state.confirmed_policy_actions.iter().cloned().collect(),
                    });
                    return json!({
                        "id": id,
                        "success": true,
                        "data": {
                            "confirmation_required": true,
                            "confirmation_id": id,
                            "action": policy_action,
                        },
                    });"#;
    const UPSTREAM_CONFIRM_HANDLERS: &str = r#"async fn handle_confirm(_cmd: &Value, state: &mut DaemonState) -> Result<Value, String> {
    let pending = state
        .pending_confirmation
        .take()
        .ok_or("No pending confirmation")?;

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

async fn handle_deny(_cmd: &Value, state: &mut DaemonState) -> Result<Value, String> {
    let pending = state
        .pending_confirmation
        .take()
        .ok_or("No pending confirmation")?;

    Ok(json!({ "denied": true, "action": pending.action }))
}"#;
    const REWRITTEN_CONFIRM_HANDLERS: &str =
        "use crate::confirmation::{handle_confirm, handle_deny};";

    let mut rewritten = replace_once_named(
        contents,
        "PendingConfirmation",
        UPSTREAM_PENDING_CONFIRMATION,
        REWRITTEN_PENDING_CONFIRMATION,
    );
    rewritten = replace_once_named(
        rewritten,
        "policy confirmation response",
        UPSTREAM_POLICY_CONFIRM_RESPONSE,
        REWRITTEN_POLICY_CONFIRM_RESPONSE,
    );
    rewritten = replace_once_named(
        rewritten,
        "confirm_actions confirmation response",
        UPSTREAM_CONFIRM_ACTIONS_RESPONSE,
        REWRITTEN_CONFIRM_ACTIONS_RESPONSE,
    );
    rewritten = replace_once_named(
        rewritten,
        "confirm/deny handlers",
        UPSTREAM_CONFIRM_HANDLERS,
        REWRITTEN_CONFIRM_HANDLERS,
    );
    assert!(
        rewritten.contains("pub id: String"),
        "upstream PendingConfirmation shape changed"
    );
    rewritten
}
