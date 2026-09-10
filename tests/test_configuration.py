from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest

from agentbrowser import (
    AsyncBrowser,
    Browser,
    CDPTarget,
    LaunchOptions,
    RestoreOptions,
    SessionOptions,
)

pytestmark = pytest.mark.sdk_dx


@pytest.mark.parametrize(
    "factory,error,match",
    [
        (lambda: CDPTarget(), ValueError, "exactly one"),
        (lambda: CDPTarget(url=""), ValueError, "url"),
        (lambda: CDPTarget(port=0), ValueError, "port"),
        (lambda: SessionOptions(timeout=-1), ValueError, "timeout"),
        (lambda: SessionOptions(allowed_domains=("",)), ValueError, "allowed_domains"),
        (
            lambda: SessionOptions(allowed_domains=cast(Any, "example.com")),
            TypeError,
            "allowed_domains",
        ),
        (lambda: SessionOptions(confirm_actions=cast(Any, "click")), TypeError, "confirm_actions"),
        (lambda: SessionOptions(pin_tab=cast(Any, 1)), TypeError, "pin_tab"),
        (lambda: LaunchOptions(extensions=cast(Any, "extension")), TypeError, "extensions"),
        (lambda: LaunchOptions(args=cast(Any, "--headless")), TypeError, "args"),
        (lambda: LaunchOptions(ca_cert=""), ValueError, "ca_cert"),
        (
            lambda: SessionOptions(
                restore=RestoreOptions("saved"),
                allowed_domains=("example.com",),
            ),
            ValueError,
            "allowed_domains",
        ),
        (
            lambda: Browser.launch(
                LaunchOptions(storage_state="state.json"),
                session=SessionOptions(allowed_domains=("example.com",)),
            ),
            ValueError,
            "storage_state",
        ),
        (
            lambda: Browser.launch(
                LaunchOptions(profile="profile"),
                session=SessionOptions(allowed_domains=("example.com",)),
            ),
            ValueError,
            "profile",
        ),
        (
            lambda: Browser.launch(
                LaunchOptions(args=("--user-data-dir=profile",)),
                session=SessionOptions(allowed_domains=("example.com",)),
            ),
            ValueError,
            "user-data-dir",
        ),
        (
            lambda: Browser.launch(
                LaunchOptions(provider="safari"),
                session=SessionOptions(allowed_domains=("example.com",)),
            ),
            ValueError,
            "safari",
        ),
        (
            lambda: Browser.attach(
                CDPTarget(port=9222),
                session=SessionOptions(allowed_domains=("example.com",)),
            ),
            ValueError,
            "CDP attachment",
        ),
    ],
)
def test_public_configuration_rejects_invalid_values(
    factory: Any,
    error: type[Exception],
    match: str,
) -> None:
    with pytest.raises(error, match=match):
        factory()


def test_webgpu_process_controls_require_a_local_browser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match="webgpu requires a local browser launch"):
        Browser.attach(CDPTarget(port=9222), launch=LaunchOptions(webgpu=True))
    with pytest.raises(ValueError, match="webgpu requires a local browser launch"):
        Browser.launch(LaunchOptions(provider="remote", webgpu=True))
    with pytest.raises(ValueError, match="no_xvfb requires a local browser launch"):
        Browser.attach(CDPTarget(port=9222), launch=LaunchOptions(no_xvfb=True))

    monkeypatch.setenv("AGENT_BROWSER_WEBGPU", "1")
    with pytest.raises(ValueError, match="Pass webgpu=False"):
        Browser.attach(CDPTarget(port=9222))
    monkeypatch.delenv("AGENT_BROWSER_WEBGPU")

    async def run() -> None:
        with pytest.raises(ValueError, match="webgpu requires a local browser launch"):
            await AsyncBrowser.attach(
                CDPTarget(port=9222),
                launch=LaunchOptions(webgpu=True),
            )
        with pytest.raises(ValueError, match="no_xvfb requires a local browser launch"):
            await AsyncBrowser.launch(LaunchOptions(provider="remote", no_xvfb=True))

    asyncio.run(run())


def test_ca_certificate_requires_compatible_local_chromium() -> None:
    options = LaunchOptions(ca_cert="proxy-ca.pem")

    with pytest.raises(ValueError, match="local Chromium"):
        Browser.attach(CDPTarget(port=9222), launch=options)
    with pytest.raises(ValueError, match="local Chromium"):
        Browser.launch(LaunchOptions(ca_cert="proxy-ca.pem", provider="remote"))
    with pytest.raises(ValueError, match="Chrome engine"):
        Browser.launch(LaunchOptions(ca_cert="proxy-ca.pem", engine="lightpanda"))
    with pytest.raises(ValueError, match="profile"):
        Browser.launch(LaunchOptions(ca_cert="proxy-ca.pem", profile="profile"))
    with pytest.raises(ValueError, match="ignore_https_errors"):
        Browser.launch(LaunchOptions(ca_cert="proxy-ca.pem", ignore_https_errors=True))

    async def run() -> None:
        with pytest.raises(ValueError, match="local Chromium"):
            await AsyncBrowser.attach(CDPTarget(port=9222), launch=options)

    asyncio.run(run())


def test_session_dashboard_requires_named_options() -> None:
    with pytest.raises(TypeError, match="DashboardOptions"):
        SessionOptions(dashboard=cast(Any, True))
