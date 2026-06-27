# Concepts

## Native Session

Each `Browser` owns an in-process native `agent-browser` state. Python sends the
same JSON command protocol the upstream engine uses internally, but presents
typed Python objects and exceptions.

Use `browser.native.execute(action, **params)` when a native action needs the
raw response envelope. Use `browser.native.data(..., expect="object")` when the
native action should return object-shaped data.

## Namespaces

The public API is grouped by responsibility:

- `browser.page`: navigation, active-page content, active-page evaluation, waits.
- `browser.agent`: snapshot and ref observation.
- `browser.find`: CSS and semantic lookup.
- `browser.capture`: screenshots and PDFs.
- `browser.active_frame`: native active-frame selection.
- `browser.cdp`: CDP frame handles, target handles, and JavaScript evaluation.
- `browser.scripts`: script and style injection.
- `browser.runtime`: native session and launch diagnostics.
- `browser.restore`: native restore diagnostics.
- `browser.cookies`, `browser.storage`, `browser.network`, `browser.downloads`,
  `browser.clipboard`, `browser.keyboard`, `browser.mouse`: native browser
  domains.

`AsyncBrowser` mirrors the same shape.

## Default Session

`pyagentbrowser.notebook` exposes namespace proxies over one process-local
default browser:

```python
import pyagentbrowser as ab
from pyagentbrowser import LaunchOptions

ab.notebook.configure(launch_options=LaunchOptions(headless=True))
ab.notebook.page.open("https://example.com")
print(ab.notebook.page.title())
ab.notebook.close()
```

CDP attachment uses an explicit `connect()` call:

```python
import pyagentbrowser as ab
from pyagentbrowser import CDPAttach

browser = ab.notebook.configure(attach=CDPAttach(port=9222))
browser.connect()
print(browser.tabs.list())
```

For explicitly constructed browsers, `Browser.attach(...)` connects before it
returns. In notebook workflows, use `browser.connect()` when a configured attach
target should connect before navigation.

Use `ab.notebook.default_browser()` when code needs the explicit `Browser` object.

Notebook kernels can outlive an interrupted browser run. If native close fails
and leaves the default browser stale, use `ab.notebook.reset(force=True)` or
`ab.notebook.configure(..., force=True)` to discard the process-local reference before
continuing.

## Restore State

Use `RestoreOptions` with a stable `session` when a browser should keep cookies
and localStorage across runs:

```python
import pyagentbrowser as ab
from pyagentbrowser import Browser, RestoreOptions

session_id = ab.session_id(prefix="my-app").session

with Browser.from_session(
    session_id,
    restore=RestoreOptions(key=session_id, check_text="Dashboard"),
) as browser:
    browser.page.open("https://app.example.com/dashboard")
```

`RestoreOptions.key` is the persistence key. Use a separate key such as
`RestoreOptions(key="login-state")` when browser isolation and restore state
should not share the same name. `browser.restore.info()` returns the current
restore status and the last saved or loaded state path when native provides it.

## Scratchpad Browsing

Notebook workflows often need small, repeatable browser actions. Use
`browser.tabs.open(url, label="name")` to reuse a named tab, `browser.page.ready()`
when a page is usable even if strict load-state waits are noisy, and
`browser.find.xpath("//main//a")` for DevTools-style XPath selection through the
same locator API as CSS selectors and refs.

## Snapshots And Refs

`browser.agent.observe()` returns an `AgentSnapshot`. The snapshot contains text
plus native refs such as `@e1`. `AgentSnapshot.find(...)` binds those refs to
Python objects so actions can be written directly:

```python
page = browser.agent.observe()
page.find(role="button", name="Save", exact=True).click()
```

Refs are freshness-bound. After navigation or large DOM changes, observe again.
After `click_and_observe()` or `fill_and_observe()`, continue from
`evidence.after`.

## Confirmations

Native action policy confirmations are raised as `ActionConfirmationRequired`.
Use `confirmation.pending_action.confirm()` to replay the pending action after
the native engine accepts the confirmation. Use
`confirmation.pending_action.deny()` to reject it.

Confirmation replay requires a matching confirmation id, reloads policy
fail-closed, and re-checks URL and cookie allowlist constraints before replay.
The same allowlist checks raw URL targets, host-qualified URL patterns, cookie
targets, and permission origins before native execution. Storage-state loads are
filtered before native import. Storage-state saves and cookie reads are filtered
before they return unless the unsafe export option is used.

## Skills

`pyagentbrowser.skills` exposes upstream `agent-browser` skill data embedded at
build time:

```python
from pyagentbrowser import skills

for skill in skills.list():
    print(skill.name, skill.description)

print(skills.read("core", "references/snapshot-refs.md"))
```

Runtime users do not need the upstream git submodule checked out.
