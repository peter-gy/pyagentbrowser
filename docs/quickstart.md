# Quickstart

## Open a page

```python
from pyagentbrowser import Browser, LaunchOptions

with Browser.launch(LaunchOptions(headless=True)) as browser:
    browser.page.open("https://example.com")
    page = browser.agent.observe()
    print(page.text)
```

## Read page content

```python
from pyagentbrowser import Browser, LaunchOptions, ReadMode

with Browser.launch(LaunchOptions(headless=True)) as browser:
    browser.page.set_content("<article><h1>Guide</h1><p>Read this page.</p></article>")
    result = browser.page.read(mode=ReadMode.markdown(require=True))
    print(result.content)
```

`page.read()` returns `ReadResult` with the original URL, final URL, content
type, source, truncation flag, and extracted content. Omit the URL to read the
active page.

## Use selectors

```python
from pyagentbrowser import Browser, LaunchOptions

with Browser.launch(LaunchOptions(headless=True)) as browser:
    browser.page.set_content(
        """
        <main>
          <h1>Account settings</h1>
          <a href="#billing">Billing</a>
        </main>
        """
    )
    browser.find.text("Billing").click()
    browser.find.css("h1").wait()
    print(browser.find.xpath("//h1").text())
```

## Use snapshot refs

```python
from pyagentbrowser import Browser, LaunchOptions

with Browser.launch(LaunchOptions(headless=True)) as browser:
    browser.page.set_content(
        """
        <label>Email <input aria-label="Email" /></label>
        <label>Password <input aria-label="Password" type="password" /></label>
        <button>Continue</button>
        <p aria-live="polite"></p>
        <script>
        document.querySelector("button").addEventListener("click", () => {
          document.querySelector("p").textContent = "Signed in"
        })
        </script>
        """
    )
    page = browser.agent.observe()

    page.find(name="Email").fill("ada@example.com")
    page.find(name="Password").fill("correct horse battery staple")
    evidence = page.find(role="button", name="Continue", exact=True).click_and_observe(
        wait_for_text="Signed in"
    )

    print(evidence.after.text)
    print(evidence.diff.changed)
```

Refs are scoped to the snapshot that produced them. After navigation or large DOM
changes, observe again.

## Restore a session

```python
import pyagentbrowser as ab
from pyagentbrowser import Browser, RestoreOptions

session_id = ab.session_id(prefix="example").session

with Browser.from_session(
    session_id,
    restore=RestoreOptions(key=session_id, check_text="Example Domain"),
) as browser:
    browser.page.open("https://example.com")
    print(browser.restore.info()["restoreStatus"])
```

Use `ab.session_id(prefix="my-app")` to derive a stable session id
from the current worktree without creating a browser.

## Capture a screenshot

```python
from pyagentbrowser import Browser, LaunchOptions

with Browser.launch(LaunchOptions(headless=True)) as browser:
    browser.page.open("https://example.com")
    shot = browser.capture.screenshot("page.png", full_page=True)
    print(shot.path)
```

Install `pyagentbrowser[images]` to access `shot.image` and `shot.pil()`.
Headless Chromium screenshots hide native scrollbars by default. Construct
`Browser.launch(LaunchOptions(hide_scrollbars=False))` when scrollbars are part
of the artifact.

## Async

```python
from pyagentbrowser import AsyncBrowser, LaunchOptions

browser = await AsyncBrowser.launch(LaunchOptions(headless=True))
async with browser:
    await browser.page.open("https://example.com")
    page = await browser.agent.observe()
    print(page.text)
```

## Attach to running Chrome

```python
import pyagentbrowser as ab
from pyagentbrowser import CDPAttach

browser = ab.notebook.configure(attach=CDPAttach(port=9222))
browser.connect()
print(browser.tabs.list())
```

`CDPAttach` keeps attachment target selection separate from browser process
launch options. Call `browser.connect()` to perform the no-navigation handshake.
For notebook recovery after an interrupted run, use `ab.notebook.reset(force=True)` or
`ab.notebook.configure(..., force=True)` to discard a stale default browser.

## Notebook scratchpad helpers

```python
from pyagentbrowser import Browser, LaunchOptions

with Browser.launch(LaunchOptions(headless=True)) as browser:
    browser.tabs.open("about:blank", label="scratch")
    browser.page.set_content(
        """
        <main>
          <h1>Scratch page</h1>
          <a href="#details">More information</a>
        </main>
        """
    )
    browser.page.ready(timeout_ms=15_000)
    heading = browser.find.xpath("//h1").text()
    href = browser.find.xpath("//a[contains(., 'More information')]").attribute("href")
    shot = browser.capture.screenshot("page.png")
```

`tabs.open(..., label=...)` reuses the labelled tab when it already exists.
`page.ready()` waits for readable body text. `find.xpath()` accepts the same
XPath selector style as the native engine's `xpath=` selectors. Notebook
frontends that support rich display render `shot` as image data.

More examples live in [`examples/`](../examples/).
