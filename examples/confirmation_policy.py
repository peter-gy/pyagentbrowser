from pyagentbrowser import ActionConfirmationRequired, Browser

with Browser(headless=True, confirm_actions=["click"]) as browser:
    browser.page.open("https://example.com")

    try:
        browser.find.text("More information").click()
    except ActionConfirmationRequired as confirmation:
        result = browser.confirm(confirmation)
        print(result)
