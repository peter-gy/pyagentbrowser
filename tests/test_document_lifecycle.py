from __future__ import annotations

import asyncio
import inspect
import weakref
from collections.abc import Mapping
from typing import Any

import pytest
from fakes import ScriptedNative

from agentbrowser import (
    AsyncBrowser,
    Browser,
    BrowserError,
    ConfirmationRequired,
    Frame,
    FrameLookupError,
    NativeParseError,
)
from agentbrowser.transport.async_ import AsyncNativeSession
from agentbrowser.transport.sync import NativeSession

pytestmark = pytest.mark.sdk_dx


async def result(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


@pytest.mark.parametrize("asynchronous", [False, True])
def test_retained_page_keeps_its_owner_and_obeys_close(asynchronous: bool) -> None:
    async def run() -> None:
        native = ScriptedNative({"title": {"title": "Orders"}}, default={})
        browser = (
            AsyncBrowser(_native_session=AsyncNativeSession(native=native))
            if asynchronous
            else Browser(_native_session=NativeSession(native=native))
        )
        owner = weakref.ref(browser._controller)
        page = browser.page
        del browser
        try:
            assert owner() is not None
            assert await result(page.title()) == "Orders"
        finally:
            if controller := owner():
                await result(controller.close())
        with pytest.raises(RuntimeError, match="closed"):
            await result(page.title())

    asyncio.run(run())


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("failure", ["native", "decode", "confirmation"])
def test_page_retains_target_after_failed_first_operation(asynchronous: bool, failure: str) -> None:
    async def run() -> None:
        failed = (
            {"success": True, "targetId": "page-a", "data": {"result": {"x": "bad"}}}
            if failure == "decode"
            else {"success": False, "targetId": "page-a", "error": "operation failed"}
        )
        native = ScriptedNative(
            {
                "evaluate": failed
                if failure != "confirmation"
                else {"confirmation_required": True, "confirmation_id": "first"},
                "confirm": {"confirmed": True, "action": "evaluate", "result": failed},
                "activate_other": {"success": True, "targetId": "page-b", "data": {}},
            },
            default={},
        )
        browser = (
            AsyncBrowser(_native_session=AsyncNativeSession(native=native))
            if asynchronous
            else Browser(_native_session=NativeSession(native=native))
        )
        page = browser.page
        expected = NativeParseError if failure == "decode" else BrowserError
        try:
            if failure == "confirmation":
                with pytest.raises(ConfirmationRequired) as required:
                    await result(page.geometry())
                await result(browser.native.execute("activate_other"))
                with pytest.raises(expected):
                    await result(required.value.pending.confirm())
            else:
                with pytest.raises(expected):
                    await result(page.geometry())
            assert page.target_id == "page-a"
            await result(browser.native.execute("activate_other"))
            native.replies["title"] = {"title": "Orders"}
            assert await result(page.title()) == "Orders"
            assert native.commands[-1]["_targetId"] == "page-a"
        finally:
            await result(browser.close())

    asyncio.run(run())


@pytest.mark.parametrize("asynchronous", [False, True])
def test_frame_preserves_scope_errors_across_repeated_confirmation(asynchronous: bool) -> None:
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
        return {"confirmed": True, "action": "evaluate", "result": result}

    native = ScriptedNative({"evaluate": reply, "confirm": reply}, default={})
    if asynchronous:

        async def run() -> None:
            from agentbrowser import AsyncFrame

            browser = AsyncBrowser(_native_session=AsyncNativeSession(native=native))
            frame = AsyncFrame(browser._executor, frame_id="child")
            try:
                with pytest.raises(ConfirmationRequired) as first:
                    await frame.title()
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
        frame = Frame(browser._executor, frame_id="child")
        try:
            with pytest.raises(ConfirmationRequired) as first:
                frame.title()
            with pytest.raises(ConfirmationRequired) as second:
                first.value.pending.confirm()
            with pytest.raises(FrameLookupError) as failure:
                second.value.pending.confirm()
            assert failure.value.reason == "detached"
        finally:
            browser.close()
