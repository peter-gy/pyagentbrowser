import asyncio

from agentbrowser import AsyncBrowser, LaunchOptions


async def main() -> None:
    browser = await AsyncBrowser.launch(LaunchOptions(headless=True))
    async with browser:
        await browser.page.open("https://example.com")
        page = await browser.agent.observe()
        print(page.text)


asyncio.run(main())
