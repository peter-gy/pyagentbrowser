# Quickstart

## Open a page

```python
from pyagentbrowser import Browser

with Browser(headless=True) as browser:
    browser.page.open("https://example.com")
    page = browser.agent.observe()
    print(page.text)

    browser.find.text("More information").click()
    print(browser.page.url())
```

## Use selectors

```python
from pyagentbrowser import Browser

with Browser(headless=True) as browser:
    browser.page.open("https://example.com")
    browser.find.text("More information").click()
    browser.find.css("h1").wait()
    print(browser.find.xpath("//h1").text())
```

## Use snapshot refs

```python
from pyagentbrowser import Browser

with Browser(headless=True) as browser:
    browser.launch()
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

## Capture a screenshot

```python
from pyagentbrowser import Browser

with Browser(headless=True) as browser:
    browser.page.open("https://example.com")
    shot = browser.capture.screenshot("page.png", full_page=True)
    print(shot.path)
```

Install `pyagentbrowser[images]` to access `shot.image` and `shot.pil()`.
Headless Chromium screenshots hide native scrollbars by default. Construct
`Browser(hide_scrollbars=False)` when scrollbars are part of the artifact.

## Async

```python
from pyagentbrowser import AsyncBrowser

async with AsyncBrowser(headless=True) as browser:
    await browser.page.open("https://example.com")
    page = await browser.agent.observe()
    print(page.text)
```

## Attach to running Chrome

```python
import pyagentbrowser as ab

browser = ab.configure(cdp_port=9222)
print(browser.tabs.list())
```

`Browser(cdp_port=...)` stays lazy until first use. Call `browser.connect()` to
perform the same no-navigation handshake explicitly.
For notebook recovery after an interrupted run, use `ab.reset(force=True)` or
`ab.configure(..., force=True)` to discard a stale default browser.

## Notebook scratchpad helpers

```python
browser.tabs.open("https://example.com", label="scratch")
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
