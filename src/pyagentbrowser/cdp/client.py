from __future__ import annotations

import asyncio
import json
from collections import deque
from collections.abc import Mapping
from itertools import count
from threading import RLock
from typing import Any, cast

from pyagentbrowser.cdp._protocol import _decode_message, _response_result
from pyagentbrowser.cdp.errors import CDPTimeoutError
from pyagentbrowser.cdp.transport import AsyncConnect, AsyncWebSocket, SyncConnect, SyncWebSocket


class CDPClient:
    """Synchronous Chrome DevTools Protocol WebSocket client.

    Parameters
    ----------
    url
        CDP WebSocket URL.
    timeout
        Timeout in seconds for individual responses.
    connect
        Optional test or custom WebSocket connector.
    """

    def __init__(
        self,
        url: str,
        *,
        timeout: float = 5.0,
        connect: SyncConnect | None = None,
    ) -> None:
        self._url = url
        self._timeout = timeout
        self._connect = connect
        self._websocket: SyncWebSocket | None = None
        self._ids = count(1)
        self._responses: dict[int, Mapping[str, Any]] = {}
        self._events: deque[Mapping[str, Any]] = deque()
        self._lock = RLock()

    def send(
        self,
        method: str,
        params: Mapping[str, Any] | None = None,
        *,
        session_id: str | None = None,
    ) -> Mapping[str, Any]:
        """Send one CDP method call and return its result object.

        Parameters
        ----------
        method
            CDP method name, for example `Runtime.evaluate`.
        params
            Optional CDP parameter object.
        session_id
            Optional flattened target session id.
        """
        with self._lock:
            request_id = next(self._ids)
            message: dict[str, Any] = {"id": request_id, "method": method}
            if params:
                message["params"] = dict(params)
            if session_id is not None:
                message["sessionId"] = session_id

            self._ensure_connected().send(json.dumps(message))
            response = self._wait_for_response(method, request_id)
            return _response_result(method, response)

    def pop_events(self) -> list[Mapping[str, Any]]:
        """Return queued CDP event messages and clear the queue."""
        with self._lock:
            events = list(self._events)
            self._events.clear()
            return events

    def drain_events(self, *, timeout: float = 0.05) -> list[Mapping[str, Any]]:
        """Read available CDP events until a short timeout expires."""
        with self._lock:
            while True:
                try:
                    self._receive_one(timeout=timeout)
                except TimeoutError:
                    break
            return self.pop_events()

    def close(self) -> None:
        """Close the underlying WebSocket if connected."""
        websocket = self._websocket
        self._websocket = None
        if websocket is not None:
            websocket.close()

    def _ensure_connected(self) -> SyncWebSocket:
        if self._websocket is None:
            connect = self._connect or _load_sync_websocket_connect()
            self._websocket = connect(self._url)
        return self._websocket

    def _wait_for_response(self, method: str, request_id: int) -> Mapping[str, Any]:
        if request_id in self._responses:
            return self._responses.pop(request_id)

        while True:
            try:
                message = self._receive_one(timeout=self._timeout)
            except TimeoutError as err:
                raise CDPTimeoutError(method, self._timeout) from err
            response_id = message.get("id")
            if response_id == request_id:
                return message
            if isinstance(response_id, int):
                self._responses[response_id] = message

    def _receive_one(self, *, timeout: float | None) -> Mapping[str, Any]:
        raw = self._ensure_connected().recv(timeout=timeout)
        message = _decode_message(raw)
        if "id" not in message:
            self._events.append(message)
        return message


class AsyncCDPClient:
    """Async Chrome DevTools Protocol WebSocket client."""

    def __init__(
        self,
        url: str,
        *,
        timeout: float = 5.0,
        connect: AsyncConnect | None = None,
    ) -> None:
        self._url = url
        self._timeout = timeout
        self._connect = connect
        self._websocket: AsyncWebSocket | None = None
        self._ids = count(1)
        self._responses: dict[int, Mapping[str, Any]] = {}
        self._events: deque[Mapping[str, Any]] = deque()
        self._lock = asyncio.Lock()

    async def send(
        self,
        method: str,
        params: Mapping[str, Any] | None = None,
        *,
        session_id: str | None = None,
    ) -> Mapping[str, Any]:
        """Send one CDP method call and return its result object."""
        async with self._lock:
            request_id = next(self._ids)
            message: dict[str, Any] = {"id": request_id, "method": method}
            if params:
                message["params"] = dict(params)
            if session_id is not None:
                message["sessionId"] = session_id

            await (await self._ensure_connected()).send(json.dumps(message))
            response = await self._wait_for_response(method, request_id)
            return _response_result(method, response)

    async def pop_events(self) -> list[Mapping[str, Any]]:
        """Return queued CDP event messages and clear the queue."""
        async with self._lock:
            events = list(self._events)
            self._events.clear()
            return events

    async def drain_events(self, *, timeout: float = 0.05) -> list[Mapping[str, Any]]:
        """Read available CDP events until a short timeout expires."""
        async with self._lock:
            while True:
                try:
                    await self._receive_one(timeout=timeout)
                except TimeoutError:
                    break
            events = list(self._events)
            self._events.clear()
            return events

    async def close(self) -> None:
        """Close the underlying WebSocket if connected."""
        websocket = self._websocket
        self._websocket = None
        if websocket is not None:
            await websocket.close()

    async def _ensure_connected(self) -> AsyncWebSocket:
        if self._websocket is None:
            connect = self._connect or _load_async_websocket_connect()
            self._websocket = await connect(self._url)
        return self._websocket

    async def _wait_for_response(self, method: str, request_id: int) -> Mapping[str, Any]:
        if request_id in self._responses:
            return self._responses.pop(request_id)

        while True:
            try:
                message = await self._receive_one(timeout=self._timeout)
            except TimeoutError as err:
                raise CDPTimeoutError(method, self._timeout) from err
            response_id = message.get("id")
            if response_id == request_id:
                return message
            if isinstance(response_id, int):
                self._responses[response_id] = message

    async def _receive_one(self, *, timeout: float | None) -> Mapping[str, Any]:
        websocket = await self._ensure_connected()
        raw = await asyncio.wait_for(websocket.recv(), timeout=timeout)
        message = _decode_message(raw)
        if "id" not in message:
            self._events.append(message)
        return message


def _load_sync_websocket_connect() -> SyncConnect:
    try:
        from websockets.sync.client import connect
    except ModuleNotFoundError as exc:
        raise ImportError(
            "CDP frame/context evaluation requires the optional cdp extra. "
            'install pyagentbrowser with "pyagentbrowser[cdp]" or install websockets.'
        ) from exc
    return cast(SyncConnect, connect)


def _load_async_websocket_connect() -> AsyncConnect:
    try:
        from websockets.asyncio.client import connect
    except ModuleNotFoundError as exc:
        raise ImportError(
            "Async CDP frame/context evaluation requires the optional cdp extra. "
            'install pyagentbrowser with "pyagentbrowser[cdp]" or install websockets.'
        ) from exc
    return cast(AsyncConnect, connect)
