# API map

Start with `Browser` or `AsyncBrowser`. Both controllers expose the same domain
model. The async surface adds `await` to operations that cross the native
session boundary.

| Task | Python surface | Result |
| --- | --- | --- |
| Open a page | `browser.page.open(url)` | `None` after navigation completes |
| Read the current location | `page.url()` and `page.title()` | URL and page title strings |
| Bind one exact tab | `browser.tabs.get(id=...)` | `Page` with stable target identity |
| Inspect accessible state | `page.observe(spec)` | Document-scoped refs and text |
| Inspect descendant frames | `page.frames.tree()` | `Frame` handles with identities and parent links |
| Bind one child frame | `page.frames.get(selector=...)` | `Frame` with scoped operations |
| Act with evidence | `snapshot.one(...).click()` | `ActionResult` with before, after, and diff |
| Act through a live locator | `page.find.role(...).click()` | The same scoped live query |
| Read a page | `page.read(url)` | `ReadResult` with content and source metadata |
| Wait for state | `browser.page.wait_for_*()` | `None` after the condition passes |
| Measure scrolling | `page.scroll.by(...)` | `ScrollResult` with before and after offsets |
| Measure layout | `page.geometry(selector=None)` | Bounds, client size, scroll size, and overflow flags |
| Capture an image | `page.capture.screenshot()` | `Screenshot` with artifact and document scope |
| Prepare host image content | `screenshot.content()` | Image bytes, MIME type, and source path |
| Execute code for an agent | `CodeSession.execute_code()` | Ordered text and image tool-result content |
| Keep async work across calls | `current_host().start_task(...)` | Observable `Task` with retained result and settled cancellation |
| Inspect configured features | `browser.capabilities(host=...)` | `BrowserCapabilities` without browser startup |
| Probe optional dependencies | `browser.healthcheck()` | Loaded module paths and recovery guidance |
| Work with tabs | `browser.tabs` | Typed tab records and switch results |
| Inspect traffic | `browser.network` | Routes, requests, details, or an HTTP archive |
| Inspect failures | `browser.diagnostics` | Console, page error, vital, and audit records |
| Inspect the native session | `browser.session.status()` | Typed identity and lifecycle state |
| Call page tools | `browser.webmcp` | Typed WebMCP tools and invocations |
| Use a CDP session | `browser.cdp` | Direct protocol targets and execution contexts |
| Call any native action | `browser.native.execute()` | Complete native response envelope |
| Read native action data | `browser.native.data()` | Native response data mapping |

Use `SnapshotSpec` to scope and compact accessible state. Use `Wait` on ref
actions when an expected page transition should finish before the returned
snapshot. The default snapshot emphasizes interactive elements, so inspect
`result.after.origin` and use `SnapshotSpec(interactive=False)` when the result
must include surrounding page content. Use `SessionOptions` for session identity, restore policy, domain
allowlists, confirmation policy, timeouts, pinned tabs, and dashboard streaming.

`current_host()` returns the `AgentHost` bound to the current tool execution.
An `AgentHost` returns `OpenTarget` when the workflow should open an application
URL. It returns `AttachedTarget` when it can supply an authorized browser
connection and exact page identity. `ExecutionContext.limit()` converts the
host's remaining tool budget into an operation timeout while reserving cleanup
time.

The installed package records the exact native engine identity:

```python
import agentbrowser

print(agentbrowser.__version__)
print(agentbrowser.__agent_browser_version__)
print(agentbrowser.__agent_browser_commit__)
```

Use <https://peter-gy.github.io/pyagentbrowser/llms.txt> for the complete
versioned documentation map.
