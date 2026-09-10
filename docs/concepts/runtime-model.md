---
title: Runtime model
description: Learn how controllers, native sessions, browser processes, tabs, frames, and stored state fit together.
---

# Runtime model

A `Browser` or `AsyncBrowser` controller owns one native session. The session orders native actions, applies policy, tracks lifecycle state, and controls a local browser process or an attached browser endpoint.

```text
Browser or AsyncBrowser controller
  -> native session
     -> local browser process or attached browser endpoint
        -> page handle
           -> main document or frame handle
```

## Canonical terms

| Term | Meaning |
| --- | --- |
| Controller | The Python `Browser` or `AsyncBrowser` object used by application code. |
| Native session | The ordered command, policy, identity, and persistence boundary owned by the controller. |
| Browser process | A locally launched Chrome or Chromium process. An attached endpoint is externally owned. |
| Page | A handle bound to one browser page target. Acquire the configured or active target through `browser.page`, or select one through `browser.tabs.get()`. |
| Frame | A handle bound to one child browsing context. Observation, queries, evaluation, waits, and ref actions carry its frame identity. |
| Direct CDP handle | An execution context or raw protocol target from the direct Chrome DevTools Protocol API. Context handles are generation-bound. |

## Choose a startup mode

| API | When startup happens | Browser ownership |
| --- | --- | --- |
| `Browser()` | First browser-dependent operation | Controller launches and owns the local process |
| `Browser.launch()` | Before the call returns | Controller launches and owns the local process |
| `Browser.attach(CDPTarget(...))` | Before the call returns | External owner keeps the browser process |

An explicit URL passed to `browser.page.read(url=...)` can use the engine's HTTP reader before browser startup. Reading the active document, using direct CDP, or acting on a page starts a lazy local browser.

## Operation, action, and command

A high-level operation is one Python method call. A native action is one engine behavior such as `launch`, `navigate`, or `click`. A JSON command is one serialized invocation of a native action.

Some high-level operations contain several native actions. `Browser().page.open(url)` can launch the browser and then navigate. Confirmation policy may pause either action.

## Identity and stored state

| Name | Scope | Purpose |
| --- | --- | --- |
| `SessionOptions.session_id` | Native session | Finds the same native session or pinned tab binding |
| `SessionOptions.namespace` | Native control and state paths | Separates session discovery, restore records, and tab bindings |
| `RestoreOptions.key` | Keyed restore record | Loads and periodically saves cookies and origin storage |
| Tab `label` | Open tabs in a session | Gives application code a readable tab selector |
| Tab `target_id` | Browser page target | Identifies a tab across native restarts when the browser preserves it |

`browser.storage` reads live Web Storage in the active origin. `browser.state` reads and writes explicit storage-state files. `RestoreOptions` manages an automatic keyed restore record. `browser.session.status()` reports lifecycle and persistence status.

## Terminal close

`close()` is idempotent and terminal. It releases controller-owned browser resources, dashboard and stream helpers, direct CDP clients, and retained confirmation context. It returns `CloseResult` with restore and save status.

A restore-save failure is raised as `RestoreSaveError` after cleanup completes. The error keeps the terminal result on `error.result`.

Read [Tabs and state](/guides/tabs-and-state) for persistence workflows and [Direct CDP](/guides/cdp) for protocol handle lifetimes.
