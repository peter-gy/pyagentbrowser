# Guides

These guides build on the browser lifecycle from [Get started](getting-started.md). Each section links its public objects to the matching contract in the [API reference](api.md).

## Capture a page transition

[`Browser.observe()`](api.md#snapshots-and-refs) captures an accessibility snapshot. A ref action captures the next snapshot with the same `SnapshotSpec` and returns both states in an `ActionResult`.

```python
from agentbrowser import Browser, SnapshotSpec, Wait

spec = SnapshotSpec(compact=True, urls=True)

with Browser.launch() as browser:
    browser.open("https://example.com")
    page = browser.observe(spec)

    result = page.one(role="link", name="Learn more").click(
        wait=Wait.all(
            Wait.loaded("domcontentloaded"),
            Wait.url("*://www.iana.org/*"),
        )
    )

    print(result.before.origin)
    print(result.after.origin)
    print(result.diff.changed)
```

The action runs before the wait. If the action succeeds and the wait, resulting snapshot, or diff fails, `ActionTransitionError` identifies the failed `stage` and keeps the snapshot captured before the action. Treat the action as completed when handling this error.

## Refresh a stale ref

Refs belong to the [snapshot](api.md#snapshots-and-refs) that created them. A page replacement can expire their native identity. `StaleRefError.refresh()` captures a new snapshot and resolves the ref by its accessible role and name.

```python
from agentbrowser import Browser, StaleRefError

with Browser.launch() as browser:
    browser.page.set_content('<button type="button">Save</button>')
    save = browser.observe().one(role="button", name="Save")
    browser.open("data:text/html,<button%20type='button'>Save</button>")

    try:
        result = save.click()
    except StaleRefError as error:
        result = error.refresh().click()
```

Pass new criteria to `refresh()` when the accessible name changed.

## Use live queries

[`browser.find`](api.md#live-queries) creates a `Query` that resolves against the active document when an operation runs. Query mutations return the query for chaining.

```python
from agentbrowser import Browser

with Browser.launch() as browser:
    browser.page.set_content("""
        <label>Email <input id="email"></label>
        <label>Password <input id="password" type="password"></label>
        <button type="button">Sign in</button>
    """)
    browser.find.label("Email").fill("ada@example.com")
    browser.find.label("Password").fill("correct horse battery staple")
    browser.find.role("button", name="Sign in").click()
```

Available strategies are CSS, XPath, role, text, label, placeholder, alt text, title, and test ID. Snapshot refs add before-and-after evidence. Queries keep direct interactions short.

## Read a document and capture the page

[`browser.read()`](api.md#active-page-methods) returns agent-readable content from an explicit URL or the rendered active tab. `ReadMode` selects Markdown, HTML, outline, or `llms.txt` behavior. [`browser.capture`](api.md#page-and-artifact-namespaces) writes screenshots and PDFs from the active tab.

```python
from agentbrowser import Browser, ReadMode

with Browser.launch() as browser:
    browser.open("https://example.com")
    document = browser.read(mode=ReadMode.markdown())
    screenshot = browser.capture.screenshot("page.png", full_page=True)

    print(document.content)
    print(screenshot.path)
```

Install `pyagentbrowser[images]` to use `Screenshot.pil()` and `Screenshot.image`. PNG and JPEG screenshots expose notebook display data from their file bytes. `Screenshot.marimo()` requires marimo. `browser.capture.pdf()` returns the written PDF path.

## Work with tabs

Labels give [tabs](api.md#browser-state-namespaces) stable names inside a session. `tabs.open()` reuses a matching label by default and returns a `TabInfo`.

```python
from agentbrowser import Browser

with Browser.launch() as browser:
    browser.tabs.open("https://example.com/report", label="report")
    browser.tabs.open("https://example.com/settings", label="settings")

    selected = browser.tabs.switch(label="report")
    print(selected.revived, selected.dialog_blocked)
    print(browser.tabs.list())
```

Pass `reuse=False` to create a new tab when the label already exists.
`tabs.switch()` and `tabs.close()` accept one id, label, or zero-based index.
A switch can reactivate a discarded renderer. `TabSwitchResult.revived=True`
means the page may have reloaded, so refresh workflow state derived from the
page. `TabSwitchResult.dialog_blocked=True` means a JavaScript dialog paused
the renderer and the result contains last-known URL and title metadata.
`TabCloseResult.active_tab_revived=True` reports a reactivated successor after
the selected tab closes.

## Save and restore browser state

[`browser.state`](api.md#browser-state-namespaces) saves and loads cookies plus origin storage through explicit files. [`RestoreOptions`](api.md#restoreoptions) binds periodic persistence to a session key.

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
browser.open("https://example.com")
print(browser.session.status().restore_status)

closed = browser.close()
print(closed.save_status)
```

An explicit `autosave_interval_ms` takes precedence over `AGENT_BROWSER_AUTOSAVE_INTERVAL_MS`. `close()` raises `RestoreSaveError` after cleanup when persistence fails. Use `browser.state.save(path)` and `browser.state.load(path)` when the workflow owns the state file directly.

## Capture network traffic

[`browser.network`](api.md#browsernetwork) records an HTTP Archive with request
metadata and selected response bodies:

```python
from agentbrowser import Browser

with Browser.launch() as browser:
    browser.network.har_start(content="text")
    browser.open("https://example.com")
    har_path = browser.network.har_stop("trace.har")

print(har_path)
```

`content="text"` embeds text-like bodies up to 2 MiB each. Use `"all"` to
include base64-encoded binary bodies or `"none"` to record metadata. One
recording can embed up to 64 MiB. Treat the HAR as sensitive when the page uses
cookies, authorization headers, or account data.

## Audit page accessibility

[`browser.diagnostics.accessibility()`](api.md#browserscripts-browserdiagnostics-and-browseractive_frame)
runs the embedded axe-core engine and returns typed violations, incomplete
checks, and rule counts:

```python
from agentbrowser import Browser

with Browser.launch() as browser:
    audit = browser.diagnostics.accessibility(
        "https://example.com",
        tags=("wcag2a", "wcag2aa"),
        selector="main",
    )

for issue in audit.violations:
    print(issue.id, issue.impact, issue.node_count)
```

Pass a URL to navigate before the audit or omit it to inspect the active page.
Each `AccessibilityNode.target` preserves axe selector paths as nested tuples
across frames and shadow roots. Audits require a CDP browser.

## Restrict domains and confirm actions

[`SessionOptions.allowed_domains`](api.md#sessionoptions) checks navigation,
host-qualified URL patterns, cookies, permission origins, and raw native
commands before native execution. State exports are filtered after the native
write unless `unsafe_export_all=True`.

```python
from agentbrowser import Browser, ConfirmationRequired, SessionOptions

session = SessionOptions(
    allowed_domains=("example.com", "*.example.com", "iana.org", "www.iana.org"),
    confirm_actions=("click",),
)

with Browser.launch(session=session) as browser:
    browser.open("https://example.com")
    link = browser.observe().one(role="link", name="Learn more")

    try:
        result = link.click()
    except ConfirmationRequired as required:
        result = required.pending.confirm()
```

Domain-restricted sessions launch a fresh controllable browser context so
containment covers page requests, popups, frames, workers, and WebRTC before
scripts run. Configure authentication after launch through browser APIs.
Restore, storage-state replay, profiles, CDP attachment, and
`browser.state.load()` raise an error while the allowlist is active.

[`pending.confirm()`](api.md#confirmation) preserves the initiating method's return type. For a ref action, it also completes the requested wait, resulting snapshot, and diff. `pending.deny()` rejects the action and returns `None`.

An action policy file can define allow, deny, and confirm rules. `SessionOptions.action_policy` accepts its path. Policy confirmation is rechecked against the current policy and domain allowlist when the pending action resumes.

## Observe a session dashboard

Configure [`DashboardOptions`](api.md#dashboardoptions) before the native session starts:

```python
from agentbrowser import Browser, DashboardOptions, SessionOptions

session = SessionOptions(dashboard=DashboardOptions(port=0))

with Browser.launch(session=session) as browser:
    print(browser.dashboard.status())
    browser.dashboard.stop()
```

The browser owns the stream and dashboard sidecar. Closing the browser releases both.

## Use frames, scripts, and CDP

[`browser.active_frame`](api.md#network-and-script-namespaces) selects the native frame used by later native commands. [`browser.cdp`](api.md#cdp) exposes target, frame, execution-context, evaluation, and raw protocol methods.

```python
from agentbrowser import Browser

with Browser.launch() as browser:
    browser.scripts.add_init("window.__agentReady = true")
    browser.open("https://example.com")

    frames = browser.cdp.frames.list()
    title = browser.cdp.evaluate("document.title", frame=frames[0])
    ready = browser.cdp.evaluate("window.__agentReady", frame=frames[0])
    print(title, ready)
```

Install `pyagentbrowser[cdp]` for these APIs. Page navigation and tab changes invalidate cached CDP handles. Resolve the frame, target, or context again after navigation.

## Call the native protocol

Typed namespaces cover the stable Python workflows. [`browser.native`](api.md#native-protocol) exposes every action in the pinned engine while retaining Python allowlist, policy, and lifecycle handling.

```python
from agentbrowser import Browser

with Browser.launch() as browser:
    response = browser.native.execute("stream_status")
    data = browser.native.data("stream_status")

    print(response.success)
    print(data)
```

`native.execute()` returns the complete `BrowserResponse` envelope. `native.data()` raises `BrowserError` for unsuccessful responses and returns checked response data. Pass `expect="any"` for native actions whose data is a scalar, list, or `null`.

See the [API reference](api.md) for namespace methods, configuration fields, result models, and errors.
