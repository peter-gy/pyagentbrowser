from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Generic, Protocol, TypeVar, cast

from agentbrowser.contracts.errors import BrowserError, ConfirmationRequired, FrameLookupError
from agentbrowser.contracts.scope import DocumentScope

T = TypeVar("T")
Data = Mapping[str, Any]


def identity(data: Data) -> Data:
    return data


@dataclass(frozen=True, slots=True)
class Command(Generic[T]):
    """One checked native action with its parameters and result decoder."""

    action: str
    params: Mapping[str, object] = field(default_factory=dict)
    decode: Callable[[Data], T] = field(default_factory=lambda: cast(Callable[[Data], T], identity))


class Executor(Protocol):
    """Checked command execution available to a synchronous capability."""

    @property
    def scope(self) -> DocumentScope: ...

    @property
    def generation(self) -> int: ...

    def execute(self, command: Command[T]) -> T: ...

    def bind(self, scope: DocumentScope, *, ref_generation: int | None = None) -> Executor: ...


class AsyncExecutor(Protocol):
    """Checked command execution available to an asynchronous capability."""

    @property
    def scope(self) -> DocumentScope: ...

    @property
    def generation(self) -> int: ...

    async def execute(self, command: Command[T]) -> T: ...

    def bind(self, scope: DocumentScope, *, ref_generation: int | None = None) -> AsyncExecutor: ...


class Controller(Protocol):
    _active_target_id: str | None
    _ref_generation: int

    def _command(self, action: str, *, _decode: Callable[[Data], T], **params: Any) -> T: ...


class AsyncController(Protocol):
    _active_target_id: str | None
    _ref_generation: int

    async def _command(self, action: str, *, _decode: Callable[[Data], T], **params: Any) -> T: ...


def _parameters(
    command: Command[Any], scope: DocumentScope | None, generation: int | None
) -> dict[str, object]:
    params = dict(command.params)
    if scope is not None:
        if scope.target_id is not None:
            params["_targetId"] = scope.target_id
        params["_frameId"] = scope.frame_id or ""
    if generation is not None:
        params["_refGeneration"] = generation
    return params


def _scope_error(error: BaseException, scope: DocumentScope | None) -> BaseException:
    if not isinstance(error, BrowserError) or scope is None or scope.frame_id is None:
        return error
    if error.code in {"frame_scope", "tab_gone"}:
        return FrameLookupError("scope_mismatch", scope.frame_id)
    if error.code == "frame_detached":
        return FrameLookupError("detached", scope.frame_id)
    return error


def result_scope(executor: Executor | AsyncExecutor, data: Data) -> DocumentScope:
    scope = executor.scope
    target_id = data.get("targetId")
    origin = data.get("origin")
    generation = data.get("refGeneration", executor.generation)
    return DocumentScope(
        target_id if isinstance(target_id, str) else scope.target_id,
        scope.frame_id,
        origin if isinstance(origin, str) else scope.url,
        generation,
    )


@dataclass(slots=True)
class BoundExecutor:
    """Retain a controller and apply document identity to each checked command."""

    _controller: Controller
    _scope: DocumentScope | None = None
    _ref_generation: int | None = None

    @property
    def scope(self) -> DocumentScope:
        return self._scope or DocumentScope(self._controller._active_target_id, None)

    @property
    def generation(self) -> int:
        return self._controller._ref_generation

    def bind(self, scope: DocumentScope, *, ref_generation: int | None = None) -> BoundExecutor:
        return BoundExecutor(
            self._controller,
            scope,
            self._ref_generation if ref_generation is None else ref_generation,
        )

    def execute(self, command: Command[T]) -> T:
        def decode(data: Data) -> T:
            self._bind_target()
            return command.decode(data)

        try:
            return self._controller._command(
                command.action,
                _decode=decode,
                **_parameters(command, self._scope, self._ref_generation),
            )
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map_error(self._map_error)
            raise
        except BrowserError as error:
            mapped = self._map_error(error)
            if mapped is error:
                raise
            raise mapped from error

    def _map_error(self, error: BaseException) -> BaseException:
        scope = self._scope
        if isinstance(error, BrowserError) and not isinstance(error, ConfirmationRequired):
            target_id = error.response.get("targetId")
            if scope is not None and scope.target_id is None and isinstance(target_id, str):
                self._scope = DocumentScope(target_id, scope.frame_id, scope.url, scope.generation)
        return _scope_error(error, self._scope)

    def _bind_target(self) -> None:
        scope = self._scope
        if scope is not None and scope.target_id is None:
            self._scope = DocumentScope(
                self._controller._active_target_id, scope.frame_id, scope.url, scope.generation
            )


@dataclass(slots=True)
class AsyncBoundExecutor:
    """Retain an async controller and apply document identity to checked commands."""

    _controller: AsyncController
    _scope: DocumentScope | None = None
    _ref_generation: int | None = None

    @property
    def scope(self) -> DocumentScope:
        return self._scope or DocumentScope(self._controller._active_target_id, None)

    @property
    def generation(self) -> int:
        return self._controller._ref_generation

    def bind(
        self, scope: DocumentScope, *, ref_generation: int | None = None
    ) -> AsyncBoundExecutor:
        return AsyncBoundExecutor(
            self._controller,
            scope,
            self._ref_generation if ref_generation is None else ref_generation,
        )

    async def execute(self, command: Command[T]) -> T:
        def decode(data: Data) -> T:
            self._bind_target()
            return command.decode(data)

        try:
            return await self._controller._command(
                command.action,
                _decode=decode,
                **_parameters(command, self._scope, self._ref_generation),
            )
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map_error(self._map_error)
            raise
        except BrowserError as error:
            mapped = self._map_error(error)
            if mapped is error:
                raise
            raise mapped from error

    def _map_error(self, error: BaseException) -> BaseException:
        scope = self._scope
        if isinstance(error, BrowserError) and not isinstance(error, ConfirmationRequired):
            target_id = error.response.get("targetId")
            if scope is not None and scope.target_id is None and isinstance(target_id, str):
                self._scope = DocumentScope(target_id, scope.frame_id, scope.url, scope.generation)
        return _scope_error(error, self._scope)

    def _bind_target(self) -> None:
        scope = self._scope
        if scope is not None and scope.target_id is None:
            self._scope = DocumentScope(
                self._controller._active_target_id, scope.frame_id, scope.url, scope.generation
            )
