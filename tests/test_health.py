from __future__ import annotations

import pytest

from agentbrowser import Browser
from agentbrowser.session import NativeSession
from tests.fakes import EchoNative

pytestmark = pytest.mark.sdk_dx


def test_importable_public_transports_report_available():
    pytest.importorskip("websockets.sync.client")
    pytest.importorskip("websockets.asyncio.client")
    browser = Browser()

    check = next(entry for entry in browser.healthcheck().checks if entry.name == "direct_cdp")

    assert check.status == "ready"
    assert browser.capabilities().direct_cdp


def test_loaded_dependency_mismatch_reports_recovery_and_preserves_native_operations(monkeypatch):
    websockets = pytest.importorskip("websockets")
    monkeypatch.setattr(websockets, "__version__", "stale")
    native = EchoNative()
    browser = Browser(_native_session=NativeSession(native=native))

    check = next(entry for entry in browser.healthcheck().checks if entry.name == "direct_cdp")

    assert check.status == "unavailable"
    assert "loaded websockets stale differs from installed" in check.detail
    assert check.module_path is not None
    assert check.recovery is not None and "Restart the Python process" in check.recovery
    assert not browser.capabilities().direct_cdp
    assert native.commands == []
    assert browser.native.execute("session_info").success
