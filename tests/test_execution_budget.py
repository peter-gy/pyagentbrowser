from __future__ import annotations

import asyncio
from threading import Event

import pytest

from agentbrowser import (
    CallbackHost,
    ExecutionContext,
    ImageDelivery,
    OpenTarget,
    bind_host,
    reset_host,
)
from agentbrowser.session import NativeSession
from agentbrowser.session_async import AsyncNativeSession
from tests.fakes import EchoNative, ScriptedNative

pytestmark = pytest.mark.sdk_dx


def test_execution_budget_decreases_and_stops_dispatch_but_allows_cleanup(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("agentbrowser.host.monotonic", lambda: now[0])
    context = ExecutionContext(timeout_ms=5_000)
    native = EchoNative()
    session = NativeSession(native=native)
    token = bind_host(
        CallbackHost(OpenTarget("https://example.com"), lambda _: ImageDelivery("queued"), context)
    )
    try:
        now[0] = 101.0
        assert context.limit(8_000) == 3_000
        session.execute("probe")
        assert native.commands[-1]["_timeoutMs"] == 3_000
        now[0] = 105.0
        with pytest.raises(TimeoutError, match="before browser dispatch"):
            session.execute("probe")
        session.execute("__agent_browser_internal_shutdown")
        assert [command["action"] for command in native.commands] == [
            "probe",
            "__agent_browser_internal_shutdown",
        ]
    finally:
        reset_host(token)


def test_async_queue_preserves_deadline_from_submission(monkeypatch):
    async def run():
        now = [100.0]
        monkeypatch.setattr("agentbrowser.host.monotonic", lambda: now[0])
        started, release = Event(), Event()

        def hold(_):
            started.set()
            assert release.wait(2)
            return {"done": True}

        native = ScriptedNative({"hold": hold, "__agent_browser_internal_shutdown": {}})
        session = AsyncNativeSession(native=native)
        first = asyncio.create_task(session.execute("hold"))
        assert await asyncio.to_thread(started.wait, 2)
        token = bind_host(
            CallbackHost(
                OpenTarget("https://example.com"),
                lambda _: ImageDelivery("queued"),
                ExecutionContext(timeout_ms=2_000),
            )
        )
        try:
            queued = asyncio.create_task(session.execute("probe"))
            await asyncio.sleep(0)
            now[0] = 103.0
            release.set()
            await first
            with pytest.raises(TimeoutError, match="before browser dispatch"):
                await queued
            assert [command["action"] for command in native.commands] == ["hold"]
        finally:
            release.set()
            reset_host(token)
            await session.aclose()

    asyncio.run(run())
