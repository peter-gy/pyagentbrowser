from pyagentbrowser import Browser, LaunchOptions

HTML = """
<main>
  <h1>XPath page</h1>
  <a href="#first">First link</a>
</main>
"""

with Browser.launch(LaunchOptions(headless=True)) as browser:
    browser.tabs.open("about:blank", label="xpath")
    browser.page.set_content(HTML)
    browser.page.ready(timeout_ms=15_000)

    heading = browser.find.xpath("//h1").text()
    first_link = browser.find.xpath("(//a)[1]")

    print(heading)
    print(first_link.attribute("href"))
