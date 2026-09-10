from __future__ import annotations

import asyncio
import importlib

import pytest

from agentbrowser import AsyncBrowser, Browser
from agentbrowser.transport.async_ import AsyncNativeSession
from agentbrowser.transport.sync import NativeSession
from tests.support.cdp_transport import (
    PublicPathAsyncCDPClient,
    PublicPathCDPClient,
    PublicPathNative,
)

pytestmark = pytest.mark.sdk_dx


def test_page_evaluate_without_context_uses_native_command() -> None:
    browser = Browser(_native_session=NativeSession(native=PublicPathNative()))

    assert browser.page.evaluate("1 + 1") == 2


def test_browser_cdp_frames_list_uses_public_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    browser = _browser_with_public_path_cdp(monkeypatch)

    frames = {frame.id: frame for frame in browser.cdp.frames.list()}
    assert frames["main"].url == "https://example.com"
    assert frames["child"].name == "target"


def test_browser_cdp_frames_lookup_by_name_uses_public_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    browser = _browser_with_public_path_cdp(monkeypatch)

    assert browser.cdp.frames.get(name="target").id == "child"


def test_browser_cdp_frames_lookup_by_selector_uses_public_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    browser = _browser_with_public_path_cdp(monkeypatch)

    assert browser.cdp.frames.get(selector="#target").id == "child"


def test_browser_cdp_evaluate_uses_frame_selector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cdp_controller = importlib.import_module("agentbrowser.cdp.controller")
    monkeypatch.setattr(cdp_controller, "CDPClient", PublicPathCDPClient)

    browser = Browser(_native_session=NativeSession(native=PublicPathNative()))

    assert browser.cdp.evaluate("document.title", frame="#target") == "context:child-unique"


def test_browser_async_cdp_frames_list_uses_public_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run() -> None:
        browser = await _async_browser_with_public_path_cdp(monkeypatch)

        frames = {frame.id: frame for frame in await browser.cdp.frames.list()}
        assert frames["main"].url == "https://example.com"
        assert frames["child"].name == "target"
        await browser.close()

    asyncio.run(run())


def _browser_with_public_path_cdp(monkeypatch: pytest.MonkeyPatch) -> Browser:
    cdp_controller = importlib.import_module("agentbrowser.cdp.controller")
    monkeypatch.setattr(cdp_controller, "CDPClient", PublicPathCDPClient)
    return Browser(_native_session=NativeSession(native=PublicPathNative()))


async def _async_browser_with_public_path_cdp(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncBrowser:
    cdp_controller = importlib.import_module("agentbrowser.cdp.controller")
    monkeypatch.setattr(cdp_controller, "AsyncCDPClient", PublicPathAsyncCDPClient)
    return AsyncBrowser(_native_session=AsyncNativeSession(native=PublicPathNative()))
