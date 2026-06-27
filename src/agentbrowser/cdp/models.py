from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

ContextPredicate = Callable[["ExecutionContext"], bool]
AsyncContextPredicate = Callable[["AsyncExecutionContext"], bool]


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Synchronous JavaScript execution context."""

    id: int
    unique_id: str | None
    frame_id: str | None
    origin: str
    name: str
    type: str
    is_default: bool
    _owner: Any = field(repr=False, compare=False)
    _session_id: str = field(repr=False, compare=False)
    _generation: int = field(repr=False, compare=False)

    def evaluate(
        self,
        script: str,
        *,
        await_promise: bool = True,
        return_by_value: bool = True,
    ) -> Any:
        """Evaluate JavaScript in this execution context."""
        return self._owner.evaluate(
            script,
            context=self,
            await_promise=await_promise,
            return_by_value=return_by_value,
        )


@dataclass(frozen=True, slots=True)
class Frame:
    """Synchronous CDP frame handle."""

    id: str
    name: str
    url: str
    session_id: str
    _owner: Any = field(repr=False, compare=False)
    _generation: int = field(repr=False, compare=False)

    def contexts(
        self,
        *,
        extension_id: str | None = None,
        predicate: ContextPredicate | None = None,
    ) -> list[ExecutionContext]:
        """Return execution contexts for this frame."""
        return self._owner.contexts(frame=self, extension_id=extension_id, predicate=predicate)

    def context(
        self,
        *,
        extension_id: str | None = None,
        predicate: ContextPredicate | None = None,
    ) -> ExecutionContext:
        """Return one execution context for this frame."""
        return self._owner.context(frame=self, extension_id=extension_id, predicate=predicate)

    def evaluate(
        self,
        script: str,
        *,
        extension_id: str | None = None,
        await_promise: bool = True,
        return_by_value: bool = True,
    ) -> Any:
        """Evaluate JavaScript in this frame."""
        return self._owner.evaluate(
            script,
            frame=self,
            extension_id=extension_id,
            await_promise=await_promise,
            return_by_value=return_by_value,
        )


@dataclass(frozen=True, slots=True)
class AsyncExecutionContext:
    """Async JavaScript execution context."""

    id: int
    unique_id: str | None
    frame_id: str | None
    origin: str
    name: str
    type: str
    is_default: bool
    _owner: Any = field(repr=False, compare=False)
    _session_id: str = field(repr=False, compare=False)
    _generation: int = field(repr=False, compare=False)

    async def evaluate(
        self,
        script: str,
        *,
        await_promise: bool = True,
        return_by_value: bool = True,
    ) -> Any:
        """Evaluate JavaScript in this execution context."""
        return await self._owner.evaluate(
            script,
            context=self,
            await_promise=await_promise,
            return_by_value=return_by_value,
        )


@dataclass(frozen=True, slots=True)
class AsyncFrame:
    """Async CDP frame handle."""

    id: str
    name: str
    url: str
    session_id: str
    _owner: Any = field(repr=False, compare=False)
    _generation: int = field(repr=False, compare=False)

    async def contexts(
        self,
        *,
        extension_id: str | None = None,
        predicate: AsyncContextPredicate | None = None,
    ) -> list[AsyncExecutionContext]:
        """Return execution contexts for this frame."""
        return await self._owner.contexts(
            frame=self,
            extension_id=extension_id,
            predicate=predicate,
        )

    async def context(
        self,
        *,
        extension_id: str | None = None,
        predicate: AsyncContextPredicate | None = None,
    ) -> AsyncExecutionContext:
        """Return one execution context for this frame."""
        return await self._owner.context(
            frame=self,
            extension_id=extension_id,
            predicate=predicate,
        )

    async def evaluate(
        self,
        script: str,
        *,
        extension_id: str | None = None,
        await_promise: bool = True,
        return_by_value: bool = True,
    ) -> Any:
        """Evaluate JavaScript in this frame."""
        return await self._owner.evaluate(
            script,
            frame=self,
            extension_id=extension_id,
            await_promise=await_promise,
            return_by_value=return_by_value,
        )
