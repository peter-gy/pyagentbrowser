from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, overload

from agentbrowser.contracts.protocol import BrowserResponse
from agentbrowser.contracts.types import JSONMapping, JSONValue

if TYPE_CHECKING:
    from agentbrowser.execution.controller import Controller
    from agentbrowser.execution.controller_async import AsyncController


@dataclass(frozen=True, slots=True)
class Native:
    """Raw native command boundary for a `Browser`."""

    _controller: Controller

    def execute(self, action: str, **params: Any) -> BrowserResponse:
        """Run a native command and return the response envelope."""
        return self._controller._native_execute(action, **params)

    @overload
    def data(self, action: str, **params: Any) -> JSONMapping: ...

    @overload
    def data(
        self,
        action: str,
        *,
        expect: Literal["object"],
        **params: Any,
    ) -> JSONMapping: ...

    @overload
    def data(
        self,
        action: str,
        *,
        expect: Literal["any"],
        **params: Any,
    ) -> JSONValue: ...

    def data(
        self,
        action: str,
        *,
        expect: str = "object",
        **params: Any,
    ) -> JSONMapping | JSONValue:
        """Run a native command and return checked response data.

        `expect="object"` requires object-shaped response data. Use
        `expect="any"` for native actions whose `data` is a scalar, array, or
        `null`.
        """
        return self._controller._native_data(action, expect=expect, **params)


@dataclass(frozen=True, slots=True)
class AsyncNative:
    """Raw native command boundary for an `AsyncBrowser`."""

    _controller: AsyncController

    async def execute(self, action: str, **params: Any) -> BrowserResponse:
        """Run a native command and return the response envelope."""
        return await self._controller._native_execute(action, **params)

    @overload
    async def data(self, action: str, **params: Any) -> JSONMapping: ...

    @overload
    async def data(
        self,
        action: str,
        *,
        expect: Literal["object"],
        **params: Any,
    ) -> JSONMapping: ...

    @overload
    async def data(
        self,
        action: str,
        *,
        expect: Literal["any"],
        **params: Any,
    ) -> JSONValue: ...

    async def data(
        self,
        action: str,
        *,
        expect: str = "object",
        **params: Any,
    ) -> JSONMapping | JSONValue:
        """Run a native command and return checked response data.

        `expect="object"` requires object-shaped response data. Use
        `expect="any"` for native actions whose `data` is a scalar, array, or
        `null`.
        """
        return await self._controller._native_data(action, expect=expect, **params)
