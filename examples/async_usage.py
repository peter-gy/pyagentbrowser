import asyncio

from agentbrowser import AsyncBrowser


async def main() -> None:
    browser = await AsyncBrowser.launch({"headless": True})
    async with browser:
        await browser.page.open("https://example.com")
        page = await browser.agent.observe()
        print(page.text)

        await browser.find.text("Learn more").click()
        await browser.page.wait_for_url("*://www.iana.org/*")
        print(await browser.page.url())


asyncio.run(main())
