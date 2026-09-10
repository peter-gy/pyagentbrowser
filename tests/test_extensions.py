from __future__ import annotations

import asyncio
import weakref
from collections.abc import Mapping
from dataclasses import dataclass
from threading import Event

import pytest
from fakes import ConfirmationNative, ScriptedNative

from agentbrowser import AsyncBrowser, Browser, ConfirmationRequired, Frame, FrameLookupError
from agentbrowser.execution.commands import AsyncExecutor, Command, Executor
from agentbrowser.transport.async_ import AsyncNativeSession
from agentbrowser.transport.sync import NativeSession

pytestmark = pytest.mark.sdk_dx


def _count(data: Mapping[str, object]) -> int:
    value = data["count"]
    if not isinstance(value, int):
        raise TypeError("count must be an integer")
    return value


@dataclass
class ItemCount:
    executor: Executor

    def read(self) -> int:
        return self.executor.execute(Command("item_count", {"kind": "article"}, decode=_count))


@dataclass
class AsyncItemCount:
    executor: AsyncExecutor

    async def read(self) -> int:
        return await self.executor.execute(
            Command("item_count", {"kind": "article"}, decode=_count)
        )


def test_extension_preserves_document_scope_and_result_type() -> None:
    native = ScriptedNative({"item_count": {"count": 4}}, default={})
    browser = Browser(_native_session=NativeSession(native=native))
    frame = Frame(
        browser.extension(lambda executor: executor), target_id="page-2", frame_id="child"
    )
    extension = frame.extension(ItemCount)

    assert extension.read() == 4
    command = native.commands[-1]
    assert command["kind"] == "article"
    assert command["_targetId"] == "page-2"
    assert command["_frameId"] == "child"
    browser.close()


def test_extension_confirmation_resumes_its_decoder() -> None:
    browser = Browser(
        _native_session=NativeSession(
            native=ConfirmationNative(action="item_count", result={"count": 7})
        )
    )
    extension = browser.page.extension(ItemCount)
    with pytest.raises(ConfirmationRequired) as raised:
        extension.read()
    assert raised.value.pending.confirm() == 7
    browser.close()


def test_first_extension_call_binds_the_page_before_the_active_target_changes() -> None:
    native = ScriptedNative(
        {
            "item_count": {"success": True, "targetId": "page-a", "data": {"count": 4}},
            "activate_other": {"success": True, "targetId": "page-b", "data": {}},
        },
        default={},
    )
    browser = Browser(_native_session=NativeSession(native=native))
    page = browser.page
    extension = page.extension(ItemCount)
    assert extension.read() == 4
    assert page.target_id == "page-a"
    browser.native.execute("activate_other")
    assert extension.read() == 4
    assert native.commands[-1]["_targetId"] == "page-a"
    browser.close()


def test_extension_retains_its_resource_owner() -> None:
    native = ScriptedNative({"item_count": {"count": 2}}, default={})
    browser = Browser(_native_session=NativeSession(native=native))
    owner = weakref.ref(browser._controller)
    extension = browser.extension(ItemCount)
    del browser

    try:
        assert owner() is not None
        assert extension.read() == 2
    finally:
        if controller := owner():
            controller.close()


def test_extension_obeys_terminal_close() -> None:
    browser = Browser(_native_session=NativeSession(native=ScriptedNative(default={})))
    extension = browser.extension(ItemCount)
    browser.close()
    with pytest.raises(RuntimeError, match="closed"):
        extension.read()


def test_async_extension_preserves_scope_and_confirmation_decoder() -> None:
    async def run() -> None:
        from agentbrowser import AsyncFrame

        native = ConfirmationNative(action="item_count", result={"count": 9})
        browser = AsyncBrowser(_native_session=AsyncNativeSession(native=native))
        frame = AsyncFrame(
            browser.extension(lambda executor: executor), target_id="page-3", frame_id="child"
        )
        extension = frame.extension(AsyncItemCount)
        with pytest.raises(ConfirmationRequired) as raised:
            await extension.read()
        assert native.commands[0]["_targetId"] == "page-3"
        assert native.commands[0]["_frameId"] == "child"
        assert await raised.value.pending.confirm() == 9
        await browser.close()

    asyncio.run(run())


def test_async_extension_cancellation_skips_queued_native_work() -> None:
    async def run() -> None:
        started = Event()
        release = Event()

        def block(_command: Mapping[str, object]) -> Mapping[str, object]:
            started.set()
            release.wait(5)
            return {"ok": True}

        native = ScriptedNative({"block": block}, default={})
        browser = AsyncBrowser(_native_session=AsyncNativeSession(native=native))
        executor = browser.extension(lambda executor: executor)
        first = asyncio.create_task(executor.execute(Command("block")))
        try:
            assert await asyncio.to_thread(started.wait, 2)
            queued = asyncio.create_task(browser.extension(AsyncItemCount).read())
            await asyncio.sleep(0)
            queued.cancel()
            with pytest.raises(asyncio.CancelledError):
                await queued
        finally:
            release.set()
            await first
            await browser.close()
        assert all(command["action"] != "item_count" for command in native.commands)

    asyncio.run(run())


@pytest.mark.parametrize("asynchronous", [False, True])
def test_scoped_extension_preserves_errors_across_repeated_confirmation(asynchronous: bool) -> None:
    def reply(command: Mapping[str, object]) -> Mapping[str, object]:
        if command["action"] != "confirm":
            return {"confirmation_required": True, "confirmation_id": "first"}
        result = (
            {
                "success": True,
                "data": {"confirmation_required": True, "confirmation_id": "second"},
            }
            if command["confirmation_id"] == "first"
            else {"success": False, "error": "frame left the document", "code": "frame_detached"}
        )
        return {"confirmed": True, "action": "item_count", "result": result}

    native = ScriptedNative({"item_count": reply, "confirm": reply}, default={})
    if asynchronous:

        async def run() -> None:
            from agentbrowser import AsyncFrame

            browser = AsyncBrowser(_native_session=AsyncNativeSession(native=native))
            frame = AsyncFrame(browser.extension(lambda value: value), frame_id="child")
            try:
                with pytest.raises(ConfirmationRequired) as first:
                    await frame.extension(AsyncItemCount).read()
                with pytest.raises(ConfirmationRequired) as second:
                    await first.value.pending.confirm()
                with pytest.raises(FrameLookupError) as failure:
                    await second.value.pending.confirm()
                assert failure.value.reason == "detached"
            finally:
                await browser.close()

        asyncio.run(run())
    else:
        browser = Browser(_native_session=NativeSession(native=native))
        frame = Frame(browser.extension(lambda value: value), frame_id="child")
        try:
            with pytest.raises(ConfirmationRequired) as first:
                frame.extension(ItemCount).read()
            with pytest.raises(ConfirmationRequired) as second:
                first.value.pending.confirm()
            with pytest.raises(FrameLookupError) as failure:
                second.value.pending.confirm()
            assert failure.value.reason == "detached"
        finally:
            browser.close()


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("failure", ["native", "decoder", "confirmation"])
def test_document_retains_first_target_when_command_fails(asynchronous: bool, failure: str) -> None:
    from agentbrowser import BrowserError

    def decode(_data: Mapping[str, object]) -> object:
        raise ValueError("invalid item count")

    failed = {
        "success": False,
        "targetId": "page-a",
        "error": "element detached",
    }
    native = ScriptedNative(
        {
            "item_count": (
                {"success": True, "targetId": "page-a", "data": {}}
                if failure == "decoder"
                else {"confirmation_required": True, "confirmation_id": "pending"}
                if failure == "confirmation"
                else failed
            ),
            "confirm": {"confirmed": True, "action": "item_count", "result": failed},
            "activate_other": {"success": True, "targetId": "page-b", "data": {}},
            "title": {"title": "Orders"},
        },
        default={},
    )
    command = (
        Command("item_count", decode=decode) if failure == "decoder" else Command("item_count")
    )
    expected = ValueError if failure == "decoder" else BrowserError
    if asynchronous:

        async def run() -> None:
            browser = AsyncBrowser(_native_session=AsyncNativeSession(native=native))
            page = browser.page
            try:
                if failure == "confirmation":
                    with pytest.raises(ConfirmationRequired) as raised:
                        await page.execute(command)
                    await browser.native.execute("activate_other")
                    with pytest.raises(expected):
                        await raised.value.pending.confirm()
                else:
                    with pytest.raises(expected):
                        await page.execute(command)
                assert page.target_id == "page-a"
                await browser.native.execute("activate_other")
                assert await page.title() == "Orders"
                assert native.commands[-1]["_targetId"] == "page-a"
            finally:
                await browser.close()

        asyncio.run(run())
    else:
        browser = Browser(_native_session=NativeSession(native=native))
        page = browser.page
        try:
            if failure == "confirmation":
                with pytest.raises(ConfirmationRequired) as raised:
                    page.execute(command)
                browser.native.execute("activate_other")
                with pytest.raises(expected):
                    raised.value.pending.confirm()
            else:
                with pytest.raises(expected):
                    page.execute(command)
            assert page.target_id == "page-a"
            browser.native.execute("activate_other")
            assert page.title() == "Orders"
            assert native.commands[-1]["_targetId"] == "page-a"
        finally:
            browser.close()
