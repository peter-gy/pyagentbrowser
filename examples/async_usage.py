import asyncio

from agentbrowser import AsyncBrowser, Wait


async def main() -> None:
    browser = await AsyncBrowser.launch()
    async with browser:
        await browser.open("https://example.com")
        page = await browser.observe()
        result = await page.one(role="link", name="Learn more").click(
            wait=Wait.url("*://www.iana.org/*")
        )
        print(result.after.text)


asyncio.run(main())
