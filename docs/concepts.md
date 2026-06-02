# Concepts

## Native Session

Each `Browser` owns an in-process native `agent-browser` state. Python sends the
same JSON command protocol the upstream engine uses internally, but presents
typed Python objects and exceptions.

Use `Browser.command(action, **params)` for native actions that need the raw
command surface.

## Namespaces

The public API is grouped by responsibility:

- `browser.page`: navigation, active-page content, active-page evaluation, waits.
- `browser.agent`: snapshot and ref observation.
- `browser.find`: CSS and semantic lookup.
- `browser.capture`: screenshots and PDFs.
- `browser.frames`: high-level frame listing, resolution, and switching.
- `browser.cdp`: frame/context/target JavaScript evaluation.
- `browser.scripts`: script and style injection.
- `browser.cookies`, `browser.storage`, `browser.network`, `browser.downloads`,
  `browser.clipboard`, `browser.keyboard`, `browser.mouse`: native browser
  domains.

`AsyncBrowser` mirrors the same shape.

## Default Session

`import pyagentbrowser as ab` exposes namespace proxies over one process-local
default browser:

```python
import pyagentbrowser as ab

ab.configure(headless=True)
ab.page.open("https://example.com")
print(ab.page.title())
ab.close()
```

CDP attachment options connect immediately on configure:

```python
browser = ab.configure(cdp_port=9222)
print(browser.tabs.list())
```

For explicitly constructed browsers, use `browser.connect()` when you need to
attach without navigating first.

Use `ab.default_browser()` when code needs the explicit `Browser` object.

Notebook kernels can outlive an interrupted browser run. If native close fails
and leaves the default browser stale, use `ab.reset(force=True)` or
`ab.configure(..., force=True)` to discard the process-local reference before
continuing.

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
`browser.confirm(...)` replays the pending action only after the native engine
accepts the confirmation.

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
