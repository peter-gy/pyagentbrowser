from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from agentbrowser.cdp import AsyncCDPController, CDPController


@dataclass(frozen=True, slots=True)
class CDPFrames:
    """CDP frame discovery helpers."""

    controller: Callable[[], CDPController]

    def list(self) -> Sequence[Any]:
        """Return frames for the active CDP page target."""
        return self.controller().frames()

    def get(
        self,
        *,
        selector: str | None = None,
        name: str | None = None,
        url: str | None = None,
    ) -> Any:
        """Return one CDP frame selected by iframe selector, name, or URL."""
        return self.controller().frame(selector=selector, name=name, url=url)


@dataclass(frozen=True, slots=True)
class CDP:
    """High-level Chrome DevTools Protocol helpers."""

    controller: Callable[[], CDPController]
    frames: CDPFrames = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "frames", CDPFrames(self.controller))

    def evaluate(
        self,
        script: str,
        *,
        frame: Any = None,
        extension_id: str | None = None,
        context: Any = None,
        await_promise: bool = True,
        return_by_value: bool = True,
    ) -> Any:
        """Evaluate JavaScript through CDP in a frame or execution context."""
        return self.controller().evaluate(
            script,
            frame=frame,
            extension_id=extension_id,
            context=context,
            await_promise=await_promise,
            return_by_value=return_by_value,
        )

    def send(
        self,
        method: str,
        params: Mapping[str, Any] | None = None,
        *,
        session_id: str | None = None,
    ) -> Mapping[str, Any]:
        """Send one raw Chrome DevTools Protocol method."""
        return self.controller().send(method, params, session_id=session_id)

    def target(
        self,
        *,
        label: str | None = None,
        url: str | None = None,
        target_id: str | None = None,
    ) -> Any:
        """Return a CDP target handle selected by label, URL, or target id."""
        return self.controller().target(label=label, url=url, target_id=target_id)


@dataclass(frozen=True, slots=True)
class AsyncCDPFrames:
    """Async CDP frame discovery helpers."""

    controller: Callable[[], AsyncCDPController]

    async def list(self) -> Sequence[Any]:
        """Return frames for the active CDP page target."""
        return await self.controller().frames()

    async def get(
        self,
        *,
        selector: str | None = None,
        name: str | None = None,
        url: str | None = None,
    ) -> Any:
        """Return one CDP frame selected by iframe selector, name, or URL."""
        return await self.controller().frame(selector=selector, name=name, url=url)


@dataclass(frozen=True, slots=True)
class AsyncCDP:
    """Async high-level Chrome DevTools Protocol helpers."""

    controller: Callable[[], AsyncCDPController]
    frames: AsyncCDPFrames = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "frames", AsyncCDPFrames(self.controller))

    async def evaluate(
        self,
        script: str,
        *,
        frame: Any = None,
        extension_id: str | None = None,
        context: Any = None,
        await_promise: bool = True,
        return_by_value: bool = True,
    ) -> Any:
        """Evaluate JavaScript through CDP in a frame or execution context."""
        return await self.controller().evaluate(
            script,
            frame=frame,
            extension_id=extension_id,
            context=context,
            await_promise=await_promise,
            return_by_value=return_by_value,
        )

    async def send(
        self,
        method: str,
        params: Mapping[str, Any] | None = None,
        *,
        session_id: str | None = None,
    ) -> Mapping[str, Any]:
        """Send one raw Chrome DevTools Protocol method."""
        return await self.controller().send(method, params, session_id=session_id)

    def target(
        self,
        *,
        label: str | None = None,
        url: str | None = None,
        target_id: str | None = None,
    ) -> Any:
        """Return a CDP target handle selected by label, URL, or target id."""
        return self.controller().target(label=label, url=url, target_id=target_id)
