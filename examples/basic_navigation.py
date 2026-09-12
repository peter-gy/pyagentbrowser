from agentbrowser import Browser, Wait

with Browser.launch() as browser:
    browser.page.open("https://example.com")
    page = browser.page.observe()
    result = page.one(role="link", name="Learn more").click(wait=Wait.url("*://www.iana.org/*"))
    print(result.after.text)
