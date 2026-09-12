from __future__ import annotations

import asyncio
from threading import Event

import pytest

from agentbrowser.transport.async_ import AsyncNativeSession
from tests.fakes import ScriptedNative

pytestmark = pytest.mark.sdk_dx


def test_async_queue_preserves_command_timeout_from_submission(monkeypatch):
    async def run():
        now = [100.0]
        monkeypatch.setattr("agentbrowser.transport.deadlines.monotonic", lambda: now[0])
        started, release = Event(), Event()

        def hold(_):
            started.set()
            assert release.wait(2)
            return {"done": True}

        native = ScriptedNative({"hold": hold, "__agent_browser_internal_shutdown": {}})
        session = AsyncNativeSession(native=native)
        first = asyncio.create_task(session.execute("hold"))
        assert await asyncio.to_thread(started.wait, 2)
        try:
            queued = asyncio.create_task(session.execute("probe", _timeoutMs=2_000))
            await asyncio.sleep(0)
            now[0] = 103.0
            release.set()
            await first
            with pytest.raises(TimeoutError, match="before browser dispatch"):
                await queued
            assert [command["action"] for command in native.commands] == ["hold"]
        finally:
            release.set()
            await session.aclose()

    asyncio.run(run())
