from __future__ import annotations

import asyncio
import concurrent.futures
import json
import socket
import threading
from pathlib import Path

import pytest

from agentbrowser import (
    AsyncBrowser,
    BrowserError,
    LaunchOptions,
    OpenTarget,
    SessionOptions,
    Tasks,
)
from agentbrowser._native import NativeBrowser, NativeCancellation


@pytest.mark.native_smoke
def test_cancelled_native_command_is_rejected_before_dispatch() -> None:
    native = NativeBrowser()
    cancellation = NativeCancellation()
    cancellation.cancel()

    response = json.loads(
        native.execute_json(json.dumps({"id": "cancelled", "action": "launch"}), cancellation)
    )

    assert response["success"] is False
    assert response["code"] == "execution_cancelled"
    assert response["id"] == "cancelled"


@pytest.mark.native_smoke
@pytest.mark.parametrize("interruption", ["cancelled", "timeout"])
def test_interrupted_confirmation_requires_approval_for_the_next_command(
    interruption: str,
) -> None:
    accepted = threading.Event()
    released = threading.Event()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        listener.settimeout(3)

        def serve() -> None:
            connection, _ = listener.accept()
            with connection:
                accepted.set()
                released.wait(5)

        server = threading.Thread(target=serve)
        server.start()
        native = NativeBrowser(json.dumps({"confirm_actions": ["read"]}))
        command = {
            "id": "request",
            "action": "read",
            "url": f"http://127.0.0.1:{listener.getsockname()[1]}/",
        }
        cancellation = NativeCancellation()
        try:
            required = json.loads(native.execute_json(json.dumps(command)))
            approval = {
                "id": "approval",
                "action": "confirm",
                "confirmation_id": required["data"]["confirmation_id"],
            }
            if interruption == "timeout":
                approval["_timeoutMs"] = 1_000
            with concurrent.futures.ThreadPoolExecutor() as workers:
                pending = workers.submit(native.execute_json, json.dumps(approval), cancellation)
                try:
                    assert accepted.wait(3)
                    if interruption == "cancelled":
                        cancellation.cancel()
                    response = json.loads(pending.result(3))
                finally:
                    cancellation.cancel()
            assert response["code"] == f"execution_{interruption}"
            command.update(id="next", url="http://127.0.0.1:1/")
            required = json.loads(native.execute_json(json.dumps(command)))
            assert required["data"]["confirmation_required"] is True
            assert required["data"]["action"] == "read"
        finally:
            cancellation.cancel()
            released.set()
            server.join(4)


async def _wait_for_evaluation(browser: AsyncBrowser) -> None:
    async with asyncio.timeout(3):
        while not await browser.cdp.evaluate("window.evaluationStarted"):
            pass


@pytest.mark.integration
@pytest.mark.parametrize("managed", [False, True])
def test_cancelling_active_evaluation_releases_native_worker(
    chrome_path: Path, managed: bool
) -> None:
    async def run() -> None:
        browser = await AsyncBrowser.launch(
            LaunchOptions(executable_path=chrome_path), session=SessionOptions(timeout=None)
        )
        tasks = Tasks(OpenTarget("about:blank"))
        try:
            await browser.page.open("data:text/html,<title>Cancellation</title>")
            await browser.cdp.evaluate("window.evaluationStarted = false")

            async def evaluate() -> object:
                return await browser.page.evaluate(
                    "window.evaluationStarted = true; new Promise(() => {})"
                )

            if managed:
                task = tasks.start("evaluation", evaluate)
            else:
                pending = asyncio.create_task(evaluate())
            await _wait_for_evaluation(browser)
            async with asyncio.timeout(3):
                if managed:
                    assert (await task.cancel()).state == "cancelled"
                else:
                    pending.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await pending
                assert await browser.page.title() == "Cancellation"
        finally:
            await asyncio.wait_for(tasks.close(), 3)
            await asyncio.wait_for(browser.close(timeout=3), 4)
        assert browser.closed

    asyncio.run(run())


@pytest.mark.integration
def test_browser_close_cancels_active_evaluation_and_settles_shutdown(chrome_path: Path) -> None:
    async def run() -> None:
        browser = await AsyncBrowser.launch(
            LaunchOptions(executable_path=chrome_path), session=SessionOptions(timeout=None)
        )
        try:
            await browser.page.open("data:text/html,<title>Close</title>")
            await browser.cdp.evaluate("window.evaluationStarted = false")
            pending = asyncio.create_task(
                browser.page.evaluate("window.evaluationStarted = true; new Promise(() => {})")
            )
            await _wait_for_evaluation(browser)
            await asyncio.wait_for(browser.close(timeout=3), 4)
            with pytest.raises(BrowserError) as failed:
                await pending
            assert failed.value.code == "execution_cancelled"
            assert browser.closed
        finally:
            await asyncio.wait_for(browser.close(timeout=3), 4)

    asyncio.run(run())
