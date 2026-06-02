import asyncio

from pyagentbrowser import AsyncBrowser


async def main() -> None:
    async with AsyncBrowser(headless=True) as browser:
        await browser.page.open("https://example.com")
        page = await browser.agent.observe()
        print(page.text)


asyncio.run(main())
