---
title: Use browsers from code-mode hosts
description: Keep browser objects across agent calls and forward screenshot bytes through the calling host.
---

# Use browsers from code-mode hosts

A code-mode host executes Python on behalf of an agent. It supplies the target
URL or browser connection and retains objects across calls. Use the same
`Browser`, `Page`, and `Frame` APIs as a Python application.

## Keep a browser across calls

```python
import agentbrowser.agent as browser_agent

help(browser_agent)
print(browser_agent.help())
browser = browser_agent.create("review")
browser.page.set_content("<h1>Orders</h1>")
```

In a later call in the same Python process:

```python
browser = browser_agent.get("review")
print(browser.page.title())
shot = browser.page.capture.screenshot("artifacts/orders.png")
```

Use `browser.page.open(app_url)` for an application URL supplied by the host.
For an existing browser, use `Browser.attach(CDPTarget(...))` and select the
intended tab by ID. See [Tabs and state](/guides/tabs-and-state). A registry name
identifies a controller in this Python process. A fresh process needs its own
browser construction or explicit attachment.

Finish with `browser_agent.close("review")`.

## Forward image content

`shot.content()` returns `ImageContent` with bytes, MIME type, and source path.
The host converts this value into its image-output format. For a
[Model Context Protocol tool result](https://modelcontextprotocol.io/specification/2025-06-18/server/tools#tool-result):

```python
import base64

from agentbrowser import Screenshot


def screenshot_result(shot: Screenshot) -> dict:
    content = shot.content()
    return {
        "content": [{
            "type": "image",
            "data": base64.b64encode(content.data).decode("ascii"),
            "mimeType": content.media_type,
        }],
        "isError": False,
    }
```

The tool handler returns this result through the host's content channel. Keep
image blocks typed as images when forwarding them to the model. Encoding the
whole result as text would expose base64 text rather than an image. A notebook
image display and a saved file are separate from this model-facing delivery.

Inspect the delivered image before reporting visual findings. Snapshot diffs,
scroll offsets, and geometry provide additional behavioral evidence.

## Bound browser work

Use `AsyncBrowser` with the host's asyncio task management. Cancellation waits
for the active native command to settle, and queued cancelled commands are
skipped. See [Async applications](/guides/async).

`SessionOptions.timeout` configures engine operation timeouts in seconds.
Explicit wait methods accept milliseconds. For raw commands, `_timeoutMs`
bounds dispatch and includes time spent in the async queue. See
[Native protocol](/guides/native-protocol). A cancelled or timed-out command
can have browser effects that were already sent. Inspect current page state
before retrying a mutation.
