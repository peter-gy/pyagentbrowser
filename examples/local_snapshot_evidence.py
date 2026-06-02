from pyagentbrowser import Browser

HTML = """
<label>Email <input aria-label="Email" /></label>
<button>Continue</button>
<p aria-live="polite"></p>
<script>
document.querySelector("button").addEventListener("click", () => {
  document.querySelector("p").textContent = "Signed in";
});
</script>
"""


with Browser(headless=True) as browser:
    browser.launch()
    browser.page.set_content(HTML)

    page = browser.agent.observe()
    page.find(name="Email").fill("ada@example.com")
    evidence = page.find(role="button", name="Continue", exact=True).click_and_observe(
        wait_for_text="Signed in"
    )

    print(evidence.after.text)
    print(evidence.diff.changed)
