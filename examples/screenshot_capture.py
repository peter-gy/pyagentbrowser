from agentbrowser import Browser

with Browser.launch() as browser:
    browser.page.open("https://example.com")
    screenshot = browser.page.capture.screenshot("example.png")
    print(screenshot.path)
