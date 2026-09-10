from agentbrowser import Browser, ConfirmationRequired, SessionOptions

session = SessionOptions(confirm_actions=("click",))

with Browser.launch(session=session) as browser:
    browser.page.open("https://example.com")
    link = browser.page.observe().one(role="link", name="Learn more")
    try:
        result = link.click()
    except ConfirmationRequired as required:
        result = required.pending.confirm()
    print(result.after.text)
