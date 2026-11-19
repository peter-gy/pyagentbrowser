---
title: Safety model
description: Configure domain containment, action confirmation, policy files, and explicit unsafe scope overrides.
---

# Safety model

`SessionOptions` attaches domain containment and action policy to one native session. The checks apply to typed namespaces and raw native calls.

A session keeps the allowed domains, action policy, and confirm actions it started with. A command that would change one of them fails with `BrowserError.code == "security_settings"`. The rule covers a raw `settings` object, a raw `launch`, and every command a [saved flow](/guides/flows) replays. A session created without allowed domains can adopt a list through one raw `launch`.

Raw `browser.cdp` methods travel over a separate WebSocket and skip action
policy and confirmation. Use the typed or raw native action path when those
checks or controller lifecycle updates are part of the application contract.

## Restrict reachable domains

```python
from agentbrowser import Browser, SessionOptions

session = SessionOptions(
    allowed_domains=("example.com", "*.example.com", "iana.org"),
)

with Browser.launch(session=session) as browser:
    browser.page.open("https://example.com")
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
    publish = browser.page.observe().one(role="button", name="Publish")

    try:
        result = publish.click()
    except ConfirmationRequired as required:
        result = required.pending.confirm()
```

`PendingAction.confirm()` resumes the initiating operation and preserves its return type. For a ref mutation, the continuation also completes the requested wait, next snapshot, and diff. `deny()` rejects it. `map()` attaches higher-level work that runs after confirmation.

Confirmation replay loads the current policy and checks target domains again.

`SessionOptions.action_policy` accepts a JSON file with `default`, `allow`, `deny`, and `confirm` fields:

```json
{
  "default": "allow",
  "deny": ["state_load"],
  "confirm": ["click", "cookies_set"]
}
```

The pinned engine compares exact native action names. Deny rules run first, then confirmation rules. A nonempty allow list denies unmatched actions unless `default` is `allow`. A missing allow list uses `default`, with `allow` as the fallback behavior.

A semantic query such as `page.find.role("button").click()` runs as one locator command: `getbyrole`, `getbytext`, `getbylabel`, `getbyplaceholder`, `getbyalttext`, `getbytitle`, `getbytestid`, or `nth`. The engine checks that command under its own name and under the action it performs on the match: `click`, `fill`, `check`, `hover`, or `gettext`. A `click` rule therefore covers a click through a ref, a CSS selector, and a semantic query. An allow list must name both the locator command and the action. `ConfirmationRequired.policy_action` reports which of the two names paused the operation.

`SessionOptions.confirm_actions=("click", "cookies_set")` requests the same exact-name confirmation directly. The installed engine's native dispatcher defines the JSON action vocabulary. Print `agentbrowser.__agent_browser_commit__` and inspect `cli/src/native/actions.rs` at that exact upstream revision. The [raw native protocol guide](/guides/native-protocol#find-the-action-vocabulary) builds the source URL.

The policy file must remain readable and valid JSON. The engine rereads it before each action. While the file is unreadable or invalid, every action except `close` fails with `action policy failed to load`. Confirmation rereads it before replay and fails when the action is now denied.

## Explicit unscoped operations

Each flag widens one operation. Pass it at the call that needs the wider scope:

| Flag | Operation |
| --- | --- |
| `unsafe_export_all=True` | Export cookies or storage state beyond the session allowlist |
| `unsafe_clear_all=True` | Clear cookies without a domain scope |
| `unsafe_import_all=True` | Request an unscoped state import when session containment permits loading |

## Treat captured artifacts as sensitive

Screenshots, PDFs, downloads, saved state, and HTTP Archive files can contain page data, credentials, authorization headers, cookies, and response bodies. Store them according to the account and origin they came from.

Continue with [Tabs and state](/guides/tabs-and-state) or [Network and diagnostics](/guides/network-and-diagnostics).
