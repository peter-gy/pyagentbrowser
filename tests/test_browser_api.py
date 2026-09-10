from __future__ import annotations

import asyncio

import pytest
from fakes import ScriptedNative
from support.sdk import _browser, _command_without_id, _session_status_data

from agentbrowser import (
    AsyncBrowser,
    NativeParseError,
    ReadMode,
    ReadResult,
)
from agentbrowser.transport.async_ import AsyncNativeSession

pytestmark = pytest.mark.sdk_dx


def test_capabilities_and_healthcheck_do_not_launch_browser() -> None:
    browser = _browser(ScriptedNative(default={}))

    capabilities = browser.capabilities()
    health = browser.healthcheck()

    assert capabilities.screenshots and capabilities.image_bytes
    assert not capabilities.host_image_delivery
    assert {check.name for check in health.checks} == {"pillow", "direct_cdp"}
    assert not browser.is_launched


def test_browser_core_is_agent_first_and_returns_typed_values() -> None:
    native = ScriptedNative(
        {
            "launch": {},
            "navigate": {},
            "title": {"title": "Example"},
            "url": {"url": "https://example.com/"},
        }
    )
    browser = _browser(native)

    assert browser.page.open("example.com", wait_until="domcontentloaded") is None
    assert browser.page.title() == "Example"
    assert browser.page.url() == "https://example.com/"
    assert _command_without_id(native.commands[1]) == {
        "action": "navigate",
        "url": "https://example.com",
        "waitUntil": "domcontentloaded",
    }


@pytest.mark.parametrize("action,field", [("title", "title"), ("url", "url"), ("content", "html")])
def test_browser_core_rejects_missing_typed_fields(action: str, field: str) -> None:
    browser = _browser(ScriptedNative({action: {}}))

    with pytest.raises(NativeParseError, match=field):
        getattr(browser.page, action)()


def test_emulation_groups_environment_commands_and_hides_native_payloads() -> None:
    native = ScriptedNative({"viewport": {"width": 800, "height": 600}})
    browser = _browser(native)

    assert browser.emulation.viewport(800, 600, device_scale_factor=2) is None
    assert _command_without_id(native.commands[0]) == {
        "action": "viewport",
        "width": 800,
        "height": 600,
        "deviceScaleFactor": 2,
        "mobile": False,
    }


def test_dashboard_namespace_reports_status_and_stops_streaming() -> None:
    native = ScriptedNative(
        {
            "stream_status": {"enabled": True, "port": 4312},
            "stream_disable": {},
        }
    )
    browser = _browser(native)

    assert browser.dashboard.status()["port"] == 4312
    assert browser.dashboard.stop() is None


def test_read_returns_typed_content_and_serializes_mode() -> None:
    native = ScriptedNative(
        {
            "read": {
                "url": "https://example.com/docs",
                "finalUrl": "https://example.com/docs",
                "status": 200,
                "contentType": "text/markdown",
                "source": "accept-markdown-outline",
                "truncated": False,
                "content": "# Outline\n",
            }
        }
    )
    browser = _browser(native)

    result = browser.page.read(
        "example.com/docs",
        mode=ReadMode.outline_only(),
        timeout_ms=1_000,
    )

    assert isinstance(result, ReadResult)
    assert result.content == "# Outline\n"
    assert native.commands[0]["url"] == "https://example.com/docs"
    assert native.commands[0]["outline"] is True
    assert native.commands[0]["timeout"] == 1_000


def test_async_core_uses_the_same_nouns() -> None:
    async def run() -> None:
        native = ScriptedNative(
            {
                "launch": {},
                "navigate": {},
                "title": {"title": "Async"},
                "session_info": _session_status_data(),
                "__agent_browser_internal_shutdown": {
                    "closed": True,
                    "restoreStatus": "loaded",
                    "saveStatus": "saved",
                },
            }
        )
        browser = AsyncBrowser(
            _native_session=AsyncNativeSession(native=native),
        )

        assert await browser.page.open("example.com") is None
        assert await browser.page.title() == "Async"
        assert (await browser.session.status()).restore_status == "loaded"
        result = await browser.close()
        assert result.save_status == "saved"
        assert await browser.close() is result
        assert browser.closed is True

    asyncio.run(run())
