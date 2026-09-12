from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, cast

import pytest
from fakes import ScriptedNative
from support.sdk import _command_without_id

from agentbrowser import (
    AsyncBrowser,
    Browser,
    CDPTarget,
    DashboardOptions,
    LaunchOptions,
    SessionOptions,
)
from agentbrowser.transport.async_ import AsyncNativeSession
from agentbrowser.transport.sync import NativeSession

pytestmark = pytest.mark.sdk_dx


def test_public_options_use_named_types_and_python_units(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class CapturingSession:
        def __init__(self, **options: Any) -> None:
            captured.update(options)

    monkeypatch.setattr("agentbrowser.execution.controller.NativeSession", CapturingSession)
    session = SessionOptions(
        timeout=2.5,
        allowed_domains=("example.com", "*.example.org"),
        confirm_actions=("click",),
        auto_dialogs=False,
        pin_tab=True,
        dashboard=DashboardOptions(port=0),
    )

    Browser(session=session)
    assert captured["default_timeout_ms"] == 2500
    assert captured["allowed_domains"] == "example.com,*.example.org"
    assert captured["confirm_actions"] == ("click",)
    assert captured["no_auto_dialog"] is True
    assert captured["pin_tab"] is True
    assert captured["dashboard"] == DashboardOptions(port=0)
    assert LaunchOptions(headless=False).headless is False
    with pytest.raises(TypeError, match="LaunchOptions"):
        cast(Any, Browser.launch)({"headless": True})


def test_launch_options_serialize_browser_process_controls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sync_native = ScriptedNative(default={})
    sync_from_configuration = Browser._from_configuration

    def sync_browser(
        cls: type[Browser],
        configuration: Any,
        *,
        session: SessionOptions | None = None,
        native_session: NativeSession | None = None,
    ) -> Browser:
        del cls, native_session
        return sync_from_configuration(
            configuration,
            session=session,
            native_session=NativeSession(native=sync_native),
        )

    monkeypatch.setattr(Browser, "_from_configuration", classmethod(sync_browser))

    with Browser.launch():
        pass
    with Browser.launch(LaunchOptions(webgpu=True, webmcp=False, no_xvfb=True)):
        pass
    with Browser.attach(
        CDPTarget(port=9222),
        launch=LaunchOptions(webgpu=False, webmcp=True, no_xvfb=False),
    ):
        pass

    sync_default = _command_without_id(sync_native.commands[0])
    assert "webgpu" not in sync_default
    assert "webmcp" not in sync_default
    assert "noXvfb" not in sync_default
    sync_launch = _command_without_id(sync_native.commands[2])
    assert sync_launch["action"] == "launch"
    assert sync_launch["webgpu"] is True
    assert sync_launch["webmcp"] is False
    assert sync_launch["noXvfb"] is True
    sync_attach = _command_without_id(sync_native.commands[4])
    assert sync_attach["cdpPort"] == 9222
    assert sync_attach["webgpu"] is False
    assert sync_attach["webmcp"] is True
    assert sync_attach["noXvfb"] is False

    async def run() -> None:
        async_native = ScriptedNative(default={})
        async_from_configuration = AsyncBrowser._from_configuration

        def async_browser(
            cls: type[AsyncBrowser],
            configuration: Any,
            *,
            session: SessionOptions | None = None,
            native_session: AsyncNativeSession | None = None,
        ) -> AsyncBrowser:
            del cls, native_session
            return async_from_configuration(
                configuration,
                session=session,
                native_session=AsyncNativeSession(native=async_native),
            )

        monkeypatch.setattr(AsyncBrowser, "_from_configuration", classmethod(async_browser))

        async with await AsyncBrowser.launch():
            pass
        async with await AsyncBrowser.launch(
            LaunchOptions(webgpu=True, webmcp=False, no_xvfb=True)
        ):
            pass
        async with await AsyncBrowser.attach(
            CDPTarget(port=9222),
            launch=LaunchOptions(webgpu=False, webmcp=True, no_xvfb=False),
        ):
            pass

        async_default = _command_without_id(async_native.commands[0])
        assert "webgpu" not in async_default
        assert "webmcp" not in async_default
        assert "noXvfb" not in async_default
        async_launch = _command_without_id(async_native.commands[2])
        assert async_launch["action"] == "launch"
        assert async_launch["webgpu"] is True
        assert async_launch["webmcp"] is False
        assert async_launch["noXvfb"] is True
        async_attach = _command_without_id(async_native.commands[4])
        assert async_attach["cdpPort"] == 9222
        assert async_attach["webgpu"] is False
        assert async_attach["webmcp"] is True
        assert async_attach["noXvfb"] is False

    asyncio.run(run())


def test_launch_options_serialize_private_ca_certificate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sync_native = ScriptedNative(default={})
    sync_from_configuration = Browser._from_configuration

    def sync_browser(
        cls: type[Browser],
        configuration: Any,
        *,
        session: SessionOptions | None = None,
        native_session: NativeSession | None = None,
    ) -> Browser:
        del cls, native_session
        return sync_from_configuration(
            configuration,
            session=session,
            native_session=NativeSession(native=sync_native),
        )

    monkeypatch.setattr(Browser, "_from_configuration", classmethod(sync_browser))

    with Browser.launch(LaunchOptions(ca_cert=Path("proxy-ca.pem"))):
        pass

    sync_launch = _command_without_id(sync_native.commands[0])
    assert sync_launch["action"] == "launch"
    assert sync_launch["caCert"] == "proxy-ca.pem"

    async def run() -> None:
        async_native = ScriptedNative(default={})
        async_from_configuration = AsyncBrowser._from_configuration

        def async_browser(
            cls: type[AsyncBrowser],
            configuration: Any,
            *,
            session: SessionOptions | None = None,
            native_session: AsyncNativeSession | None = None,
        ) -> AsyncBrowser:
            del cls, native_session
            return async_from_configuration(
                configuration,
                session=session,
                native_session=AsyncNativeSession(native=async_native),
            )

        monkeypatch.setattr(AsyncBrowser, "_from_configuration", classmethod(async_browser))

        async with await AsyncBrowser.launch(LaunchOptions(ca_cert="proxy-ca.pem")):
            pass

        async_launch = _command_without_id(async_native.commands[0])
        assert async_launch["action"] == "launch"
        assert async_launch["caCert"] == "proxy-ca.pem"

    asyncio.run(run())
