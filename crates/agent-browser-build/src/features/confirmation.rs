use super::super::{
    patch::{replace_n_named, replace_once_named},
    source::Source,
};

pub(crate) fn rewrite_confirmation_handling(contents: Source) -> Source {
    let contents = replace_once_named(
        contents,
        "confirmation replay state access",
        "    confirmed_policy_actions: HashSet<String>,",
        "    pub(crate) confirmed_policy_actions: HashSet<String>,",
    );
    let contents = replace_once_named(
        contents,
        "PendingConfirmation id field",
        "pub struct PendingConfirmation {\n    pub action: String,",
        "pub struct PendingConfirmation {\n    pub id: String,\n    pub action: String,",
    );
    // Every site parks the command under the request id it reports as
    // `confirmation_id`: the policy file, confirm-actions, and flow-write gates.
    let contents = replace_n_named(
        contents,
        "PendingConfirmation id value",
        "state.pending_confirmation = Some(PendingConfirmation {\n",
        "state.pending_confirmation = Some(PendingConfirmation {\n id: id.to_string(),\n",
        3,
    );
    let contents = replace_once_named(
        contents,
        "confirm authorization",
        "async fn handle_confirm(_cmd: &Value, state: &mut DaemonState) -> Result<Value, String> {\n",
        "async fn handle_confirm(_cmd: &Value, state: &mut DaemonState) -> Result<Value, String> {\n    crate::confirmation::authorize_confirm(_cmd, state).await?;\n",
    );
    // Every settings change is planned here before it is applied: the wire
    // patch, the `launch` envelope, and commands replayed by a saved flow.
    let contents = replace_once_named(
        contents,
        "security settings authorization",
        "    let full = state.settings.plan(&patch);\n",
        "    let full = state.settings.plan(&patch);\n    crate::confirmation::authorize_settings(\n        &state.settings,\n        full.changes.iter().map(|change| change.key),\n    )?;\n",
    );
    // Upstream checks a semantic locator command under the locator's name
    // alone, so a `click` policy would miss a click that names its target by
    // role, text, or label.
    let contents = replace_once_named(
        contents,
        "semantic locator policy action",
        "    let mut actions = vec![action.to_string()];\n",
        "    let mut actions = vec![action.to_string()];\n    if FIND_SUBACTION_COMMANDS.contains(&action) {\n        actions.push(crate::confirmation::locator_policy_action(cmd).to_string());\n    }\n",
    );
    replace_once_named(
        contents,
        "deny authorization",
        "async fn handle_deny(_cmd: &Value, state: &mut DaemonState) -> Result<Value, String> {\n",
        "async fn handle_deny(_cmd: &Value, state: &mut DaemonState) -> Result<Value, String> {\n    crate::confirmation::authorize_deny(_cmd, state)?;\n",
    )
}
