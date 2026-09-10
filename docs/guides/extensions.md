---
title: Compose extensions
description: Add typed browser capabilities with checked commands and document-scoped executors.
---

# Compose extensions

`browser.extension(factory)` and `document.extension(factory)` construct a
capability with a checked command executor. A document executor retains its
page and frame identity. Use an ordinary Python class to group an application's
browser operations.

```python
from collections.abc import Mapping
from dataclasses import dataclass

from agentbrowser import Browser, Command, Executor, NativeParseError


def decode_count(data: Mapping[str, object]) -> int:
    value = data.get("result")
    if type(value) is not int:
        raise NativeParseError("evaluate: result must be an integer")
    return value


def heading_count() -> Command[int]:
    return Command(
        "evaluate",
        {"script": "document.querySelectorAll('h1').length"},
        decode=decode_count,
    )


@dataclass
class Headings:
    executor: Executor

    def count(self) -> int:
        return self.executor.execute(heading_count())


with Browser() as browser:
    browser.page.set_content("<h1>Orders</h1><h1>Returns</h1>")
    headings = browser.page.extension(Headings)
    print(headings.count())  # 2
```

Local browser startup finds Chrome or downloads Chrome for Testing when needed.
See [Get started](/getting-started) for installation and browser requirements.
The command uses the pinned engine's native action and parameter names. Check
the [native protocol guide](/guides/native-protocol) when using another action.

## Share commands across sync and async APIs

Reuse `heading_count()` and `decode_count()` from the synchronous example.
The asynchronous capability awaits its executor and returns the same result:

```python
import asyncio

from agentbrowser import AsyncBrowser, AsyncExecutor


@dataclass
class AsyncHeadings:
    executor: AsyncExecutor

    async def count(self) -> int:
        return await self.executor.execute(heading_count())


async def main() -> None:
    async with AsyncBrowser() as browser:
        await browser.page.set_content("<h1>Orders</h1><h1>Returns</h1>")
        headings = browser.page.extension(AsyncHeadings)
        print(await headings.count())  # 2


asyncio.run(main())
```

## Select scope before construction

Construct a session-wide capability with `browser.extension(factory)`. Construct
a capability for one document with `page.extension(factory)` or
`frame.extension(factory)`. A retained document capability keeps that document
identity when another tab becomes active.

The executor retains its resource owner. Keep the browser lifecycle explicit
with a context manager or `close()`. Closing the browser makes every capability
sharing that owner terminal.

## Executor contract

| Member | Behavior |
| --- | --- |
| `Command(action, params={}, decode=...)` | Describe one checked native action. The default decoder returns the native data mapping. |
| `Executor.execute(command)` | Check the native response and decode its data into the command's result type. |
| `AsyncExecutor.execute(command)` | Await checked execution through the ordered native worker. |
| `executor.scope` | Return the executor's current `DocumentScope`. |
| `executor.generation` | Return the current native ref-map generation. |
| `executor.bind(scope, *, ref_generation=None)` | Return an executor for an explicit document identity and optional captured ref generation. |

Checked commands inherit launch preparation, policy, confirmation, execution
limits, and terminal close. A paused command retains its decoder on
`ConfirmationRequired.pending`. Confirming it returns the decoded value.
If a capability composes several commands, it must retain the remaining work
across any confirmation boundary. See [Safety](/concepts/safety).

Use `browser.native.execute()` when the caller needs the full native response
envelope. Use extensions when the caller needs a typed result or a reusable
operation. Import `Command`, `Executor`, and `AsyncExecutor` from `agentbrowser`.
