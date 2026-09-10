---
title: Integrate a code-mode agent
description: Execute Python with persistent globals, explicit browser targets, and model-facing image results.
---

# Integrate a code-mode agent

`CodeSession` executes trusted Python across sequential tool calls and returns
text and image content. It binds an `AgentHost` during each call so agent code
can discover the application target, capture browser evidence, and emit image
bytes to the tool result.

## Return an image from executed code

```python
from agentbrowser import CodeSession, OpenTarget

session = CodeSession(OpenTarget("https://example.com"))
result = session.execute_code("""
from agentbrowser import Browser, current_host

with Browser() as browser:
    browser.page.set_content("<h1>Ready</h1>")
    shot = browser.page.capture.screenshot("artifacts/ready.png")
    current_host().emit_image(shot.content())
    print(browser.page.title())
""")

print(result["isError"])
print([block["type"] for block in result["content"]])
```

```text
False
['image', 'text']
```

The result follows the [Model Context Protocol tool-result shape](https://modelcontextprotocol.io/specification/2025-06-18/server/tools#tool-result).
Model Context Protocol, or MCP, lets an application expose tools and return
typed content to an agent. Forward `result["content"]` through the host's tool
content channel, preserving each block's type. An image block contains
`type="image"`, base64-encoded `data`, and `mimeType`. Serializing that block
inside a text result sends text to the model.

`ImageDelivery("queued")` acknowledges insertion into this call's result.
Record a visual assessment after the model receives the image. A notebook
frontend displaying the screenshot and the model receiving image content are
separate transport boundaries.

## Preserve Python state across calls

```python
session.execute_code("count = 40")
result = session.execute_code("count + 2")
print(result["content"])
```

```text
[{'type': 'text', 'text': '42\n'}]
```

`print()` calls and the final expression produce text. Exceptions set
`isError=True`, append the exception type and message, and preserve prior
output and assignments. Imported libraries' writes to process stdout remain
process output. Calls on one `CodeSession` must run sequentially.

Use `await session.aexecute_code(code)` for top-level `await` and
`AsyncBrowser`. The embedding application owns authentication, process
isolation, and interruption of arbitrary Python code. Executed code has the
permissions of its Python process.

## Supply the application target

Pass an `OpenTarget` when the agent should open an application URL in its own
browser. Pass an `AttachedTarget` to use an authorized connection and exact
page identity. A callback can derive either target from the current
authenticated application context.

Agent code uses the same contract for either target:

```python
import agentbrowser.agent as browser_agent
from agentbrowser import OpenTarget, current_host

target = current_host().current_target()
if isinstance(target, OpenTarget):
    browser = browser_agent.open("review", target)
else:
    browser = browser_agent.attach("review", target)

# A later call in the same Python process
browser = browser_agent.get("review")
```

Call `browser_agent.close("review")` after the final browser operation.
`browser_agent.status("review")` reports process ID, ownership, native session
ID, lifecycle, and the active target. Keep connection credentials out of URLs
used as evidence and out of printed application metadata.

## Bound browser operations by the tool deadline

`execute_code(code, timeout_ms=30_000)` gives native browser operations the
remaining call budget after reserving one second for cleanup. Time spent in
the async command queue consumes that budget. `ExecutionContext.limit()`
subtracts elapsed time and can reserve a different cleanup interval.

```python
host = current_host()
browser.page.wait_for_text(
    "Ready",
    timeout_ms=host.execution_context().limit(10_000),
)
```

An expired operation can have changed the page. Inspect the current state
before retrying a mutation, and close browser controllers explicitly.
`timeout_ms` bounds browser work. The embedding application must interrupt
arbitrary Python work at its own execution boundary.

## Keep asynchronous work observable across calls

`CodeSession.tasks` retains task handles and results on one persistent event
loop. Agent code can start work through `current_host().start_task()` and await
its result in a later asynchronous call. `aexecute_code()` reports
`managed_tasks=True`. Synchronous `execute_code()` reports `managed_tasks=False`.

```python
import asyncio

from agentbrowser import CodeSession, OpenTarget


async def main():
    session = CodeSession(OpenTarget("https://example.com"))
    try:
        await session.aexecute_code("""
from agentbrowser import AsyncBrowser, current_host

async def capture():
    async with AsyncBrowser() as browser:
        await browser.page.set_content("<h1>Ready</h1>")
        return await browser.page.capture.screenshot("artifacts/task.png")

task = current_host().start_task("capture", capture, timeout_ms=20_000)
print(task.id)
""")
        result = await session.aexecute_code("""
shot = await task.result(timeout_ms=10_000)
delivery = current_host().emit_image(shot.content())
""")
        print([block["type"] for block in result["content"]])
    finally:
        await session.close()


asyncio.run(main())
```

```text
['image']
```

`task.status()` reports the lifecycle. `await task.result(timeout_ms=...)`
leaves the task running if result retrieval times out. `await task.cancel()`
requests cancellation and waits for cleanup, then reports the actual terminal
state. An operation that handles cancellation can still complete or fail.
Use `task.report(progress=0.5, detail="Captured desktop")` to update a running
task's progress and detail.

Task execution receives its own timeout and browser budget. Return screenshots
from a task and emit them during an active code call. Background emission has
no active tool result, reports `host.image_delivery=False`, and raises
`RuntimeError`. Blocking Python code still
requires interruption by the embedding application.

Call `await session.close()` on the task's event loop before shutting it down.
Close is terminal and settles task cancellation. Application-injected browser
controllers and other resources remain owned by the application.

## Adapt an existing execution host

An existing Python executor can supply `CallbackHost` and bind it around each
tool invocation. Its target callback resolves the current application. Its
image callback receives `ImageContent` bytes and returns `ImageDelivery` after
accepting, queuing, or submitting the image. Its execution callback returns a
fresh `ExecutionContext` for that call.

`host.image_delivery` reports whether the current execution accepts images.
`CallbackHost` derives this capability from its optional `image_emitter`.

The application provides the three callbacks and its Python executor:

```python
from agentbrowser import CallbackHost, bind_host, reset_host

adapter = CallbackHost(
    target=resolve_application_target,
    image_emitter=enqueue_model_image,
    execution=current_execution_context,
)
token = bind_host(adapter)
try:
    result = execute_user_code()
finally:
    reset_host(token)
```

Returning HTML or an image path from `execute_user_code()` requires the host
to load the bytes and emit a typed image block before the model can inspect it.
`Screenshot.content()` prepares those bytes without optional dependencies.

Read [agent skills](/guides/agent-skills) to supply version-matched instructions
and [read and capture](/guides/read-and-capture) for screenshot contracts.
