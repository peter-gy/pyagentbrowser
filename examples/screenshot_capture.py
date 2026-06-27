from agentbrowser import Browser

with Browser.launch({"headless": True, "hide_scrollbars": False}) as browser:
    browser.page.open("https://example.com")
    shot = browser.capture.screenshot("page.png", full_page=True)

    print(shot.path)
    print(len(shot.bytes()))
