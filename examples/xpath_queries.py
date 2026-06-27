from agentbrowser import Browser

with Browser.launch({"headless": True}) as browser:
    browser.page.open("https://example.com")
    browser.page.ready(timeout_ms=15_000)

    heading = browser.find.xpath("//h1").text()
    first_link = browser.find.xpath("(//a)[1]")

    print(heading)
    print(first_link.attribute("href"))
