import agentbrowser as ab

ab.configure(launch={"headless": True})
try:
    ab.page.open("https://example.com")
    page = ab.agent.observe()
    print(page.text)

    ab.find.text("Learn more").click()
    ab.page.wait_for_url("*://www.iana.org/*")
    print(ab.page.title())
    print(ab.page.url())
finally:
    ab.close()
