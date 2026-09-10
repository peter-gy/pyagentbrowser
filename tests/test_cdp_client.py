from __future__ import annotations

import asyncio
import builtins
import importlib
import json
from typing import Any

import pytest

from agentbrowser import AgentBrowserError
from agentbrowser.cdp import (
    AsyncCDPClient,
    CDPClient,
    CDPClosedError,
    CDPError,
    CDPTimeoutError,
)
from tests.support.cdp_socket import DelayedAsyncWebSocket, FakeWebSocket, FakeWebSocketContext

pytestmark = pytest.mark.sdk_dx


def test_cdp_client_queues_events_while_waiting_for_response() -> None:
    class EventBeforeResponseWebSocket(FakeWebSocket):
        def send(self, message: str) -> None:
            request = json.loads(message)
            self.sent.append(request)
            if request["method"] == "Runtime.evaluate":
                self.messages.extend(
                    [
                        json.dumps(
                            {
                                "method": "Runtime.executionContextCreated",
                                "params": {"context": {"id": 1}},
                            }
                        ),
                        json.dumps({"id": request["id"], "result": {"ok": True}}),
                    ]
                )

    websocket = EventBeforeResponseWebSocket()
    client = CDPClient("ws://cdp", connect=lambda _url: websocket)

    assert client.send("Runtime.evaluate", {"expression": "1"}, session_id="s1") == {"ok": True}
    assert client.pop_events()[0]["method"] == "Runtime.executionContextCreated"


def test_cdp_client_owns_default_websocket_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    websocket = FakeWebSocket(responses={"Browser.getVersion": {"product": "Chrome"}})
    context = FakeWebSocketContext(websocket)

    def connect(url: str) -> FakeWebSocketContext:
        assert url == "ws://cdp"
        return context

    client_module = importlib.import_module("agentbrowser.cdp.client")
    monkeypatch.setattr(client_module, "_load_sync_websocket_connect", lambda: connect)
    client = CDPClient("ws://cdp")

    assert client.send("Browser.getVersion") == {"product": "Chrome"}
    client.close()

    assert context.entered is True
    assert context.exited is True
    assert websocket.closed is True


def test_cdp_client_timeout_is_typed_sdk_error() -> None:
    client = CDPClient("ws://cdp", timeout=0.25, connect=lambda _url: FakeWebSocket([]))

    with pytest.raises(CDPTimeoutError) as exc_info:
        client.send("Runtime.evaluate", {"expression": "1"})

    assert exc_info.value.method == "Runtime.evaluate"
    assert isinstance(exc_info.value, CDPError)
    assert isinstance(exc_info.value, AgentBrowserError)


def test_cdp_client_rejects_send_after_close() -> None:
    client = CDPClient("ws://cdp", connect=lambda _url: FakeWebSocket([]))

    client.close()

    with pytest.raises(CDPClosedError, match="CDP client is closed"):
        client.send("Runtime.evaluate", {"expression": "1"})


def test_cdp_client_rejects_event_drain_after_close() -> None:
    client = CDPClient("ws://cdp", connect=lambda _url: FakeWebSocket([]))

    client.close()

    with pytest.raises(CDPClosedError, match="CDP client is closed"):
        client.drain_events()


def test_async_cdp_client_rejects_send_after_close() -> None:
    async def run() -> None:
        client = AsyncCDPClient("ws://cdp")

        await client.close()

        with pytest.raises(CDPClosedError, match="CDP client is closed"):
            await client.send("Runtime.evaluate", {"expression": "1"})

    asyncio.run(run())


def test_async_cdp_client_close_wins_over_in_flight_response() -> None:
    async def run() -> None:
        websocket = DelayedAsyncWebSocket()

        async def connect(_url: str) -> DelayedAsyncWebSocket:
            return websocket

        client = AsyncCDPClient("ws://cdp", connect=connect)
        pending = asyncio.create_task(client.send("Runtime.evaluate"))
        await websocket.sent_event.wait()

        await client.close()
        websocket.response_event.set()

        with pytest.raises(CDPClosedError, match="CDP client is closed"):
            await pending
        assert websocket.closed is True

    asyncio.run(run())


def test_cdp_client_optional_extra_error_is_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    _block_websockets_import(monkeypatch)

    with pytest.raises(ImportError, match=r"pyagentbrowser\[cdp\]"):
        CDPClient("ws://cdp").send("Browser.getVersion")


def test_async_cdp_client_optional_extra_error_is_actionable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _block_websockets_import(monkeypatch)

    async def run() -> None:
        with pytest.raises(ImportError, match=r"pyagentbrowser\[cdp\]"):
            await AsyncCDPClient("ws://cdp").send("Browser.getVersion")

    asyncio.run(run())


def _block_websockets_import(monkeypatch: pytest.MonkeyPatch) -> None:
    original_import = builtins.__import__

    def import_without_websockets(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.startswith("websockets"):
            raise ModuleNotFoundError("No module named 'websockets'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_websockets)


@pytest.mark.parametrize("asynchronous", [False, True])
def test_loaded_transport_mismatch_reports_paths_and_recovery(monkeypatch, asynchronous):
    websockets = pytest.importorskip("websockets")
    monkeypatch.setattr(websockets, "__version__", "stale")
    from agentbrowser.cdp import AsyncCDPClient, CDPClient

    with pytest.raises(
        ImportError, match="loaded websockets stale differs from installed"
    ) as caught:
        if asynchronous:
            asyncio.run(AsyncCDPClient("ws://127.0.0.1:9").send("Browser.getVersion"))
        else:
            CDPClient("ws://127.0.0.1:9").send("Browser.getVersion")
    assert str(websockets.__file__) in str(caught.value)
    assert "restart the Python process" in str(caught.value)
