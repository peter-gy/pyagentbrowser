"""Requires `pyagentbrowser[cdp]`."""

from agentbrowser import Browser

with Browser.launch({"headless": True}) as browser:
    browser.page.open("https://example.com")

    for frame in browser.cdp.frames.list():
        print(frame.name, frame.url)

    frame = browser.cdp.frames.list()[0]
    print(frame.evaluate("document.querySelector('h1')?.textContent"))
