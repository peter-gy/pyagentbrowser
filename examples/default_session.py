import pyagentbrowser as ab

ab.configure(headless=True, allowed_domains="*.example.com")
try:
    ab.page.open("example.com")
    page = ab.agent.observe()
    print(page.text)
    print(ab.page.title(), ab.page.url())
finally:
    ab.close()
