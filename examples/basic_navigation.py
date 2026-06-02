from pyagentbrowser import Browser

with Browser(headless=True) as browser:
    browser.page.open("https://example.com")
    print(browser.page.title())
    print(browser.page.url())
