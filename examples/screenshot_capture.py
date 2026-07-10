from agentbrowser import Browser

with Browser.launch() as browser:
    browser.open("https://example.com")
    screenshot = browser.capture.screenshot("example.png")
    print(screenshot.path)
