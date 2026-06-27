from agentbrowser import ActionConfirmationRequired, Browser

with Browser.launch(
    {"headless": True},
    session={"confirm_actions": ["click"]},
) as browser:
    browser.page.open("https://example.com")

    try:
        browser.find.text("Learn more").click()
    except ActionConfirmationRequired as confirmation:
        confirmation.pending_action.confirm()

    browser.page.wait_for_url("*://www.iana.org/*")
    print(browser.page.url())
