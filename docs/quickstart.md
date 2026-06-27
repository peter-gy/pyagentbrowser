# Quickstart

## Open a page

```python
from agentbrowser import Browser

with Browser.launch({"headless": True}) as browser:
    browser.page.open("https://example.com")
    page = browser.agent.observe()
    print(page.text)
```

## Read page content

```python
from agentbrowser import Browser, ReadMode

with Browser.launch({"headless": True}) as browser:
    result = browser.page.read(
        "https://example.com",
        mode=ReadMode.markdown(require=True),
    )
    print(result.content)
```

`page.read()` returns `ReadResult` with the original URL, final URL, content
type, source, truncation flag, and extracted content. Omit the URL to read the
active page.

## Use selectors

```python
from agentbrowser import Browser

with Browser.launch({"headless": True}) as browser:
    browser.page.open("https://example.com")
    print(browser.find.xpath("//h1").text())

    browser.find.text("Learn more").click()
    browser.page.wait_for_url("*://www.iana.org/*")
    print(browser.page.url())
```

## Use snapshot refs

```python
from agentbrowser import Browser

with Browser.launch({"headless": True}) as browser:
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
from agentbrowser import Browser

with Browser.launch({"headless": True}) as browser:
    browser.page.open("https://example.com")
    shot = browser.capture.screenshot("page.png", full_page=True)
    print(shot.path)
```

Install `pyagentbrowser[images]` to access `shot.image` and `shot.pil()`.
Headless Chromium screenshots hide native scrollbars by default. Construct
`Browser.launch({"hide_scrollbars": False})` when scrollbars are part
of the artifact.

## Async

```python
from agentbrowser import AsyncBrowser

browser = await AsyncBrowser.launch({"headless": True})
async with browser:
    await browser.page.open("https://example.com")
    page = await browser.agent.observe()
    print(page.text)
```

## Attach to running Chrome

```python
import agentbrowser as ab

browser = ab.configure(attach={"port": 9222})
browser.connect()
print(browser.tabs.list())
```

`attach` keeps target selection separate from browser process launch options.
Call `browser.connect()` to perform the no-navigation handshake.
For notebook recovery after an interrupted run, use `ab.reset(force=True)` or
`ab.configure(..., force=True)` to discard a stale default browser.

More examples live in [`examples/`](../examples/).
