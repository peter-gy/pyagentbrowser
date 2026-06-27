from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Protocol


class SyncWebSocket(Protocol):
    """Minimal synchronous WebSocket protocol required by `CDPClient`."""

    def send(self, message: str) -> None: ...

    def recv(self, timeout: float | None = None) -> str | bytes: ...

    def close(self) -> None: ...


class AsyncWebSocket(Protocol):
    """Minimal async WebSocket protocol required by `AsyncCDPClient`."""

    async def send(self, message: str) -> None: ...

    async def recv(self) -> str | bytes: ...

    async def close(self) -> None: ...


class SyncCDPTransport(Protocol):
    """Synchronous CDP transport used by page sessions."""

    def send(
        self,
        method: str,
        params: Mapping[str, Any] | None = None,
        *,
        session_id: str | None = None,
    ) -> Mapping[str, Any]: ...

    def drain_events(self, *, timeout: float = 0.05) -> list[Mapping[str, Any]]: ...


class AsyncCDPTransport(Protocol):
    """Async CDP transport used by page sessions."""

    async def send(
        self,
        method: str,
        params: Mapping[str, Any] | None = None,
        *,
        session_id: str | None = None,
    ) -> Mapping[str, Any]: ...

    async def drain_events(self, *, timeout: float = 0.05) -> list[Mapping[str, Any]]: ...


SyncConnect = Callable[[str], SyncWebSocket]
AsyncConnect = Callable[[str], Any]
