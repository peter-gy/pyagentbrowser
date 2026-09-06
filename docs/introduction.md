---
title: What is pyagentbrowser?
description: Learn the objects and boundaries that make up the pyagentbrowser Python SDK.
---

# What is pyagentbrowser?

pyagentbrowser embeds the native Rust [`agent-browser`](https://agent-browser.dev/) engine in a Python process. The `pyagentbrowser` distribution installs the `agentbrowser` import package, a typed Python API, the native engine, browser lifecycle management, safety policy, and action evidence.

The central object is a `Browser` controller. It owns a native session, which sends ordered actions to a local browser process or an attached browser. The controller exposes the active tab through focused namespaces such as `page`, `tabs`, `capture`, and `network`.

## The core objects

| Object | Role |
| --- | --- |
| `Browser` | The synchronous Python controller. `AsyncBrowser` exposes the same browser contract with awaitable operations. |
| Native session | The ordered command and policy boundary owned by one controller. |
| Active tab | The page target used by browser methods until a tab operation selects another target. |
| `Snapshot` | An immutable observation of the browser accessibility tree, including the semantic roles, names, states, and relationships exposed for assistive technology. |
| `Ref` | An element identity scoped to the snapshot that produced it. |
| `Query` | An element lookup resolved against the live document each time an operation runs. |
| `ActionResult` | The source snapshot, resulting snapshot, target ref, action name, and snapshot diff from one completed ref mutation. |

## One interaction, end to end

```python
from agentbrowser import Browser, Wait

with Browser.launch() as browser:
    browser.open("https://example.com")
    snapshot = browser.observe()
    link = snapshot.one(role="link", name="Learn more")
    result = link.click(wait=Wait.url("*://www.iana.org/*"))

    print(result.before.origin)
    print(result.after.origin)
    print(result.diff.changed)
```

`Browser.launch()` starts the browser before returning. `observe()` records the current accessibility tree. `Snapshot.one()` selects exactly one ref. `Ref.click()` performs the mutation, waits for the new URL, captures another snapshot with the same specification, and returns the transition evidence.

## Two element models

Use a `Ref` when the workflow needs evidence tied to the page state the agent inspected. A ref mutation produces an `ActionResult`.

Use a `Query` when direct live-page control is the goal. A query resolves when each operation runs and returns the query or requested value.

| Need | Element model | Result |
| --- | --- | --- |
| Explain what changed after an action | Snapshot-scoped `Ref` | `ActionResult` with before, after, and diff |
| Reuse a locator across live page updates | `Query` | Direct mutation or value |
| Revisit an element after its snapshot expires | Ref refreshed against a new snapshot | New `Ref` |

## Product boundaries

The typed API owns stable Python workflows, input validation, result decoding, safety checks, and cleanup. `browser.native` exposes every action in the pinned engine through its JSON protocol while retaining those controller boundaries.

The accessibility tree is derived from the document and rendered semantics. It is smaller than the Document Object Model because it focuses on perceivable and operable content. [MDN explains how browsers build this representation](https://developer.mozilla.org/en-US/docs/Glossary/Accessibility_tree).

The optional `browser.cdp` API opens a direct [Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/) connection for page targets, frames, execution contexts, evaluation, and raw protocol methods.

Continue with [Why pyagentbrowser?](/why) for the design rationale or [Get started](/getting-started) for the first complete session.
