from pyagentbrowser import Browser

with Browser(headless=True) as browser:
    browser.tabs.open("https://example.com", label="xpath")
    browser.page.ready(timeout_ms=15_000)

    heading = browser.find.xpath("//h1").text()
    first_link = browser.find.xpath("(//a)[1]")

    print(heading)
    print(first_link.attribute("href"))
