from agentbrowser import Browser, Wait

with Browser.launch() as browser:
    browser.open("https://example.com")
    page = browser.observe()
    result = page.one(role="link", name="Learn more").click(wait=Wait.url("*://www.iana.org/*"))
    print(result.after.text)
