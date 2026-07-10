from agentbrowser import Browser, RestoreOptions, SessionOptions

session = SessionOptions(
    session_id="research",
    restore=RestoreOptions("research", save="always"),
)

with Browser.launch(session=session) as browser:
    browser.open("https://example.com")
    print(browser.native.data("session_info")["restoreStatus"])
