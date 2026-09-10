from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path

import pytest

from agentbrowser import AsyncBrowser, Browser, LaunchOptions, OpenTarget
from agentbrowser.contracts.images import ImageContent, ImageDelivery
from agentbrowser.integrations.host import CallbackHost, bind_host, current_host, reset_host
from agentbrowser.integrations.runtime import CodeSession
from agentbrowser.integrations.tasks import Tasks


@pytest.mark.sdk_dx
def test_execution_preserves_globals_and_serializes_ordered_image_content() -> None:
    session = CodeSession(OpenTarget("https://example.com"))
    first = session.execute_code(
        "from agentbrowser import current_host, ImageContent\n"
        "value = 20\n"
        "def report():\n"
        "    print('before')\n"
        "    current_host().emit_image(ImageContent(b'image-bytes', 'image/png'))\n"
        "    print('after')\n"
        "report()"
    )

    transported = json.loads(json.dumps(first))
    assert transported == {
        "content": [
            {"type": "text", "text": "before\n"},
            {"type": "image", "data": "aW1hZ2UtYnl0ZXM=", "mimeType": "image/png"},
            {"type": "text", "text": "after\n"},
        ],
        "isError": False,
    }
    assert session.execute_code("value + 22") == {
        "content": [{"type": "text", "text": "42\n"}],
        "isError": False,
    }
    assert session.execute_code("report()") == first


@pytest.mark.sdk_dx
def test_execution_reports_capabilities_available_in_its_call_context() -> None:
    session = CodeSession(OpenTarget("https://example.com"))
    code = (
        "from agentbrowser import current_host\n"
        "(current_host().image_delivery, current_host().execution_context().cancellation, "
        "current_host().execution_context().managed_tasks)"
    )
    assert session.execute_code(code)["content"] == [
        {"type": "text", "text": "(True, False, False)\n"}
    ]

    async def run() -> None:
        try:
            assert (await session.aexecute_code(code))["content"] == [
                {"type": "text", "text": "(True, True, True)\n"}
            ]
        finally:
            await session.close()

    asyncio.run(run())


@pytest.mark.sdk_dx
def test_execution_restores_host_and_preserves_partial_output_on_error() -> None:
    outer = CallbackHost(OpenTarget("https://outer.example"), lambda _: ImageDelivery("accepted"))
    token = bind_host(outer)
    try:
        session = CodeSession(OpenTarget("https://inner.example"))
        result = session.execute_code(
            "from agentbrowser import current_host\n"
            "saved = current_host().current_target().url\n"
            "print(saved)\n"
            "raise ValueError('failed')"
        )
        assert result == {
            "content": [{"type": "text", "text": "https://inner.example\nValueError: failed\n"}],
            "isError": True,
        }
        assert current_host() is outer
        assert session.namespace["saved"] == "https://inner.example"
        assert session.execute_code("saved")["isError"] is False
    finally:
        reset_host(token)


@pytest.mark.sdk_dx
def test_image_emission_after_execution_fails_before_changing_returned_content() -> None:
    session = CodeSession(OpenTarget("https://example.com"))
    result = session.execute_code("from agentbrowser import current_host\nhost = current_host()")
    with pytest.raises(RuntimeError, match="execution has ended"):
        session.namespace["host"].emit_image(ImageContent(b"png", "image/png"))
    assert result == {"content": [], "isError": False}


@pytest.mark.sdk_dx
def test_async_execution_awaits_preserves_globals_and_restores_cancelled_context() -> None:
    async def run() -> None:
        entered = asyncio.Event()
        release = asyncio.Event()
        session = CodeSession(
            OpenTarget("https://example.com"), namespace={"entered": entered, "release": release}
        )
        result = await session.aexecute_code(
            "import asyncio\nawait asyncio.sleep(0)\nvalue = 7\nvalue"
        )
        assert result == {"content": [{"type": "text", "text": "7\n"}], "isError": False}
        pending = asyncio.create_task(session.aexecute_code("entered.set()\nawait release.wait()"))
        await entered.wait()
        with pytest.raises(RuntimeError, match="another call"):
            session.execute_code("value")
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
        assert session.execute_code("value")["content"] == [{"type": "text", "text": "7\n"}]
        with pytest.raises(RuntimeError, match="no AgentHost"):
            current_host()

    asyncio.run(run())


@pytest.mark.sdk_dx
def test_concurrent_sessions_capture_their_own_print_calls() -> None:
    async def run() -> None:
        release = asyncio.Event()
        first = CodeSession(OpenTarget("https://first.example"), namespace={"release": release})
        second = CodeSession(OpenTarget("https://second.example"), namespace={"release": release})
        first_task = asyncio.create_task(
            first.aexecute_code("await release.wait()\nprint('first')")
        )
        second_task = asyncio.create_task(
            second.aexecute_code("await release.wait()\nprint('second')")
        )
        release.set()
        results = await asyncio.gather(first_task, second_task)
        assert results == [
            {"content": [{"type": "text", "text": "first\n"}], "isError": False},
            {"content": [{"type": "text", "text": "second\n"}], "isError": False},
        ]

    asyncio.run(run())


@pytest.mark.sdk_dx
def test_managed_task_retains_result_and_owns_execution_budget_across_calls() -> None:
    async def run() -> None:
        release = asyncio.Event()
        session = CodeSession(OpenTarget("https://example.com"), namespace={"release": release})
        started = await session.aexecute_code(
            "from agentbrowser import current_host\n"
            "async def operation():\n"
            "    await release.wait()\n"
            "    return current_host().execution_context().timeout_ms\n"
            "task = current_host().start_task('budget', operation, timeout_ms=8000)\n"
            "task.id",
            timeout_ms=2_000,
        )
        assert started["isError"] is False
        task = session.namespace["task"]
        assert session.tasks.get(task.id) is task
        assert task.status().state == "running"
        release.set()
        result = await session.aexecute_code("await task.result()")
        assert result == {"content": [{"type": "text", "text": "8000\n"}], "isError": False}
        assert task.status().state == "completed"
        assert await task.result() == 8_000
        await session.close()
        assert await session.tasks.get(task.id).result() == 8_000
        with pytest.raises(RuntimeError, match="CodeSession is closed"):
            session.execute_code("1")

    asyncio.run(run())


@pytest.mark.sdk_dx
def test_task_cancel_waits_for_cleanup_before_reporting_cancellation() -> None:
    async def run() -> None:
        started = asyncio.Event()
        cleaning = asyncio.Event()
        finish = asyncio.Event()
        tasks = Tasks(OpenTarget("https://example.com"))

        async def operation() -> None:
            try:
                started.set()
                await asyncio.Event().wait()
            finally:
                cleaning.set()
                await finish.wait()

        task = tasks.start("cleanup", operation)
        await started.wait()
        cancellation = asyncio.create_task(task.cancel())
        await cleaning.wait()
        assert not cancellation.done()
        finish.set()
        assert (await cancellation).state == "cancelled"
        with pytest.raises(asyncio.CancelledError):
            await task.result()
        await tasks.close()

    asyncio.run(run())


@pytest.mark.sdk_dx
def test_task_result_timeout_leaves_work_running_and_registry_close_settles_it() -> None:
    async def run() -> None:
        started = asyncio.Event()
        cleaned = asyncio.Event()
        tasks = Tasks(OpenTarget("https://example.com"))

        async def operation() -> None:
            try:
                started.set()
                await asyncio.Event().wait()
            finally:
                cleaned.set()

        task = tasks.start("pending", operation)
        await started.wait()
        with pytest.raises(TimeoutError):
            await task.result(timeout_ms=0)
        assert task.status().state == "running"
        await tasks.close()
        assert cleaned.is_set()
        assert task.status().state == "cancelled"
        with pytest.raises(RuntimeError, match="Tasks is closed"):
            tasks.start("again", operation)

    asyncio.run(run())


@pytest.mark.sdk_dx
def test_task_timeout_and_failure_remain_inspectable() -> None:
    async def run() -> None:
        tasks = Tasks(OpenTarget("https://example.com"))

        async def operation() -> None:
            await asyncio.Event().wait()

        task = tasks.start("deadline", operation, timeout_ms=0)
        with pytest.raises(TimeoutError):
            await task.result()
        assert task.status().state == "failed"
        assert task.status().detail == "TimeoutError: "
        assert (await tasks.get(task.id).cancel()).state == "failed"
        await tasks.close()

    asyncio.run(run())


@pytest.mark.sdk_dx
def test_task_progress_remains_observable_until_completion() -> None:
    async def run() -> None:
        release = asyncio.Event()
        reported = asyncio.Event()
        tasks = Tasks(OpenTarget("https://example.com"))

        async def operation() -> int:
            task.report(0.5, "captured first viewport")
            reported.set()
            await release.wait()
            task.report(1, "captured both viewports")
            return 2

        task = tasks.start("viewports", operation)
        await reported.wait()
        assert task.status().progress == 0.5
        assert task.status().detail == "captured first viewport"
        with pytest.raises(ValueError, match="between zero and one"):
            task.report(float("nan"))
        release.set()
        assert await task.result() == 2
        assert task.status().progress == 1
        assert task.status().detail == "captured both viewports"
        with pytest.raises(RuntimeError, match="progress is final"):
            task.report(0)
        await tasks.close()

    asyncio.run(run())


@pytest.mark.sdk_dx
def test_background_image_emission_requires_an_active_code_call() -> None:
    async def run() -> None:
        session = CodeSession(OpenTarget("https://example.com"))
        result = await session.aexecute_code(
            "from agentbrowser import current_host, ImageContent\n"
            "async def operation():\n"
            "    current_host().emit_image(ImageContent(b'png', 'image/png'))\n"
            "task = current_host().start_task('image', operation)"
        )
        assert result == {"content": [], "isError": False}
        task = session.namespace["task"]
        with pytest.raises(RuntimeError, match="Return the screenshot"):
            await task.result()
        assert task.status().state == "failed"
        await session.close()

    asyncio.run(run())


@pytest.mark.integration
def test_real_screenshot_reaches_serialized_tool_result(chrome_path: Path, tmp_path: Path) -> None:
    with Browser.launch(LaunchOptions(executable_path=chrome_path)) as browser:
        session = CodeSession(
            OpenTarget("data:text/html,<title>Image delivery</title><h1>Visible pixels</h1>"),
            namespace={"browser": browser, "output_path": tmp_path / "capture.png"},
        )
        result = session.execute_code(
            "from agentbrowser import current_host\n"
            "host = current_host()\n"
            "browser.page.open(host.current_target().url)\n"
            "shot = browser.page.capture.screenshot(path=output_path)\n"
            "delivery = host.emit_image(shot.content())\n"
            "print(browser.page.title())"
        )

        payload = json.loads(json.dumps(result))
        assert payload["isError"] is False, payload
        image, text = payload["content"]
        assert image["type"] == "image"
        assert image["mimeType"] == "image/png"
        assert base64.b64decode(image["data"]) == (tmp_path / "capture.png").read_bytes()
        assert base64.b64decode(image["data"]).startswith(b"\x89PNG\r\n\x1a\n")
        assert text == {"type": "text", "text": "Image delivery\n"}
        assert session.namespace["delivery"].status == "queued"


@pytest.mark.integration
def test_managed_browser_task_returns_screenshot_to_a_later_call(
    chrome_path: Path, tmp_path: Path
) -> None:
    async def run() -> None:
        browser = await AsyncBrowser.launch(LaunchOptions(executable_path=chrome_path))
        async with browser:
            session = CodeSession(
                OpenTarget("data:text/html,<h1>Task result</h1>"),
                namespace={"browser": browser, "output_path": tmp_path / "task.png"},
            )
            try:
                started = await session.aexecute_code(
                    "from agentbrowser import current_host\n"
                    "async def capture():\n"
                    "    await browser.page.open(current_host().current_target().url)\n"
                    "    return await browser.page.capture.screenshot(path=output_path)\n"
                    "task = current_host().start_task('capture', capture, timeout_ms=10000)",
                    timeout_ms=1,
                )
                assert started == {"content": [], "isError": False}
                result = await session.aexecute_code(
                    "shot = await task.result()\n"
                    "delivery = current_host().emit_image(shot.content())"
                )
                payload = json.loads(json.dumps(result))
                assert payload["isError"] is False, payload
                assert len(payload["content"]) == 1
                image = payload["content"][0]
                assert image["type"] == "image"
                assert base64.b64decode(image["data"]) == (tmp_path / "task.png").read_bytes()
            finally:
                await session.close()

    asyncio.run(run())
