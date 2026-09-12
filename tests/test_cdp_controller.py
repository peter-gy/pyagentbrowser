from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any, cast

import pytest

from agentbrowser import AsyncBrowser
from agentbrowser.cdp import (
    AsyncCDPController,
    CDPClosedError,
    CDPController,
    CDPStaleObjectError,
    CDPTargetAmbiguityError,
)
from agentbrowser.execution.commands import Command
from agentbrowser.transport.async_ import AsyncNativeSession
from tests.support.cdp_targets import MultiTargetCommands, _multi_target_controller
from tests.support.cdp_transport import (
    PublicPathAsyncCDPClient,
    PublicPathNative,
)

pytestmark = pytest.mark.sdk_dx


def test_cdp_controller_reresolves_active_target_after_invalidation() -> None:
    browser = MultiTargetCommands()
    controller = _multi_target_controller(browser)

    assert controller.evaluate("location.href") == "s-one"
    browser.current_url = "https://example.com/two"
    controller.invalidate()
    assert controller.evaluate("location.href") == "s-two"


def test_cdp_controller_selects_explicit_target_id() -> None:
    browser = MultiTargetCommands()
    controller = _multi_target_controller(browser)

    assert controller.target(target_id="one").evaluate("location.href") == "s-one"


def test_cdp_controller_selects_native_tab_label() -> None:
    browser = MultiTargetCommands()
    controller = _multi_target_controller(browser)

    assert controller.target(label="second").evaluate("location.href") == "s-two"


def test_active_target_ambiguity_is_explicit() -> None:
    class FakeCommands:
        def execute(self, command: Command[Any]) -> Any:
            data = (
                {"cdpUrl": "ws://cdp"}
                if command.action == "cdp_url"
                else {"url": "https://example.com"}
            )
            return command.decode(data)

    class AmbiguousTargetClient:
        def __init__(self, _url: str) -> None:
            pass

        def send(
            self,
            method: str,
            params: Mapping[str, Any] | None = None,
            *,
            session_id: str | None = None,
        ) -> Mapping[str, Any]:
            del params, session_id
            if method != "Target.getTargets":
                return {}
            return {
                "targetInfos": [
                    {"targetId": "a", "type": "page", "url": "https://example.com"},
                    {"targetId": "b", "type": "page", "url": "https://example.com"},
                ]
            }

    with pytest.raises(
        CDPTargetAmbiguityError,
        match=r"Pass label=\.\.\., url=\.\.\., or target_id=\.\.\.",
    ):
        CDPController(
            cast(Any, FakeCommands()),
            client_factory=cast(Any, AmbiguousTargetClient),
        ).evaluate("location.href")


def test_cdp_controller_close_blocks_reopen_and_stales_frame() -> None:
    browser = MultiTargetCommands()
    controller = _multi_target_controller(browser)
    frame = controller.frame()

    controller.close()

    with pytest.raises(CDPStaleObjectError, match="frame is stale"):
        frame.evaluate("location.href")
    with pytest.raises(CDPClosedError, match="CDP controller is closed"):
        controller.evaluate("location.href")


def test_async_cdp_controller_close_blocks_reopen_and_stales_frame() -> None:
    async def run() -> None:
        browser = AsyncBrowser(_native_session=AsyncNativeSession(native=PublicPathNative()))
        controller = AsyncCDPController(
            browser._executor,
            client_factory=cast(Any, PublicPathAsyncCDPClient),
        )
        frame = await controller.frame()

        await controller.close()

        with pytest.raises(CDPStaleObjectError, match="frame is stale"):
            await frame.evaluate("location.href")
        with pytest.raises(CDPClosedError, match="CDP controller is closed"):
            await controller.evaluate("location.href")
        await browser.close()

    asyncio.run(run())
