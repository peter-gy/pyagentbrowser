---
title: Call the raw native protocol
description: Use the complete agent-browser JSON action surface while retaining Python lifecycle, safety, and confirmation handling.
---

# Call the raw native protocol

`browser.native` exposes every JSON action in the pinned `agent-browser` engine. Use it when the installed engine supports a capability that has no typed Python namespace yet.

```python
from agentbrowser import Browser

with Browser.launch() as browser:
    response = browser.native.execute("stream_status")
    print(response.success)
```

## Choose raw envelope or checked data

`native.execute()` preserves the complete `BrowserResponse` envelope, including unsuccessful and confirmation-required results.

`native.data()` raises `BrowserError` or `ConfirmationRequired` for those envelopes and returns checked response data. The default `expect="object"` requires a mapping. Pass `expect="any"` for scalar, array, or null data.

```python
with Browser.launch() as browser:
    data = browser.native.data("stream_status")
    print(data)
```

Both paths retain local-browser preparation, domain checks, policy and confirmation context, lifecycle updates, and direct CDP invalidation.

Pass `_timeoutMs` as a positive integer to bound one native dispatch. The async
worker includes queue time in this budget. Expiry before dispatch raises
`TimeoutError`. An interrupted native command reports `code="execution_timeout"`.
Inspect page state before retrying an interrupted mutation.

## Find the action vocabulary

The engine's native dispatcher defines JSON action names and fields. Print the installed commit and inspect that exact source revision:

```python
import agentbrowser

commit = agentbrowser.__agent_browser_commit__
print(
    "https://github.com/vercel-labs/agent-browser/blob/"
    f"{commit}/cli/src/native/actions.rs"
)
```

The [CLI command reference](https://agent-browser.dev/commands) explains the corresponding user workflows, but CLI spellings such as `tab` can map to JSON actions such as `tab_switch`.

Pass JSON command fields as keyword arguments or through a mapping:

```python
with Browser.launch() as browser:
    browser.tabs.open("https://example.com", label="report")
    tab = browser.native.data("tab_switch", **{"tabId": "report"})
    print(tab)
```

Native action names and response shapes follow the embedded engine version. Promote repeated application code to a typed wrapper only when the application can own its validation and result shape.

Compose application workflows with the public `Page` and `Frame` methods.
