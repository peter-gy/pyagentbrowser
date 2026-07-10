from agentbrowser import Browser

with Browser.launch() as browser:
    browser.open("https://example.com")
    for frame in browser.cdp.frames.list():
        title = browser.cdp.evaluate("document.title", frame=frame)
        print(frame.id, frame.url, title)
