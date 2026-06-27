from pyagentbrowser import Browser, LaunchOptions

with Browser.launch(LaunchOptions(headless=True)) as browser:
    browser.page.open("https://example.com")
    print(browser.page.title())
    print(browser.page.url())
