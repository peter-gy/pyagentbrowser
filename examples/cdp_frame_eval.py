from pyagentbrowser import Browser

with Browser(headless=True) as browser:
    browser.page.open("https://example.com")

    for frame in browser.frames.list():
        print(frame.name, frame.url)

    print(browser.cdp.evaluate("document.title"))
