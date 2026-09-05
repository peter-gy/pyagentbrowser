---
title: Why pyagentbrowser?
description: Understand why pyagentbrowser combines a native browser engine with Python-owned lifecycle, evidence, and safety policy.
---

# Why pyagentbrowser?

Browser automation for agents has to answer more than whether a click returned successfully. The caller also needs to know what page state the agent inspected, what changed after the action, which browser resources remain active, and which targets the session may reach.

pyagentbrowser makes those questions part of the Python contract.

## Keep the engine in the Python process

The native `agent-browser` engine is embedded in the installed extension. A `Browser` controller calls it directly through an ordered native session.

| Problem | Mechanism | Observable consequence |
| --- | --- | --- |
| A separate browser CLI or service has its own process and connection lifecycle | The native engine is embedded through [PyO3](https://pyo3.rs/), the Rust-to-Python binding layer | The controller owns startup, ordered calls, status, and terminal cleanup |
| Agents need evidence tied to the state they inspected | Snapshots create scoped refs and ref actions capture the next snapshot | Each ref mutation can be reviewed as a before-and-after transition |
| A narrow high-level API can hide engine capabilities | Typed namespaces sit beside `browser.native` | Common workflows stay discoverable and new native actions remain reachable |
| Browser automation crosses network and credential boundaries | Domain containment, action policy, and confirmation run inside the session | Safety checks remain attached to typed and raw native calls |

## Make page state explicit

An accessibility snapshot records the page structure used to select an element. A ref remains attached to that snapshot. This creates a concrete chain from observation to target to action.

```text
Snapshot A
  -> Ref "Submit"
  -> click and wait
  -> Snapshot B
  -> SnapshotDiff(A, B)
```

A live query offers a separate contract for workflows that need a locator resolved at execution time. The distinction lets callers choose evidence or direct control deliberately.

## Own browser resources as one lifecycle

The controller tracks the native session, browser process or attachment, current tab state, direct CDP handles, confirmation context, dashboard stream, and restore result. `close()` releases the owned resources and returns terminal persistence evidence.

The asynchronous controller keeps native calls ordered on one owner thread while the Python event loop remains available. Concurrent close calls share one terminal result.

## Keep the Python surface focused

The SDK promotes a native action when Python can provide a stable workflow, validation, a typed result, or lifecycle behavior. The remaining engine surface stays available through:

```python
from agentbrowser import Browser

with Browser.launch() as browser:
    data = browser.native.data("stream_status")
```

`data()` checks success and returns response data. Use `execute()` when the application needs to preserve the complete response envelope.

Read [the runtime model](/concepts/runtime-model) before combining sessions, restored state, tabs, or direct protocol access.
