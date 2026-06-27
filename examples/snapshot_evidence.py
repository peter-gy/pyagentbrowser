from agentbrowser import Browser

with Browser.launch({"headless": True}) as browser:
    browser.page.open("https://example.com")

    page = browser.agent.observe()
    link = page.find(role="link", name="Learn more")
    evidence = link.click_and_observe(wait_for_url="*://www.iana.org/*")

    print(evidence.target)
    print(evidence.after.text)
    print(evidence.diff.changed)
