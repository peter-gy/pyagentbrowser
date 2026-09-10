from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest
from fakes import ConfirmationNative, ScriptedNative
from support.sdk import _accessibility_audit_data, _browser

from agentbrowser import (
    AccessibilityAudit,
    AsyncBrowser,
    BrowserError,
    ConfirmationRequired,
)
from agentbrowser.transport.async_ import AsyncNativeSession

pytestmark = pytest.mark.sdk_dx


class _InvalidationProbe:
    def __init__(self) -> None:
        self.invalidations = 0

    def invalidate(self) -> None:
        self.invalidations += 1

    def close(self) -> None:
        pass


class _AsyncInvalidationProbe:
    def __init__(self) -> None:
        self.invalidations = 0

    def invalidate(self) -> None:
        self.invalidations += 1

    async def close(self) -> None:
        pass


@pytest.mark.parametrize("action", ["recording_start", "recording_restart"])
def test_recording_navigation_preserves_the_cdp_lifecycle(action: str) -> None:
    native = ScriptedNative({action: {"fps": 30}, "__agent_browser_internal_shutdown": {}})
    with _browser(native) as browser:
        probe = _InvalidationProbe()
        browser._controller._cdp_controller = cast(Any, probe)

        browser.native.data(action, path="take.webm", url="")
        assert probe.invalidations == 0

        browser.native.data(action, path="take.webm", url="https://example.com")
        assert probe.invalidations == 1

        native.replies[action] = {"success": False, "error": "Capture failed after navigation"}
        response = browser.native.execute(action, path="take.webm", url="https://example.com")
        assert response.success is False
        assert probe.invalidations == 2


@pytest.mark.parametrize("action", ["recording_start", "recording_restart"])
def test_confirmed_recording_navigation_invalidates_cdp(action: str) -> None:
    native = ConfirmationNative(action=action, result={"fps": 30})
    with _browser(native) as browser:
        probe = _InvalidationProbe()
        browser._controller._cdp_controller = cast(Any, probe)

        pending = browser.native.execute(action, path="take.webm", url="https://example.com")
        assert pending.success is True
        assert probe.invalidations == 0

        browser.native.data("confirm", confirmation_id=native.confirmation_id)
        assert probe.invalidations == 1


@pytest.mark.parametrize("action", ["recording_start", "recording_restart"])
def test_async_recording_navigation_preserves_the_cdp_lifecycle(action: str) -> None:
    async def run() -> None:
        native = ScriptedNative({action: {"fps": 30}, "__agent_browser_internal_shutdown": {}})
        async with AsyncBrowser(_native_session=AsyncNativeSession(native=native)) as browser:
            probe = _AsyncInvalidationProbe()
            browser._controller._cdp_controller = cast(Any, probe)

            await browser.native.data(action, path="take.webm")
            assert probe.invalidations == 0

            await browser.native.data(action, path="take.webm", url="https://example.com")
            assert probe.invalidations == 1

            native.replies[action] = {"success": False, "error": "Capture failed after navigation"}
            response = await browser.native.execute(
                action, path="take.webm", url="https://example.com"
            )
            assert response.success is False
            assert probe.invalidations == 2

    asyncio.run(run())


@pytest.mark.parametrize("action", ["recording_start", "recording_restart"])
def test_async_confirmed_recording_navigation_invalidates_cdp(action: str) -> None:
    async def run() -> None:
        native = ConfirmationNative(action=action, result={"fps": 30})
        async with AsyncBrowser(_native_session=AsyncNativeSession(native=native)) as browser:
            probe = _AsyncInvalidationProbe()
            browser._controller._cdp_controller = cast(Any, probe)

            with pytest.raises(ConfirmationRequired) as pending:
                await browser.native.data(action, path="take.webm", url="https://example.com")
            assert probe.invalidations == 0

            await pending.value.pending.confirm()
            assert probe.invalidations == 1

    asyncio.run(run())


def test_accessibility_audit_invalidates_cdp_only_when_it_navigates() -> None:
    native = ScriptedNative(
        {
            "a11y": _accessibility_audit_data(),
            "__agent_browser_internal_shutdown": {},
        }
    )
    browser = _browser(native)
    probe = _InvalidationProbe()
    browser._controller._cdp_controller = cast(Any, probe)

    browser.diagnostics.accessibility()
    assert probe.invalidations == 0

    browser.diagnostics.accessibility("example.com")
    assert probe.invalidations == 1
    browser.close()


def test_accessibility_url_failure_invalidates_cdp_after_navigation_attempt() -> None:
    native = ScriptedNative(
        {
            "a11y": {
                "success": False,
                "error": "No element matches selector: #missing",
            },
            "__agent_browser_internal_shutdown": {},
        }
    )
    browser = _browser(native)
    probe = _InvalidationProbe()
    browser._controller._cdp_controller = cast(Any, probe)

    with pytest.raises(BrowserError, match="No element matches"):
        browser.diagnostics.accessibility("example.com", selector="#missing")

    assert probe.invalidations == 1
    browser.close()


def test_raw_accessibility_calls_preserve_the_cdp_lifecycle() -> None:
    def a11y(command: dict[str, Any]) -> dict[str, Any]:
        if command.get("selector") == "#missing":
            return {
                "success": False,
                "error": "No element matches selector: #missing",
            }
        return _accessibility_audit_data()

    native = ScriptedNative(
        {
            "a11y": a11y,
            "__agent_browser_internal_shutdown": {},
        }
    )
    browser = _browser(native)
    probe = _InvalidationProbe()
    browser._controller._cdp_controller = cast(Any, probe)

    browser.native.data("a11y")
    assert probe.invalidations == 0

    browser.native.data("a11y", url="https://example.com")
    assert probe.invalidations == 1

    response = browser.native.execute(
        "a11y",
        url="https://example.com",
        selector="#missing",
    )
    assert response.success is False
    assert probe.invalidations == 2
    browser.close()


@pytest.mark.parametrize(
    ("url", "expected_invalidations"),
    [(None, 0), ("https://example.com", 1)],
)
def test_confirmed_accessibility_audit_preserves_navigation_lifecycle(
    url: str | None,
    expected_invalidations: int,
) -> None:
    native = ConfirmationNative(action="a11y", result=_accessibility_audit_data())
    browser = _browser(native)
    probe = _InvalidationProbe()
    browser._controller._cdp_controller = cast(Any, probe)

    with pytest.raises(ConfirmationRequired) as required:
        browser.diagnostics.accessibility(url)

    assert probe.invalidations == 0
    assert isinstance(required.value.pending.confirm(), AccessibilityAudit)
    assert probe.invalidations == expected_invalidations
    browser.close()


def test_raw_confirmed_accessibility_audit_preserves_navigation_lifecycle() -> None:
    native = ConfirmationNative(action="a11y", result=_accessibility_audit_data())
    browser = _browser(native)
    probe = _InvalidationProbe()
    browser._controller._cdp_controller = cast(Any, probe)

    pending = browser.native.execute("a11y", url="https://example.com")
    assert pending.success is True
    assert probe.invalidations == 0

    confirmed = browser.native.execute(
        "confirm",
        confirmation_id=native.confirmation_id,
    )
    assert confirmed.success is True
    assert probe.invalidations == 1
    browser.close()


def test_async_accessibility_audit_preserves_the_cdp_lifecycle() -> None:
    async def run() -> None:
        def a11y(command: dict[str, Any]) -> dict[str, Any]:
            if "url" in command:
                return {
                    "success": False,
                    "error": "No element matches selector: #missing",
                }
            return _accessibility_audit_data()

        native = ScriptedNative(
            {
                "a11y": a11y,
                "__agent_browser_internal_shutdown": {},
            }
        )
        browser = AsyncBrowser(_native_session=AsyncNativeSession(native=native))
        probe = _AsyncInvalidationProbe()
        browser._controller._cdp_controller = cast(Any, probe)

        await browser.diagnostics.accessibility()
        assert probe.invalidations == 0

        with pytest.raises(BrowserError, match="No element matches"):
            await browser.diagnostics.accessibility(
                "example.com",
                selector="#missing",
            )

        assert probe.invalidations == 1
        await browser.close()

    asyncio.run(run())


def test_async_confirmed_accessibility_audit_preserves_navigation_lifecycle() -> None:
    async def run() -> None:
        native = ConfirmationNative(action="a11y", result=_accessibility_audit_data())
        browser = AsyncBrowser(_native_session=AsyncNativeSession(native=native))
        probe = _AsyncInvalidationProbe()
        browser._controller._cdp_controller = cast(Any, probe)

        with pytest.raises(ConfirmationRequired) as required:
            await browser.diagnostics.accessibility("example.com")

        assert probe.invalidations == 0
        assert isinstance(await required.value.pending.confirm(), AccessibilityAudit)
        assert probe.invalidations == 1
        await browser.close()

    asyncio.run(run())
