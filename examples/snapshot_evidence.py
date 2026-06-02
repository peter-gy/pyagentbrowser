from pyagentbrowser import Browser

with Browser(headless=True) as browser:
    browser.page.open("https://example.com")

    page = browser.agent.observe()
    link = page.find(role="link", contains="More")
    evidence = link.click_and_observe()

    print(evidence.target)
    print(evidence.after.text)
    print(evidence.diff.changed)
