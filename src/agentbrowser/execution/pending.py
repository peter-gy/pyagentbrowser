from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Generic, Literal, TypeVar, cast

from agentbrowser.contracts.errors import ConfirmationRequired
from agentbrowser.contracts.types import JSONMapping

if TYPE_CHECKING:
    from agentbrowser.execution.controller import Controller
    from agentbrowser.execution.controller_async import AsyncController


T = TypeVar("T")
U = TypeVar("U")


@dataclass(frozen=True, slots=True)
class PendingAction(Generic[T]):
    """Native action awaiting explicit confirmation or denial."""

    _controller: Controller
    confirmation_id: str
    action: str
    details: Mapping[str, Any]
    _decode: Callable[[JSONMapping], T] | None = None
    _expect: Literal["object", "any"] = "object"
    _error: Callable[[BaseException], BaseException] | None = None
    _complete: Callable[[Any], T] | None = None

    def _confirm(self) -> T:
        """Confirm this pending action and decode its original return type."""
        try:
            result: Any = self._controller._native_data(
                "confirm",
                expect=self._expect,
                confirmation_id=self.confirmation_id,
            )
        except ConfirmationRequired as error:
            if isinstance(error.pending, PendingAction):
                error.pending = replace(
                    error.pending,
                    _decode=self._decode,
                    _expect=self._expect,
                    _complete=self._complete,
                )
            raise
        if self._decode is not None:
            result = self._decode(cast(JSONMapping, result))
        return self._complete(result) if self._complete is not None else cast(T, result)

    def confirm(self) -> T:
        """Resume this operation and apply its result and error transformations."""
        try:
            return self._confirm()
        except ConfirmationRequired as error:
            if error.pending is not None and self._error is not None:
                error.pending = error.pending.map_error(self._error)
            raise
        except BaseException as error:
            mapped = self._error(error) if self._error is not None else error
            if mapped is error:
                raise
            raise mapped from error

    def map_error(self, transform: Callable[[BaseException], BaseException]) -> PendingAction[T]:
        """Transform operation failures, retaining the transformation across confirmation."""
        previous = self._error
        mapped = transform if previous is None else lambda error: transform(previous(error))
        return replace(self, _error=mapped)

    def deny(self) -> None:
        """Deny this pending action."""
        self._controller._command("deny", confirmation_id=self.confirmation_id)

    def map(self, complete: Callable[[T], U]) -> PendingAction[U]:
        """Complete a higher-level operation after native confirmation."""
        previous = self._complete
        if previous is None:
            composed: Callable[[Any], U] = complete
        else:

            def composed(value: Any) -> U:
                try:
                    intermediate = previous(value)
                except ConfirmationRequired as error:
                    if error.pending is not None:
                        error.pending = error.pending.map(complete)
                    raise
                return complete(intermediate)

        return cast(PendingAction[U], replace(self, _complete=composed))


@dataclass(frozen=True, slots=True)
class AsyncPendingAction(Generic[T]):
    """Native action awaiting explicit async confirmation or denial."""

    _controller: AsyncController
    confirmation_id: str
    action: str
    details: Mapping[str, Any]
    _decode: Callable[[JSONMapping], T] | None = None
    _expect: Literal["object", "any"] = "object"
    _error: Callable[[BaseException], BaseException] | None = None
    _complete: Callable[[Any], Any] | None = None

    async def _confirm(self) -> T:
        """Confirm this pending action and decode its original return type."""
        try:
            result: Any = await self._controller._native_data(
                "confirm",
                expect=self._expect,
                confirmation_id=self.confirmation_id,
            )
        except ConfirmationRequired as error:
            if isinstance(error.pending, AsyncPendingAction):
                error.pending = replace(
                    error.pending,
                    _decode=self._decode,
                    _expect=self._expect,
                    _complete=self._complete,
                )
            raise
        if self._decode is not None:
            result = self._decode(cast(JSONMapping, result))
        if self._complete is None:
            return cast(T, result)
        completed = self._complete(result)
        return cast(T, await completed if inspect.isawaitable(completed) else completed)

    async def confirm(self) -> T:
        """Resume this operation and apply its result and error transformations."""
        try:
            return await self._confirm()
        except ConfirmationRequired as error:
            if error.pending is not None and self._error is not None:
                error.pending = error.pending.map_error(self._error)
            raise
        except BaseException as error:
            mapped = self._error(error) if self._error is not None else error
            if mapped is error:
                raise
            raise mapped from error

    def map_error(
        self, transform: Callable[[BaseException], BaseException]
    ) -> AsyncPendingAction[T]:
        """Transform operation failures, retaining the transformation across confirmation."""
        previous = self._error
        mapped = transform if previous is None else lambda error: transform(previous(error))
        return replace(self, _error=mapped)

    async def deny(self) -> None:
        """Deny this pending action."""
        await self._controller._command("deny", confirmation_id=self.confirmation_id)

    def map(self, complete: Callable[[T], U]) -> AsyncPendingAction[U]:
        """Complete a higher-level operation after native confirmation."""
        previous = self._complete
        if previous is None:
            composed: Callable[[Any], Any] = complete
        else:

            async def composed(value: Any) -> Any:
                try:
                    intermediate = previous(value)
                    if inspect.isawaitable(intermediate):
                        intermediate = await intermediate
                except ConfirmationRequired as error:
                    if error.pending is not None:
                        error.pending = error.pending.map(complete)
                    raise
                completed = complete(intermediate)
                return await completed if inspect.isawaitable(completed) else completed

        return cast(AsyncPendingAction[U], replace(self, _complete=composed))
