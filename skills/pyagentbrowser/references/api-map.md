# API map

Start with `Browser` or `AsyncBrowser`. Both controllers expose the same domain
model. The async surface adds `await` to operations that cross the native
session boundary.

| Task | Python surface | Result |
| --- | --- | --- |
| Open a page | `browser.open(url)` | The same controller |
| Inspect accessible state | `browser.observe(spec)` | Snapshot-scoped refs and text |
| Act with evidence | `snapshot.one(...).click()` | `ActionResult` with before, after, and diff |
| Act through a live locator | `browser.find.role(...).click()` | The same live query |
| Read a page | `browser.read(url)` | `ReadResult` with content and source metadata |
| Wait for state | `browser.page.wait_for_*()` | `None` after the condition passes |
| Capture an image | `browser.capture.screenshot()` | `Screenshot` metadata and path |
| Work with tabs | `browser.tabs` | Typed tab records and switch results |
| Inspect traffic | `browser.network` | Routes, requests, details, or an HTTP archive |
| Inspect failures | `browser.diagnostics` | Console, page error, vital, and audit records |
| Call page tools | `browser.webmcp` | Typed WebMCP tools and invocations |
| Use a CDP session | `browser.cdp` | Direct target, frame, and execution-context handles |
| Call any native action | `browser.native.execute()` | Complete native response envelope |
| Read native action data | `browser.native.data()` | Native response data mapping |

Use `SnapshotSpec` to scope and compact accessible state. Use `Wait` on ref
actions when an expected page transition should be included in the returned
evidence. Use `SessionOptions` for session identity, restore policy, domain
allowlists, confirmation policy, timeouts, pinned tabs, and dashboard streaming.

The installed package records the exact native engine identity:

```python
import agentbrowser

print(agentbrowser.__version__)
print(agentbrowser.__agent_browser_version__)
print(agentbrowser.__agent_browser_commit__)
```

Use <https://peter-gy.github.io/pyagentbrowser/llms.txt> for the complete
versioned documentation map.
