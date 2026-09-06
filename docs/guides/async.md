---
title: Use pyagentbrowser in async applications
description: Run the same browser contract through AsyncBrowser while keeping native work ordered and shutdown explicit.
---

# Use pyagentbrowser in async applications

`AsyncBrowser` mirrors the browser, snapshot, ref, query, and capability namespace APIs. Operations that call the engine are awaitable. Handle construction and immutable snapshot lookup remain synchronous.

```python
import asyncio

from agentbrowser import AsyncBrowser, Wait


async def main() -> None:
    async with await AsyncBrowser.launch() as browser:
        await browser.open("https://example.com")
        snapshot = await browser.observe()
        link = snapshot.one(role="link", name="Learn more")
        result = await link.click(
            wait=Wait.url("*://www.iana.org/*")
        )
        print(result.after.origin)


asyncio.run(main())
```

## Shared semantics

The synchronous and asynchronous surfaces use the same method names, parameters, result models, validation, confirmation behavior, domain policy, and evidence model.

The intentional differences are:

- Engine operations return awaitables.
- Query factories and snapshot lookups stay synchronous because they create handles or inspect immutable data.
- `AsyncBrowser.close(*, timeout=5.0)` adds a shutdown timeout in seconds.
- Native work is serialized through one owner thread so the event loop stays available.

## Cancellation and close

Canceling an await prevents queued work that has not started. Native work already in progress runs through its owner.

`close()` is single-flight. Concurrent callers share the same terminal result or terminal error. Closing rejects queued operations with `RuntimeError`, requests native shutdown, and joins the owner thread.

A native shutdown timeout raises `TimeoutError`. A worker that remains alive after the join raises `RuntimeError`. The first close call fixes the timeout shared by later callers.

## Confirmation

`AsyncPendingAction.confirm()` and `deny()` are awaitable. Confirmation preserves typed decoding and any remaining wait, snapshot, and diff work for the initiating operation.

```python
from agentbrowser import AsyncBrowser, ConfirmationRequired, SessionOptions


async def publish() -> None:
    session = SessionOptions(confirm_actions=("click",))
    async with await AsyncBrowser.launch(session=session) as browser:
        await browser.page.set_content("<button>Publish</button>")
        snapshot = await browser.observe()
        try:
            await snapshot.one(role="button", name="Publish").click()
        except ConfirmationRequired as required:
            await required.pending.confirm()
```

Use [Browser controllers](/reference/browser) and [Capability namespaces](/reference/namespaces) for the shared contract. Async counterparts preserve the same order and return shapes.
