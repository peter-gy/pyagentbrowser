---
title: Troubleshooting
description: Diagnose browser launch, attachment, stale identity, timeout, persistence, optional package, and cleanup failures.
---

# Troubleshooting

Start with the exception type and the resource boundary it names. `BrowserError` preserves the native action, response, and structured error code.

## A local browser fails to launch

Call the installer before constructing the session:

```python
from agentbrowser import ensure_installed

result = ensure_installed(progress=True)
print(result.source, result.executable_path)
```

Set `AGENT_BROWSER_EXECUTABLE_PATH` or `LaunchOptions.executable_path` when discovery should use one known executable. A download failure raises `BrowserInstallError` with installer output.

On displayless Linux hosts, headed mode uses [Xvfb](https://www.x.org/releases/current/doc/man/man1/Xvfb.1.xhtml), a virtual X display server, by default. `LaunchOptions(no_xvfb=True)` requires an available display.

## The engine reports a warning

Typed methods and `browser.native.data()` emit an `EngineWarning` through Python's [`warnings`](https://docs.python.org/3/library/warnings.html) module when the engine attaches an advisory to a response. The engine warns when Chrome is behind the current stable release and the newer releases fixed CVEs, and when a JavaScript dialog blocks the page.

```python
import warnings

from agentbrowser import EngineWarning

warnings.filterwarnings("error", category=EngineWarning, message="A JavaScript .* dialog")
```

Run `ensure_installed()` or update the selected Chrome to clear the release warning. The engine checks each launched browser once by requesting the Chrome release feed from `chromereleases.googleblog.com` with a three-second timeout. Set `AGENT_BROWSER_NO_VERSION_CHECK=1` to skip that request. `browser.native.execute()` returns the same text in `BrowserResponse.warning` without emitting a Python warning.

## Attachment cannot select a tab

Confirm that the remote-debugging port or WebSocket URL belongs to the intended browser. `agentbrowser.CDPTarget` accepts exactly one endpoint.

Attachment selects a responsive page target. If every renderer is discarded, it attempts to reactivate the first one. A remaining failure raises `BrowserError`.

For a pinned attached session, `BrowserError.code == "tab_gone"` means another client closed the bound page target. Inspect `error.response["data"]` for the target ID and optional last URL before choosing a recovery tab.

## A download fails on an attached browser

`browser.downloads` saves files only from a browser this session launched. On a session created with `Browser.attach()`, an environment CDP target, or a provider, the remote endpoint names the saved file, so the engine rejects the download with a `BrowserError`. Launch a local browser for download workflows.

## A tab closed during a command

A command whose tab or frame closes before Chrome answers fails at once with a `BrowserError` whose message contains `Target closed: CDP session <id> detached`. List the remaining tabs with `browser.tabs.list()` and continue on one of them.

## A tab stopped responding

`BrowserError.code == "page_wedged"` means the active tab did not answer before the command timeout. `error.response["data"]` contains the `targetId`, `replaced`, and an optional `lastUrl`. In a launched browser, a second timeout on the same tab replaces it with a blank tab and reports `replaced: True` with its `newTargetId`. Open the page again to continue. Refs and frame handles from the replaced tab are expired.

## A ref became stale

A `Ref` belongs to its source snapshot. Refresh it against the current page:

```python
from agentbrowser import StaleRefError

try:
    result = save.click()
except StaleRefError as error:
    result = error.refresh().click()
```

Pass new role, name, or text criteria when the accessible identity changed.

## A direct CDP handle became stale

Navigation, document replacement, history movement, tab changes, new windows, browser relaunch, URL-based accessibility audits, and close invalidate cached direct CDP page state.

Resolve the frame or execution context again. A direct page-target handle resolves its selected target when each operation runs. `CDPStaleObjectError` indicates that a frame or execution-context handle belongs to an older controller generation.

## An action completed before an error

`ActionTransitionError` means the ref mutation succeeded and its wait, resulting snapshot, or diff failed later.

```python
try:
    result = submit.click(wait=wait)
except ActionTransitionError as error:
    print(error.stage)
    print(error.before.text)
    print(error.after.text if error.after else "no resulting snapshot")
```

Treat the mutation as completed before deciding whether to retry.

## A call requires confirmation

Typed methods and `browser.native.data()` raise `ConfirmationRequired`. Resume or deny the specific pending operation:

```python
try:
    result = action()
except ConfirmationRequired as required:
    result = required.pending.confirm()
```

`browser.native.execute()` preserves the confirmation-required response as a raw envelope for protocol-level callers.

## Restore persistence failed during close

`RestoreSaveError` is raised after browser cleanup. Inspect its terminal result:

```python
try:
    browser.close()
except RestoreSaveError as error:
    print(error.result.save_status)
    print(error.result.save_error)
```

The controller is closed even when persistence failed.

## An optional feature raises `ImportError`

- Install `pyagentbrowser[images]` for Pillow-backed screenshot methods.
- Install `pyagentbrowser[cdp]` for direct CDP APIs.

Direct CDP import errors report the installed version and loaded module paths. Restart the Python
process after changing the `websockets` installation. Reloading one networking
module can leave package classes and constants out of sync.

## A timeout uses the wrong scale

Browser operation fields ending in `_ms` use milliseconds. `SessionOptions.timeout`, async close timeout, and direct CDP client timeout use seconds.

An explicit native `_timeoutMs` also bounds dispatch, including time spent in
the async queue. Expiry before dispatch raises `TimeoutError`. An active command
that exceeds its budget raises `BrowserError` with `code="execution_timeout"`.
Inspect page state before retrying a mutation.

## Commands fail after close

`close()` is terminal. Create a new controller for later work. Repeated calls return the cached result after success or re-raise the cached close error. Other commands raise `RuntimeError`.

Use `browser.session.status()` before close to inspect native session, browser, and restore state. Use `browser.native.execute()` when the raw response envelope is needed for diagnosis.
