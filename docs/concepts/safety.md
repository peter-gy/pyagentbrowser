---
title: Safety model
description: Configure domain containment, action confirmation, policy files, and explicit unsafe scope overrides.
---

# Safety model

`SessionOptions` attaches domain containment and action policy to one native session. The checks apply to typed namespaces and raw native calls.

The direct `browser.cdp` WebSocket is a separate low-level command plane. Raw
CDP methods bypass Python command policy and confirmation. Use the typed or raw
native action path when those checks or controller lifecycle updates are part of
the application contract.

## Restrict reachable domains

```python
from agentbrowser import Browser, SessionOptions

session = SessionOptions(
    allowed_domains=("example.com", "*.example.com", "iana.org"),
)

with Browser.launch(session=session) as browser:
    browser.open("https://example.com")
```

An exact entry authorizes one host. A wildcard such as `*.example.com` authorizes the root host and its subdomains.

Containment begins before page, popup, frame, worker, and [WebRTC](https://www.w3.org/TR/webrtc/) real-time communication scripts. The SDK rejects launch modes that can restore or open pages before containment starts. An allowlisted session cannot use a profile, storage-state replay, keyed restore, Chrome DevTools Protocol attachment, iOS or Safari providers, or browser arguments that open existing pages.

Python validates direct URLs and host-qualified patterns before dispatch. The native browser enforces network containment. Cookie and storage-state exports are filtered after successful native work.

## Confirm selected actions

```python
from agentbrowser import Browser, ConfirmationRequired, SessionOptions

session = SessionOptions(confirm_actions=("click",))

with Browser.launch(session=session) as browser:
    browser.page.set_content("<button>Publish</button>")
    publish = browser.observe().one(role="button", name="Publish")

    try:
        result = publish.click()
    except ConfirmationRequired as required:
        result = required.pending.confirm()
```

`PendingAction.confirm()` resumes the initiating operation and preserves its return type. For a ref mutation, the continuation also completes the requested wait, next snapshot, and diff. `deny()` rejects it. `map()` attaches higher-level work that runs after confirmation.

Confirmation replay loads the current policy and checks target domains again. A pending action cannot use stale authorization to cross a changed boundary.

`SessionOptions.action_policy` accepts a JSON file with `default`, `allow`, `deny`, and `confirm` fields:

```json
{
  "default": "allow",
  "deny": ["state_load"],
  "confirm": ["click", "cookies_set"]
}
```

The pinned engine compares exact native action names. Deny rules run first, then confirmation rules. A nonempty allow list denies unmatched actions unless `default` is `allow`. A missing allow list uses `default`, with `allow` as the fallback behavior.

`SessionOptions.confirm_actions=("click", "cookies_set")` requests the same exact-name confirmation directly. The installed engine's native dispatcher defines the JSON action vocabulary. Print `agentbrowser.__agent_browser_commit__` and inspect `cli/src/native/actions.rs` at that exact upstream revision. The [raw native protocol guide](/guides/native-protocol#find-the-action-vocabulary) builds the source URL.

The policy file must remain readable and valid JSON. Confirmation reloads it before replay and fails closed when it changed to deny, became invalid, or disappeared.

## Explicit unscoped operations

These flags widen one operation and should appear at the call site that needs them:

| Flag | Operation |
| --- | --- |
| `unsafe_export_all=True` | Export cookies or storage state beyond the session allowlist |
| `unsafe_clear_all=True` | Clear cookies without a domain scope |
| `unsafe_import_all=True` | Request an unscoped state import when session containment permits loading |

## Treat captured artifacts as sensitive

Screenshots, PDFs, downloads, saved state, and HTTP Archive files can contain page data, credentials, authorization headers, cookies, and response bodies. Store them according to the account and origin they came from.

Continue with [Tabs and state](/guides/tabs-and-state) or [Network and diagnostics](/guides/network-and-diagnostics).
