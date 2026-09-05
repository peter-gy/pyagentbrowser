---
title: Snapshots and action evidence
description: Learn how accessibility snapshots, scoped refs, waits, diffs, and live queries represent page interaction.
---

# Snapshots and action evidence

`Browser.observe()` returns an immutable `Snapshot` of the active page's [accessibility tree](https://developer.mozilla.org/en-US/docs/Glossary/Accessibility_tree). The tree represents semantic roles, accessible names, states, and relationships used by assistive technology. Interactive nodes carry ref IDs such as `e1`. Each `Ref` is scoped to the snapshot that produced it.

```python
from agentbrowser import Browser, SnapshotSpec

spec = SnapshotSpec(compact=True, urls=True)

with Browser.launch() as browser:
    browser.open("https://example.com")
    snapshot = browser.observe(spec)

    print(snapshot.text)
    print(snapshot.refs)
```

`SnapshotSpec` controls an optional selector, interactive-node filtering, compact output, maximum depth, and URL inclusion. Refreshes and ref actions reuse the same specification.

Focused snippets that start from `snapshot` or `link` are partial. Run them inside an active `Browser` context such as the preceding example.

## Select refs from observed content

Use `one()` when one match is part of the workflow contract:

```python
link = snapshot.one(role="link", name="Learn more")
```

`one()` raises `LookupError` for zero or several matches. Use `all()` when the page can contain several matching elements. `ref("e1")` and `ref("@e1")` select an exact ref ID.

## A ref mutation captures a transition

```python
from agentbrowser import Wait

result = link.click(wait=Wait.url("*://www.iana.org/*"))

print(result.before.origin)
print(result.after.origin)
print(result.diff.text)
```

The operation runs in this order:

1. **Mutate.** Run the native action against the ref selector.
2. **Wait.** Apply the requested text, URL, load, or combined conditions.
3. **Observe.** Capture the next snapshot with the source specification.
4. **Diff.** Compare each snapshot origin and accessibility text, then return `ActionResult`.

If the mutation succeeds and a later stage fails, `ActionTransitionError` reports `stage`, `before`, optional `after`, and `cause`. Treat the page mutation as completed when handling this error.

## Refresh an expired ref

Page replacement can expire native element identity. A stale action raises `StaleRefError`.

```python
from agentbrowser import StaleRefError

try:
    result = link.click()
except StaleRefError as error:
    result = error.refresh().click()
```

`refresh()` captures a new snapshot and resolves the accessible role and name again. Pass new criteria when the page changed the element's accessible identity.

## Use a live query for direct control

```python
from agentbrowser import Browser

with Browser.launch() as browser:
    browser.page.set_content("""
        <label>Email <input id="email"></label>
        <button type="button">Continue</button>
    """)
    browser.find.label("Email").fill("ada@example.com")
    browser.find.role("button", name="Continue").click()
```

A `Query` resolves against the live document when each operation runs. Query mutations return the query for chaining. Query reads return a direct value.

| Contract | Snapshot-scoped `Ref` | Live `Query` |
| --- | --- | --- |
| Resolution time | Snapshot capture | Each operation |
| Mutation result | `ActionResult` | Query for chaining |
| Before-and-after evidence | Captured automatically | Capture separately |
| Stale identity | Refresh against a new snapshot | Locator resolves again |

Use [Interact with pages](/guides/interact) for complete ref and query workflows.
