---
title: Use the direct CDP API
description: Connect to Chrome DevTools Protocol targets, frames, and execution contexts from pyagentbrowser.
---

# Use the direct CDP API

The optional `browser.cdp` namespace opens a direct [Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/) connection beside the native engine. Use it for explicit page targets, frames, JavaScript execution contexts, extension contexts, and raw protocol methods.

Focused snippets that start from `browser` are partial. Place them inside an active `Browser` context such as the frame example.

Use `page.frames` for ordinary frame observation, queries, evaluation, waits,
and capture. Direct CDP frame handles provide execution-context selection and
raw protocol access. They have their own lifetime and cannot be passed as
`agentbrowser.Frame` handles.

Install the WebSocket transport:

```bash
python -m pip install "pyagentbrowser[cdp]"
```

## Evaluate in a frame

```python
from agentbrowser import Browser

with Browser.launch() as browser:
    browser.page.set_content("""
        <iframe name="preview" srcdoc="<h1>Ready</h1>"></iframe>
    """)

    frame = browser.cdp.frames.get(name="preview")
    heading = browser.cdp.evaluate(
        "document.querySelector('h1').textContent",
        frame=frame,
    )
    print(heading)
```

```text
Ready
```

`browser.cdp.frames.list()` returns direct frame handles. `get()` selects one iframe by selector, name, or URL.

## Select a page target

```python
browser.tabs.open("https://example.com", label="report")
target = browser.cdp.target(label="report")
title = target.evaluate("document.title")
print(title)
```

The direct target handle can select a tab by its label, URL, or stable target ID. `agentbrowser.CDPTarget`, used by `Browser.attach()`, is a different object that configures a browser debugging endpoint.

## Select an execution context

Direct page sessions list JavaScript execution contexts. The default context shares the page's global objects. An isolated context has its own JavaScript global scope while accessing the same document. An extension context belongs to a browser extension origin.

```python
target = browser.cdp.target()
frame = target.frame()
default_context = frame.context()
value = default_context.evaluate("location.href")

for context in frame.contexts():
    print(context.name, context.origin, context.type, context.is_default)
```

Use `frame.context(extension_id=...)` for one extension context. Use `predicate=` to select exactly one context by `name`, `origin`, `type`, or `is_default`. Zero matches raise `CDPContextNotFoundError`. Several matches raise `CDPContextAmbiguityError`.

Evaluation awaits promises and returns values by value. JavaScript exceptions raise `CDPEvaluationError`. Special numeric values such as `NaN` and infinities become Python floats.

## Send a raw protocol method

```python
result = browser.cdp.send("Runtime.evaluate", {"expression": "2 + 2"})
print(result)
```

`browser.cdp.send()` writes directly to Chrome. Session action-policy and
confirmation rules apply to typed namespaces and `browser.native`, not to raw
CDP methods. The contained browser context retains its network filter, but a raw
method can change browser state that the controller does not track. Prefer the
typed or native-action path for navigation, target creation, state changes, and
browser lifecycle.

The `agentbrowser.cdp` package also exports synchronous and asynchronous clients, controllers, page sessions, target handles, models, transports, connectors, and the CDP error family for applications that need the lower-level objects directly.

## Refresh handles after page changes

Direct frame and execution-context handles are bound to a controller generation. Navigation, document replacement, history movement, tab changes, new windows, browser relaunch, URL-based accessibility audits, and close invalidate cached page state.

Resolve the frame or context again after one of those transitions. A `browser.cdp.target()` handle resolves its selected page target again when an operation runs. Reusing an invalidated frame or context raises `CDPStaleObjectError`.

See [Browser controllers](/reference/browser) for attachment configuration and [Models and errors](/reference/models) for direct protocol failures.
