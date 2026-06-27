from agentbrowser import Browser

with Browser.launch({"headless": True}) as browser:
    browser.page.open("https://example.com")
    page = browser.agent.observe()
    print(page.text)

    browser.find.text("Learn more").click()
    browser.page.wait_for_url("*://www.iana.org/*")
    print(browser.page.title())
    print(browser.page.url())
