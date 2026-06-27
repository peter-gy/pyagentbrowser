"""Requires `pyagentbrowser[cdp]`."""

from pyagentbrowser import Browser, LaunchOptions

HTML = """
<main>
  <h1>Host page</h1>
  <iframe
    id="details"
    name="details"
    srcdoc="<title>Details</title><h1>Frame details</h1>"
  ></iframe>
</main>
"""

with Browser.launch(LaunchOptions(headless=True)) as browser:
    browser.page.set_content(HTML)

    for frame in browser.cdp.frames.list():
        print(frame.name, frame.url)

    details = browser.cdp.frames.get(selector="#details")
    print(details.evaluate("document.title"))
