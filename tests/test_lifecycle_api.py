from __future__ import annotations

import asyncio
from pathlib import Path
from threading import Event
from typing import Any

import pytest
from fakes import ScriptedNative
from support.sdk import _browser, _session_status_data

from agentbrowser import (
    AsyncBrowser,
    Browser,
    CloseResult,
    NativeParseError,
    RestoreSaveError,
    SessionStatus,
)
from agentbrowser.transport.async_ import AsyncNativeSession
from agentbrowser.transport.sync import NativeSession

pytestmark = pytest.mark.sdk_dx


def test_session_namespace_returns_typed_lifecycle_status() -> None:
    native = ScriptedNative({"session_info": _session_status_data()})
    browser = _browser(native)

    status = browser.session.status()

    assert status == SessionStatus(
        session_id="research",
        namespace="worker-a",
        socket_dir=Path("/tmp/agent-browser"),
        background_pid=42,
        browser_launched=True,
        page_count=2,
        engine="chrome",
        launch_hash=101,
        compatibility_status="current",
        restore_key="research",
        restore_status="loaded",
        restore_status_detail=None,
        restore_loaded_path=Path("/tmp/research.json"),
        restore_validation_pending=False,
        restore_save="always",
        save_status="saved",
        restore_saved_path=Path("/tmp/research.json"),
        restore_check_url=None,
        restore_check_text="Dashboard",
        restore_check_fn=None,
        raw=_session_status_data(),
    )
    assert native.commands[0]["action"] == "session_info"


def test_session_status_requires_native_lifecycle_fields() -> None:
    data = _session_status_data()
    del data["restoreStatus"]
    browser = _browser(ScriptedNative({"session_info": data}))

    with pytest.raises(NativeParseError, match="restoreStatus"):
        browser.session.status()


def test_close_is_idempotent_and_browser_cannot_be_reused() -> None:
    native = ScriptedNative(
        {
            "__agent_browser_internal_shutdown": {
                "closed": True,
                "restoreStatus": "loaded",
                "saveStatus": "saved",
                "statePath": "/tmp/research.json",
            }
        }
    )
    browser = _browser(native)

    first = browser.close()
    second = browser.close()

    assert first is second
    assert first == CloseResult(
        closed=True,
        restore_status="loaded",
        save_status="saved",
        state_path=Path("/tmp/research.json"),
        raw={
            "closed": True,
            "restoreStatus": "loaded",
            "saveStatus": "saved",
            "statePath": "/tmp/research.json",
        },
    )
    assert browser.closed is True
    assert len(native.commands) == 1
    with pytest.raises(RuntimeError, match="closed"):
        browser.native.data("probe")


def test_close_surfaces_restore_save_errors_after_terminal_cleanup() -> None:
    native = ScriptedNative(
        {
            "__agent_browser_internal_shutdown": {
                "closed": True,
                "restoreStatus": "loaded",
                "saveStatus": "error",
                "saveError": "permission denied",
            }
        }
    )
    browser = _browser(native)

    with pytest.raises(RestoreSaveError, match="permission denied") as failed:
        browser.close()

    assert failed.value.result.closed is True
    assert browser.closed is True
    with pytest.raises(RestoreSaveError, match="permission denied"):
        browser.close()


def test_close_rejects_missing_native_save_status() -> None:
    browser = _browser(
        ScriptedNative(
            {
                "__agent_browser_internal_shutdown": {
                    "closed": True,
                    "restoreStatus": "loaded",
                }
            }
        )
    )

    with pytest.raises(NativeParseError, match="saveStatus"):
        browser.close()
    assert browser.closed is True
    with pytest.raises(NativeParseError, match="saveStatus"):
        browser.close()


def test_closing_an_unused_browser_does_not_start_its_native_session() -> None:
    session = NativeSession()
    browser = Browser(_native_session=session)

    assert session.started is False
    result = browser.close()
    assert session.started is False
    assert browser.closed is True
    assert result == CloseResult(closed=True)


def test_async_close_is_single_flight() -> None:
    async def run() -> None:
        started = Event()
        release = Event()

        def close_reply(_command: dict[str, Any]) -> dict[str, Any]:
            started.set()
            release.wait(timeout=5)
            return {
                "closed": True,
                "restoreStatus": "not_configured",
                "saveStatus": "not_configured",
            }

        native = ScriptedNative(
            {
                "probe": {},
                "__agent_browser_internal_shutdown": close_reply,
            }
        )
        browser = AsyncBrowser(_native_session=AsyncNativeSession(native=native))
        await browser.native.data("probe")

        first_close = asyncio.create_task(browser.close())
        assert await asyncio.to_thread(started.wait, 1)
        second_close = asyncio.create_task(browser.close())
        await asyncio.sleep(0)
        assert second_close.done() is False
        release.set()
        first, second = await asyncio.gather(first_close, second_close)

        assert first is second
        assert [
            command["action"]
            for command in native.commands
            if command["action"] == "__agent_browser_internal_shutdown"
        ] == ["__agent_browser_internal_shutdown"]

    asyncio.run(run())


def test_async_close_replays_the_terminal_decode_error() -> None:
    async def run() -> None:
        native = ScriptedNative(
            {
                "probe": {},
                "__agent_browser_internal_shutdown": {
                    "closed": True,
                    "restoreStatus": "loaded",
                },
            }
        )
        browser = AsyncBrowser(_native_session=AsyncNativeSession(native=native))
        await browser.native.data("probe")

        for _attempt in range(2):
            with pytest.raises(NativeParseError, match="saveStatus"):
                await browser.close()

        assert [
            command["action"]
            for command in native.commands
            if command["action"] == "__agent_browser_internal_shutdown"
        ] == ["__agent_browser_internal_shutdown"]

    asyncio.run(run())


def test_async_close_timeout_preserves_shared_cleanup_and_result() -> None:
    async def run() -> None:
        started, release = Event(), Event()

        def close_reply(_command: dict[str, Any]) -> dict[str, Any]:
            started.set()
            assert release.wait(3)
            return {
                "closed": True,
                "restoreStatus": "not_configured",
                "saveStatus": "not_configured",
            }

        native = ScriptedNative({"probe": {}, "__agent_browser_internal_shutdown": close_reply})
        browser = AsyncBrowser(_native_session=AsyncNativeSession(native=native))
        await browser.native.data("probe")
        short_wait = asyncio.create_task(browser.close(timeout=0.02))
        assert await asyncio.to_thread(started.wait, 1)
        patient_wait = asyncio.create_task(browser.close())
        try:
            with pytest.raises(TimeoutError):
                await short_wait
            assert browser.closed
            assert not patient_wait.done()
            release.set()
            closed = await asyncio.wait_for(patient_wait, 1)
            assert closed.closed
            assert await browser.close() is closed
            assert [command["action"] for command in native.commands].count(
                "__agent_browser_internal_shutdown"
            ) == 1
        finally:
            release.set()
            await asyncio.gather(short_wait, patient_wait, return_exceptions=True)

    asyncio.run(run())
