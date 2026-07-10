from __future__ import annotations

import asyncio
import weakref
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass, replace
from pathlib import Path
from queue import Queue
from threading import Event, Lock, Thread
from typing import Any

from agentbrowser._browser_common import (
    INTERNAL_SHUTDOWN_ACTION,
    action_closes_browser,
    response_data_mapping,
)
from agentbrowser.models import BrowserResponse, DashboardOptions, JSONValue, RestoreOptions
from agentbrowser.session import (
    DEFAULT_TIMEOUT_MS,
    NativeEngine,
    NativeSession,
    _checked_response,
    _try_unwrap_confirmed_response,
)


@dataclass(frozen=True, slots=True)
class _AsyncCommand:
    action: str
    params: dict[str, Any]
    loop: asyncio.AbstractEventLoop
    future: asyncio.Future[BrowserResponse]
    cancelled: Event
    started: Event


@dataclass(frozen=True, slots=True)
class _AsyncNativeConfig:
    session: str | None
    restore: RestoreOptions | None
    namespace: str | None
    default_timeout_ms: int | None
    allowed_domains: str | None
    engine: str | None
    action_policy: str | Path | None
    confirm_actions: tuple[str, ...] | None
    no_auto_dialog: bool
    dashboard: bool | DashboardOptions | None
    native: NativeEngine | None


_STOP = object()


class AsyncNativeSession:
    """Async native session with one owner thread for Rust browser state."""

    def __init__(
        self,
        *,
        session: str | None = None,
        restore: RestoreOptions | None = None,
        namespace: str | None = None,
        default_timeout_ms: int | None = DEFAULT_TIMEOUT_MS,
        allowed_domains: str | None = None,
        engine: str | None = None,
        action_policy: str | Path | None = None,
        confirm_actions: Sequence[str] | None = None,
        no_auto_dialog: bool = False,
        dashboard: bool | DashboardOptions | None = False,
        native: NativeEngine | None = None,
    ) -> None:
        self._queue: Queue[_AsyncCommand | object] = Queue()
        self._ready = Event()
        self._thread: Thread | None = None
        self._config = _AsyncNativeConfig(
            session=session,
            restore=restore,
            namespace=namespace,
            default_timeout_ms=default_timeout_ms,
            allowed_domains=allowed_domains,
            engine=engine,
            action_policy=action_policy,
            confirm_actions=tuple(confirm_actions) if confirm_actions is not None else None,
            no_auto_dialog=no_auto_dialog,
            dashboard=dashboard,
            native=native,
        )
        self._startup_error: list[BaseException] = []
        self._closed = False
        self._pending_lock = Lock()
        self._pending_commands: list[_AsyncCommand] = []
        self._finalizer = weakref.finalize(self, _stop_async_worker, self._queue)

    @property
    def closed(self) -> bool:
        """Whether close has been requested for this async native session."""
        return self._closed

    def set_allowed_domains(self, allowed_domains: str | None) -> None:
        """Replace the Python-side domain allowlist before the worker starts."""
        if self._thread is not None:
            raise RuntimeError("cannot change allowed_domains after AsyncNativeSession starts")
        self._config = replace(self._config, allowed_domains=allowed_domains)

    async def command(self, action: str, **params: Any) -> JSONValue:
        """Run a native command and return checked response data."""
        response = await self.execute(action, **params)
        return _checked_response(action, response).data

    async def execute(self, action: str, **params: Any) -> BrowserResponse:
        """Run a native command and return the full response envelope."""
        await self._ensure_started()
        loop = asyncio.get_running_loop()
        future: asyncio.Future[BrowserResponse] = loop.create_future()
        cancelled = Event()
        command = _AsyncCommand(action, params, loop, future, cancelled, Event())
        future.add_done_callback(lambda done: self._finish_command(command, done))
        with self._pending_lock:
            if self._closed:
                raise RuntimeError("AsyncNativeSession is closed")
            self._pending_commands.append(command)
        self._queue.put(command)
        return await future

    async def shutdown_native(self) -> BrowserResponse | None:
        """Close native browser state without allowing queued user work to run."""
        self._begin_close()
        thread = self._thread
        if thread is None:
            return None
        loop = asyncio.get_running_loop()
        future: asyncio.Future[BrowserResponse] = loop.create_future()
        command = _AsyncCommand(
            INTERNAL_SHUTDOWN_ACTION,
            {},
            loop,
            future,
            Event(),
            Event(),
        )
        self._queue.put(command)
        return await future

    async def aclose(self, *, timeout: float = 5.0) -> None:
        """Stop the owner thread and close native browser state."""
        self._begin_close()
        thread = self._thread
        if thread is None:
            self._finalizer.detach()
            return
        self._queue.put(_STOP)
        await asyncio.shield(asyncio.to_thread(thread.join, timeout))
        if thread.is_alive():
            raise RuntimeError("AsyncNativeSession worker did not stop before timeout")
        self._thread = None
        self._finalizer.detach()

    async def _ensure_started(self) -> None:
        if self._closed:
            raise RuntimeError("AsyncNativeSession is closed")

        if self._thread is None:
            self._thread = Thread(
                target=_run_async_native_session,
                args=(self._config, self._queue, self._ready, self._startup_error),
                name="pyagentbrowser-async-session",
                daemon=True,
            )
            self._thread.start()

        await asyncio.to_thread(self._ready.wait)
        if self._startup_error:
            raise RuntimeError("failed to start async native session") from self._startup_error[0]

    def _begin_close(self) -> None:
        self._closed = True
        self._cancel_pending_commands()

    def _finish_command(
        self,
        command: _AsyncCommand,
        future: asyncio.Future[BrowserResponse],
    ) -> None:
        if future.cancelled():
            command.cancelled.set()
        with self._pending_lock, suppress(ValueError):
            self._pending_commands.remove(command)

    def _cancel_pending_commands(self) -> None:
        with self._pending_lock:
            pending = list(self._pending_commands)
        for command in pending:
            if command.started.is_set():
                continue
            command.cancelled.set()
            _call_soon(
                command.loop,
                _set_future_exception,
                command.future,
                RuntimeError("AsyncNativeSession is closed"),
            )


def _run_async_native_session(
    config: _AsyncNativeConfig,
    queue: Queue[_AsyncCommand | object],
    ready: Event,
    startup_error: list[BaseException],
) -> None:
    try:
        session = NativeSession(
            session=config.session,
            restore=config.restore,
            namespace=config.namespace,
            default_timeout_ms=config.default_timeout_ms,
            allowed_domains=config.allowed_domains,
            engine=config.engine,
            action_policy=config.action_policy,
            confirm_actions=config.confirm_actions,
            no_auto_dialog=config.no_auto_dialog,
            dashboard=config.dashboard,
            native=config.native,
        )
    except BaseException as err:  # pragma: no cover - startup failure path
        startup_error.append(err)
        ready.set()
        return

    ready.set()
    native_closed = False

    while True:
        item = queue.get()
        if item is _STOP:
            if not native_closed:
                with suppress(BaseException):
                    session.execute(INTERNAL_SHUTDOWN_ACTION)
            session.discard_pending_confirmations()
            return
        command = item
        if not isinstance(command, _AsyncCommand):
            continue
        if command.cancelled.is_set():
            continue

        try:
            command.started.set()
            response = session.execute(command.action, **command.params)
        except BaseException as err:
            _call_soon(command.loop, _set_future_exception, command.future, err)
            if command.action == INTERNAL_SHUTDOWN_ACTION:
                session.discard_pending_confirmations()
                return
        else:
            action = command.action
            data = response_data_mapping(response)
            is_confirmation = data is not None and bool(data.get("confirmation_required"))
            if command.action == "confirm" and response.success:
                action = _try_unwrap_confirmed_response(response).action
            if action_closes_browser(action) and response.success and not is_confirmation:
                native_closed = True
            _call_soon(command.loop, _set_future_result, command.future, response)
            if command.action == INTERNAL_SHUTDOWN_ACTION:
                session.discard_pending_confirmations()
                return


def _call_soon(
    loop: asyncio.AbstractEventLoop,
    callback: Any,
    future: asyncio.Future[BrowserResponse],
    value: Any,
) -> None:
    with suppress(RuntimeError):
        loop.call_soon_threadsafe(callback, future, value)


def _set_future_result(
    future: asyncio.Future[BrowserResponse],
    value: BrowserResponse,
) -> None:
    if not future.cancelled():
        future.set_result(value)


def _set_future_exception(
    future: asyncio.Future[BrowserResponse],
    err: BaseException,
) -> None:
    if not future.cancelled():
        future.set_exception(err)


def _cancel_future(
    future: asyncio.Future[BrowserResponse],
    _value: object,
) -> None:
    future.cancel()


def _stop_async_worker(queue: Queue[_AsyncCommand | object]) -> None:
    queue.put(_STOP)
