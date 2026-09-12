---
title: Work with tabs and browser state
description: Name tabs, pin attached sessions, manage cookies and Web Storage, and choose explicit or automatic persistence.
---

# Work with tabs and browser state

Tab identity and stored browser data solve separate problems. Labels select tabs inside a session. Explicit state files and keyed restore records preserve cookies and origin storage.

## Name and reuse tabs

```python
from agentbrowser import Browser

with Browser.launch() as browser:
    report = browser.tabs.open("https://example.com/report", label="report")
    browser.tabs.open("https://example.com/settings", label="settings")

    selected = browser.tabs.switch(label="report")
    print(report.target_id)
    print(selected.revived, selected.dialog_blocked)
```

`tabs.open()` reuses a matching label by default. Pass `reuse=False` with no label or a different unused label to create another tab. Labels are unique within the session. They start with an ASCII letter and contain letters, digits, hyphens, or underscores.

`tabs.switch()` accepts exactly one native ID, label, or numeric ID suffix through `index`. The `index` value maps directly to `t{index}` and begins at 1. It is a stable ID suffix, not a position in the current list. Prefer `id` or `label` for readable code. `tabs.close()` accepts one selector or closes the active tab when all three are omitted.

A switch can reactivate a discarded renderer. `revived=True` means the page may have reloaded, so refresh page-derived state. `dialog_blocked=True` means a JavaScript dialog paused the renderer and the result contains last-known tab metadata.

Retain a `Page` when work must stay on one target across tab changes:

```python
report_page = browser.tabs.get(label="report")
browser.tabs.switch(label="settings")
print(report_page.title())
```

Each operation on `report_page` selects its bound target before acting. That
selection follows the session's `tab_switch` policy and can require
confirmation. Reading `browser.page` acquires a new handle for the configured
target or the current active target.

`tabs.new()` always creates a tab and forwards its optional URL as given. `tabs.open()` normalizes host-like URLs and can reuse a label. `wait_until` applies when a labeled tab is reused and navigated. Newly created tabs return after the native creation action, so wait on the required page state explicitly.

## Pin a tab in an attached browser

```python
from agentbrowser import Browser, CDPTarget, SessionOptions

session = SessionOptions(session_id="report-agent", pin_tab=True)

with Browser.attach(CDPTarget(port=9222), session=session) as browser:
    report = browser.tabs.open("https://example.com/report", label="report")
    print(report.target_id)
```

The named session restores its page target binding across native restarts. A target closed by another client raises `BrowserError` with `code="tab_gone"`. Recovery data contains the target ID and can contain a sanitized last URL.

## Choose a persistence model

| Surface | Scope | Use it for |
| --- | --- | --- |
| `browser.cookies` | Cookies visible to selected URLs | Read, set, and clear cookie records |
| `browser.storage` | Live [Web Storage](https://html.spec.whatwg.org/multipage/webstorage.html) for the active origin | Read or change current local or session values |
| `browser.state` | An explicit serialized state file | Save, load, inspect, rename, or clean files under application control |
| `RestoreOptions` | A keyed native restore record | Load on startup and save periodically or at close |

## Save an explicit state file

```python
with Browser.launch() as browser:
    browser.page.open("https://example.com")
    state_path = browser.state.save("account.json")

with Browser.launch() as browser:
    browser.state.load(state_path)
    browser.page.open("https://example.com")
```

An active domain allowlist filters exports and rejects state loading. Use the explicit unsafe flags only when the wider scope is part of the application contract.

## Configure keyed restore

```python
from agentbrowser import Browser, RestoreOptions, SessionOptions

session = SessionOptions(
    session_id="research",
    restore=RestoreOptions(
        key="research-account",
        save="auto",
        autosave_interval_ms=30_000,
    ),
)

browser = Browser.launch(session=session)
browser.page.open("https://example.com")
print(browser.session.status().restore_status)

closed = browser.close()
print(closed.save_status, closed.state_path)
```

An explicit autosave interval takes precedence over `AGENT_BROWSER_AUTOSAVE_INTERVAL_MS`. Restore validation can check a URL, page text, or JavaScript predicate. A save failure raises `RestoreSaveError` after cleanup and preserves `CloseResult`.

## Separate session data with a namespace

`SessionOptions.namespace` scopes native discovery paths, restore records, and tab bindings. It does not create a separate browser process or a network sandbox. Use `allowed_domains` for network containment.

Read [the runtime model](/concepts/runtime-model) for every identity and [the safety model](/concepts/safety) for storage boundaries.
