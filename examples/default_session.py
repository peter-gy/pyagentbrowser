import pyagentbrowser as ab
from pyagentbrowser import BrowserSessionOptions, LaunchOptions

ab.notebook.configure(
    launch_options=LaunchOptions(headless=True),
    session_options=BrowserSessionOptions(allowed_domains="*.example.com"),
)
try:
    ab.notebook.page.open("example.com")
    page = ab.notebook.agent.observe()
    print(page.text)
    print(ab.notebook.page.title(), ab.notebook.page.url())
finally:
    ab.notebook.close()
