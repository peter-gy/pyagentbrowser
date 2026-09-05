---
title: Get started
description: Install pyagentbrowser, launch a browser, and capture the before-and-after evidence from one action.
---

# Get started

Install pyagentbrowser, start a local browser, and capture the state change caused by one action.

## Install

Install the package from the [Python Package Index](https://pypi.org/project/pyagentbrowser/):

```bash
python -m pip install pyagentbrowser
```

If the project uses [uv](https://docs.astral.sh/uv/), add the same dependency with `uv add pyagentbrowser`.

Wheels support Python 3.11 through 3.14 on macOS arm64 and x86-64, [manylinux 2.28](https://peps.python.org/pep-0600/)-compatible Linux arm64 and x86-64, and Windows x86-64.

The first local launch selects `AGENT_BROWSER_EXECUTABLE_PATH`, a cached browser, or an installed Chrome or [Chromium](https://www.chromium.org/chromium-projects/) executable. When discovery finds none, pyagentbrowser downloads [Chrome for Testing](https://developer.chrome.com/blog/chrome-for-testing/), a reproducible Chrome distribution for automation. Local browsers run headlessly by default.

## Run the first action

`Browser.launch()` starts the native session and local browser before it returns. Use the controller as a context manager so controller-owned browser resources close together. A terminal persistence failure surfaces after cleanup.

```python
from agentbrowser import Browser

with Browser.launch() as browser:
    browser.page.set_content(
        "<button onclick=\"this.textContent='Done'\">Run</button>"
    )
    snapshot = browser.observe()
    result = snapshot.one(role="button", name="Run").click()

    print(result.after.one(role="button").name)
    print(result.diff.changed)
```

```text
Done
True
```

The example uses four public objects:

- `Browser` owns the native session and active tab.
- `Snapshot` records an accessibility tree and its element refs.
- `Ref` identifies one element inside its source snapshot.
- `ActionResult` records the ref, the snapshots before and after the action, and their diff.

`Snapshot.one()` raises `LookupError` when its criteria match zero or several refs. Use `Snapshot.all()` when several results are expected.

## Choose the next path

- Use [Interact with pages](/guides/interact) for live queries, ref actions, waits, input, scripts, native frames, and emulation.
- Use [Async applications](/guides/async) for awaitable browser operations and ordered shutdown.
- Use [Browser controllers](/reference/browser#construction) to attach to an existing Chrome DevTools Protocol endpoint or select a browser executable.
- Use [Environment and platforms](/reference/environment) for browser discovery, environment variables, wheel targets, and timeout units.

## Optional packages

Install `images` for Pillow image loading and conversion on `Screenshot`:

```bash
uv add "pyagentbrowser[images]"
```

Install `cdp` for direct protocol clients, page targets, frames, execution contexts, and raw methods:

```bash
uv add "pyagentbrowser[cdp]"
```

Continue with [the runtime model](/concepts/runtime-model) or [snapshots and evidence](/concepts/evidence) before combining sessions, restored state, and direct protocol access.
