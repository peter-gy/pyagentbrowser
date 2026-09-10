---
title: Migrate to scoped browser agents
description: Update code-mode controller lifecycle, frame operations, and screenshot delivery to the scoped API.
---

# Migrate to scoped browser agents

The scoped API gives each browser operation an explicit page or frame handle.
Update controller lifecycle, frame selection, and screenshot delivery together.

## Move document operations to `browser.page`

```python
browser.page.open("https://example.com")
snapshot = browser.page.observe()
browser.page.find.role("button", name="Save").click()
screenshot = browser.page.capture.screenshot("artifacts/page.png")
```

The `Browser` owns lifecycle, tabs, session policy, storage, network, and raw
native access. The `Page` owns navigation, reading, evaluation, waits, queries,
snapshots, scrolling, geometry, frames, and capture.

## Create and retrieve controllers explicitly

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

## Carry frame scope through a handle

```python
preview = browser.page.frames.get(selector="iframe[title='Preview']")
preview.wait_for_text("Ready")
snapshot = preview.observe()
print(preview.evaluate("document.title"))
```

Replace ambient frame selection with `Page.frames.get()`. Move observation,
queries, evaluation, waits, scrolling, geometry, and capture to the returned
`Frame`. Return to the main document by using `browser.page`.

## Deliver screenshot bytes through the host

```python
host = agentbrowser.current_host()
screenshot = preview.capture.screenshot("artifacts/preview.png")
delivery = host.emit_image(screenshot.content())
```

`Screenshot.content()` returns dependency-free image bytes and MIME type. A
notebook frontend can render the `Screenshot` object through its standard image
display protocol. An agent host uses `emit_image()` to submit image content to
the model. Record the model's visual assessment separately from the delivery
receipt.
