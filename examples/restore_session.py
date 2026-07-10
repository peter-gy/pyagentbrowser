from agentbrowser import Browser, RestoreOptions, SessionOptions

session = SessionOptions(
    session_id="research",
    restore=RestoreOptions("research", save="always"),
)

browser = Browser.launch(session=session)
browser.open("https://example.com")
print(browser.session.status().restore_status)

closed = browser.close()
print(closed.save_status)
