from agentbrowser import ActionConfirmationRequired, Browser, BrowserSessionOptions, LaunchOptions

HTML = """
<button>More information</button>
<p id="status"></p>
<script>
document.querySelector("button").addEventListener("click", () => {
  document.querySelector("#status").textContent = "Confirmed"
});
</script>
"""

with Browser.launch(
    LaunchOptions(headless=True),
    session_options=BrowserSessionOptions(confirm_actions=["click"]),
) as browser:
    browser.page.set_content(HTML)

    try:
        browser.find.text("More information").click()
    except ActionConfirmationRequired as confirmation:
        result = confirmation.pending_action.confirm()
        print(result)
