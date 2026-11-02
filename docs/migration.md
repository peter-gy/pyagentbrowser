---
title: Migration guide
description: Update applications for pyagentbrowser 0.41 contracts and the scoped browser agent API.
---

# Migration guide

Each section lists the replacement for a changed contract.

## Upgrade to pyagentbrowser 0.41

### Pass one `RouteResponse` to `network.route()`

```python
from agentbrowser import RouteResponse

browser.network.route(
    "**/api/profile",
    RouteResponse(status=200, body='{"name":"Ada"}', content_type="application/json"),
    resource_types=["fetch"],
)
```

Move `status`, `body`, `content_type`, and `headers` keywords into
`RouteResponse`, and pass it as the second argument. Replace
`resource_type="fetch"` with `resource_types=["fetch"]`.

### Read and clear capture buffers

| Previous call | Replacement |
| --- | --- |
| `network.requests(clear=True)` | `network.clear_requests()` |
| `diagnostics.console(clear=True)` | `diagnostics.clear_console()` |
| `network.request_detail(id)` | `network.request(id)` |

`network.request()` returns `NetworkRequest` with `response_body` set.
`diagnostics.errors()` returns `PageError` records with `text`, `url`, `line`,
and `column`. `ConsoleMessage` carries `type`, `text`, and `args`.

### Set one cookie per `cookies.set()` call

```python
browser.cookies.set("session", "abc", url="https://example.com", http_only=True)
```

Replace `cookies.set(cookies=[...])` with one `cookies.set(name, value, ...)`
call per cookie, or send the batch through
`browser.native.data("cookies_set", cookies=[...])`.

### Rely on required model fields

`Cookie.domain`, `path`, `expires`, `http_only`, `secure`, and `session` are
always set, and a session cookie reports `expires == -1`. `TabInfo.target_id`
and `TabSwitchResult.target_id` are always set. Remove `None` checks for these
fields.

### Read embedded skills through `Skill`

| Previous call | Replacement |
| --- | --- |
| `skills.list()` | `[skills.get(name) for name in skills.available()]` |
| `skills.parts(name)` | `skills.get(name).parts` |
| `skills.part(name, path).content` | `skills.read(name, path)` |
| `skills.markdown(name, full=True)` | `skills.get(name).markdown(full=True)` |
| `skill.content` | `skill.read()` |
| `skill.markdown` | `skill.markdown()` |

`Skill.parts` holds relative path strings. Drop `full=True` from `get()`
calls and replace `SkillPart` and `SkillFile` imports with these path strings
and `read()`.

### Read the result of `state.load()`

`state.load()` returns `StateLoadResult`. Check `skipped_origins` for saved
origins whose Web Storage was not restored because the page was elsewhere.

## Migrate to scoped browser agents

The scoped API gives each browser operation an explicit page or frame handle.
Update controller lifecycle, frame selection, and screenshot delivery together.

### Move document operations to `browser.page`

```python
browser.page.open("https://example.com")
snapshot = browser.page.observe()
browser.page.find.role("button", name="Save").click()
screenshot = browser.page.capture.screenshot("artifacts/page.png")
```

The `Browser` owns lifecycle, tabs, session policy, storage, network, and raw
native access. The `Page` owns navigation, reading, evaluation, waits, queries,
snapshots, scrolling, geometry, frames, and capture.

### Create and retrieve controllers explicitly

```python
import agentbrowser
import agentbrowser.agent as browser_agent

browser = browser_agent.create("review")

# A later call in the same Python process
browser = browser_agent.get("review")

browser_agent.close("review")
```

Replace `connect()` with `create()` at ownership boundaries and `get()` at
retrieval sites. Replace `disconnect()` with `close()`. Duplicate and missing
names now fail, which prevents a retrieval typo from starting another browser.

### Carry frame scope through a handle

```python
preview = browser.page.frames.get(selector="iframe[title='Preview']")
preview.wait_for_text("Ready")
snapshot = preview.observe()
print(preview.evaluate("document.title"))
```

Replace ambient frame selection with `Page.frames.get()`. Move observation,
queries, evaluation, waits, scrolling, geometry, and capture to the returned
`Frame`. Return to the main document by using `browser.page`.

### Read screenshot content

```python
screenshot = preview.capture.screenshot("artifacts/preview.png")
content = screenshot.content()
print(content.media_type, len(content.data))
```

`Screenshot.content()` returns image bytes and MIME type. Notebook frontends
can render the screenshot through standard image display protocols. An agent
host forwards the content through its own image channel. See
[Code-mode integration](/guides/code-mode).

### Import public types from `agentbrowser`

```python
from agentbrowser import (
    NativeParseError,
    Snapshot,
    SnapshotSpec,
)
```

Replace imports from `agentbrowser.models`, `agentbrowser.domains`,
`agentbrowser.domains_async`, `agentbrowser.query`, and
`agentbrowser.query_async` with their public `agentbrowser` exports. Internal
modules now follow capability ownership and are outside the supported import
contract.

Replace `snapshot.browser` and `ref.browser` with `snapshot.document` and
`ref.document`. They return the producing page or frame handle. Keep the browser
controller separately when a task needs session-wide operations.

Use `print(browser_agent.help())` for the installed SDK task map. Python's
built-in `help(browser_agent)` describes the module's signatures.
