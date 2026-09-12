from __future__ import annotations

import asyncio
import json
from collections import deque
from collections.abc import Mapping
from typing import Any


class FakeWebSocket:
    def __init__(
        self,
        messages: list[Mapping[str, Any]] | None = None,
        *,
        responses: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        self.messages = deque(json.dumps(message) for message in messages or [])
        self.responses = dict(responses or {})
        self.sent: list[dict[str, Any]] = []
        self.closed = False

    def send(self, message: str) -> None:
        request = json.loads(message)
        self.sent.append(request)
        result = self.responses.get(str(request["method"]))
        if result is not None:
            self.messages.append(json.dumps({"id": request["id"], "result": dict(result)}))

    def recv(self, timeout: float | None = None) -> str:
        if not self.messages:
            raise TimeoutError
        return self.messages.popleft()

    def close(self) -> None:
        self.closed = True


class FakeWebSocketContext:
    def __init__(self, websocket: FakeWebSocket) -> None:
        self.websocket = websocket
        self.entered = False
        self.exited = False

    def __enter__(self) -> FakeWebSocket:
        self.entered = True
        return self.websocket

    def __exit__(self, *_args: object) -> None:
        self.exited = True
        self.websocket.close()


class DelayedAsyncWebSocket:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.sent_event = asyncio.Event()
        self.response_event = asyncio.Event()
        self.closed = False

    async def send(self, message: str) -> None:
        self.sent.append(json.loads(message))
        self.sent_event.set()

    async def recv(self) -> str:
        await self.response_event.wait()
        return json.dumps({"id": self.sent[0]["id"], "result": {"ok": True}})

    async def close(self) -> None:
        self.closed = True
