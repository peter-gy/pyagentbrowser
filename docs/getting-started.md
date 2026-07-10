# Get started

pyagentbrowser runs the native `agent-browser` engine inside a Python process. A browser session can launch local Chrome, attach to an existing CDP target, or restore saved browser state.

## Install

Install the package with uv or pip:

```bash
uv add pyagentbrowser
```

```bash
python -m pip install pyagentbrowser
```

The package supports Python 3.11 through 3.14 on macOS, Linux, and x86-64 Windows.

## Open a page

`Browser.launch()` starts the native session before it returns. Use the browser as a context manager so its browser process, stream, and dashboard resources close together.

```python
from agentbrowser import Browser, Wait

with Browser.launch() as browser:
    browser.open("https://example.com")
    page = browser.observe()

    result = page.one(role="link", name="Learn more").click(
        wait=Wait.url("*://www.iana.org/*")
    )

    print(result.after.text)
```

The example has four public objects:

- `Browser` owns the native session and active page.
- `Snapshot` records an accessibility tree and its element refs.
- `Ref` identifies one element in that snapshot.
- `ActionResult` records the ref, the snapshots before and after the action, and their diff.

`Snapshot.one()` raises `LookupError` when its criteria match zero or several refs. Use `Snapshot.all()` when several results are expected.

## Use a live query

`browser.find` resolves its selector when each action runs. It is a direct path for CSS, XPath, role, text, label, placeholder, alt-text, title, and test-id queries.

```python
from agentbrowser import Browser

with Browser.launch() as browser:
    browser.page.set_content("""
        <label>Email <input id="email"></label>
        <button type="button">Continue</button>
    """)
    browser.find.css("#email").fill("ada@example.com")
    browser.find.role("button", name="Continue").click()
```

Use snapshot refs when the workflow needs transition evidence. Use live queries for direct page control.

## Run asynchronously

`AsyncBrowser` mirrors the browser, snapshot, ref, query, and capability APIs. Native work runs on one ordered owner thread while the event loop remains available.

```python
import asyncio

from agentbrowser import AsyncBrowser, Wait


async def main() -> None:
    browser = await AsyncBrowser.launch()
    async with browser:
        await browser.open("https://example.com")
        page = await browser.observe()
        result = await page.one(role="link", name="Learn more").click(
            wait=Wait.url("*://www.iana.org/*")
        )
        print(result.after.text)


asyncio.run(main())
```

`AsyncBrowser.close(*, timeout=5.0)` is idempotent. It rejects queued calls with `RuntimeError` and waits up to the timeout for active native shutdown. A shutdown timeout raises `TimeoutError`. A worker that remains alive after the join raises `RuntimeError`.

## Attach to Chrome

Start Chrome with remote debugging enabled, then select its port or WebSocket URL with `CDPTarget`.

```python
from agentbrowser import Browser, CDPTarget

with Browser.attach(CDPTarget(port=9222)) as browser:
    print(browser.title())
    print(browser.tabs.list())
```

`Browser.attach()` completes the CDP connection before returning. `CDPTarget` accepts exactly one `port` or `url`.

## Select a browser executable

Local launches search the native browser cache, system Chrome and Chromium installations, and browser caches maintained by Puppeteer or Playwright. The native installer prepares Chrome for Testing when those searches miss.

Call `ensure_installed()` when setup should happen before session construction:

```python
from agentbrowser import ensure_installed

installed = ensure_installed()
print(installed.executable_path)
```

Pass `LaunchOptions` to select a browser or configure the launch:

```python
from agentbrowser import Browser, LaunchOptions

launch = LaunchOptions(
    executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    headless=True,
)

with Browser.launch(launch) as browser:
    browser.open("https://example.com")
```

## Optional packages

Install `images` for Pillow-backed screenshot methods:

```bash
uv add "pyagentbrowser[images]"
```

Install `cdp` for frame, target, execution-context, and raw CDP APIs:

```bash
uv add "pyagentbrowser[cdp]"
```

Continue with the [guides](guides.md) for snapshots, policy, saved state, capture, and native protocol access. Use the [API reference](api.md) for signatures and return types.
