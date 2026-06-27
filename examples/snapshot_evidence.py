from agentbrowser import Browser, LaunchOptions

HTML = """
<h1>Product page</h1>
<button>More details</button>
<section id="details" hidden>Details loaded</section>
<script>
document.querySelector("button").addEventListener("click", () => {
  document.querySelector("#details").hidden = false;
});
</script>
"""

with Browser.launch(LaunchOptions(headless=True)) as browser:
    browser.page.set_content(HTML)

    page = browser.agent.observe()
    button = page.find(role="button", contains="More")
    evidence = button.click_and_observe(wait_for_text="Details loaded")

    print(evidence.target)
    print(evidence.after.text)
    print(evidence.diff.changed)
