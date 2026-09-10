"""Observable asyncio tasks that retain results across code executions."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextvars import Context
from dataclasses import dataclass, field
from typing import Generic, TypeVar, cast
from uuid import uuid4

from agentbrowser.host import (
    BrowserTarget,
    CallbackHost,
    ExecutionContext,
    ManagedTaskStatus,
    bind_host,
    reset_host,
)

T = TypeVar("T", covariant=True)


class Task(Generic[T]):
    """Retained result and observable lifecycle for one asynchronous operation.

    Await ``result()`` to retrieve the operation's value or exception. A result
    timeout leaves the operation running. Await ``cancel()`` to request
    cancellation and wait for the operation's cleanup to finish.
    """

    def __init__(self, name: str, task_id: str, pending: asyncio.Task[T]) -> None:
        self.name = name
        self.id = task_id
        self._pending = pending
        self._progress: float | None = None
        self._detail: str | None = None
        pending.add_done_callback(self._settled)

    @staticmethod
    def _settled(pending: asyncio.Task[T]) -> None:
        if not pending.cancelled():
            pending.exception()

    def status(self) -> ManagedTaskStatus:
        """Return running, completed, failed, or cancelled state."""
        if self._pending.cancelled():
            return ManagedTaskStatus(self.id, "cancelled", self._progress, self._detail)
        if not self._pending.done():
            return ManagedTaskStatus(self.id, "running", self._progress, self._detail)
        error = self._pending.exception()
        if error is not None:
            return ManagedTaskStatus(
                self.id, "failed", self._progress, f"{type(error).__name__}: {error}"
            )
        return ManagedTaskStatus(self.id, "completed", self._progress, self._detail)

    def report(self, progress: float | None = None, detail: str | None = None) -> ManagedTaskStatus:
        """Update progress between zero and one or detail while running.

        Omitted values retain their previous values. Raises ``RuntimeError``
        after the task settles.
        """
        self._check_loop()
        if self._pending.done():
            raise RuntimeError("task has settled, progress is final")
        if progress is not None and not 0 <= progress <= 1:
            raise ValueError("progress must be between zero and one")
        if detail is not None and not isinstance(detail, str):
            raise TypeError("detail must be a string")
        if progress is not None:
            self._progress = progress
        if detail is not None:
            self._detail = detail
        return self.status()

    async def result(self, *, timeout_ms: int | None = None) -> T:
        """Wait for the retained result, raising the operation's exception."""
        self._check_loop()
        if timeout_ms is not None and timeout_ms < 0:
            raise ValueError("timeout_ms must be non-negative")
        return await asyncio.wait_for(
            asyncio.shield(self._pending),
            timeout=None if timeout_ms is None else timeout_ms / 1_000,
        )

    async def cancel(self) -> ManagedTaskStatus:
        """Request cancellation and return the state after cleanup settles.

        An operation that catches cancellation may complete or fail. Its final
        state and result remain observable.
        """
        self._check_loop()
        if self._pending is asyncio.current_task():
            raise RuntimeError("a task cannot wait for its own cancellation")
        self._pending.cancel()
        await asyncio.gather(self._pending, return_exceptions=True)
        return self.status()

    def _check_loop(self) -> None:
        if self._pending.get_loop() is not asyncio.get_running_loop():
            raise RuntimeError("Task must be awaited on the event loop that started it")


class Tasks:
    """Own asynchronous operations on one persistent event loop.

    Each operation receives a fresh context, a captured browser target, and its
    own execution budget. Return text and screenshot objects from tasks and
    emit their content during a code execution. Call ``close()`` before shutting
    down the event loop to settle task cleanup.
    """

    def __init__(self, target: BrowserTarget | Callable[[], BrowserTarget]) -> None:
        self.target = target
        self._tasks: dict[str, Task[object]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._closed = False

    def start(
        self,
        name: str,
        operation: Callable[[], Awaitable[T]],
        *,
        timeout_ms: int | None = None,
    ) -> Task[T]:
        """Start a named operation with an optional independent timeout.

        The timeout cancels awaited work cooperatively. Python operations that
        block the event loop require interruption by the calling host.
        """
        if self._closed:
            raise RuntimeError("Tasks is closed")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("task name must be a non-empty string")
        if not callable(operation):
            raise TypeError("operation must be a callable returning an awaitable")
        context = ExecutionContext(timeout_ms=timeout_ms, cancellation=True, managed_tasks=True)
        loop = asyncio.get_running_loop()
        if self._loop is not None and self._loop is not loop:
            raise RuntimeError("Tasks must run on the event loop that started its first task")
        self._loop = loop
        target = (
            cast(Callable[[], BrowserTarget], self.target)()
            if callable(self.target)
            else self.target
        )

        async def run() -> T:
            token = bind_host(_ManagedHost(target, None, context, tasks=self))
            try:
                async with asyncio.timeout(None if timeout_ms is None else timeout_ms / 1_000):
                    return await operation()
            finally:
                reset_host(token)

        task_id = uuid4().hex
        task = Task(name, task_id, loop.create_task(run(), name=name, context=Context()))
        self._tasks[task_id] = task
        return task

    def get(self, task_id: str) -> Task[object]:
        """Return a retained handle, raising KeyError for an unknown task ID."""
        return self._tasks[task_id]

    def list(self) -> tuple[Task[object], ...]:
        """Return retained task handles in creation order."""
        return tuple(self._tasks.values())

    async def close(self) -> None:
        """Cancel running tasks, await cleanup, and close the registry."""
        if self._loop is not None and self._loop is not asyncio.get_running_loop():
            raise RuntimeError("Tasks must close on the event loop that started its first task")
        if any(task._pending is asyncio.current_task() for task in self._tasks.values()):
            raise RuntimeError("a managed task cannot close its own Tasks registry")
        self._closed = True
        await asyncio.gather(*(task.cancel() for task in self._tasks.values()))


@dataclass(frozen=True)
class _ManagedHost(CallbackHost):
    tasks: Tasks = field(kw_only=True)

    def start_task(
        self,
        name: str,
        operation: Callable[[], Awaitable[T]],
        *,
        timeout_ms: int | None = None,
    ) -> Task[T]:
        return self.tasks.start(name, operation, timeout_ms=timeout_ms)
