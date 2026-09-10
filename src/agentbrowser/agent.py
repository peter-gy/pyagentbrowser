"""Keep browser controllers alive across code-mode calls."""

from __future__ import annotations

import os
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, replace
from threading import RLock
from typing import Any, Generic, Literal, TypeVar, cast

from agentbrowser.browser import Browser
from agentbrowser.contracts.errors import ConfirmationRequired
from agentbrowser.features.session.models import CloseResult
from agentbrowser.integrations.help import help as help
from agentbrowser.integrations.host import AgentConnectionStatus, AttachedTarget, OpenTarget
from agentbrowser.integrations.resources import agent_plugin as agent_plugin
from agentbrowser.integrations.resources import agent_skill as agent_skill
from agentbrowser.launch import LaunchOptions, SessionOptions, normalize_session

_DEFAULT_CONNECTION = "default"
T = TypeVar("T")
U = TypeVar("U")

__all__ = [
    "CloseAllError",
    "agent_plugin",
    "agent_skill",
    "attach",
    "close",
    "close_all",
    "create",
    "get",
    "help",
    "names",
    "open",
    "status",
]


@dataclass(frozen=True, slots=True)
class _Connection:
    browser: Browser
    session: SessionOptions
    ownership: Literal["owned", "attached"]


_CONNECTIONS: dict[str, _Connection] = {}
_CONNECTIONS_LOCK = RLock()


class CloseAllError(RuntimeError):
    """Raised after every registered controller received a close attempt."""

    def __init__(
        self,
        results: dict[str, CloseResult],
        errors: dict[str, BaseException],
    ) -> None:
        self.results = results
        self.errors = errors
        names = ", ".join(sorted(errors))
        super().__init__(f"failed to close browser controllers: {names}")


@dataclass(frozen=True, slots=True)
class _LifecyclePendingAction(Generic[T]):
    """Confirmation continuation with lifecycle cleanup on denial or failure."""

    _pending: Any
    _complete: Callable[[Any], T]
    _cleanup: Callable[[], None]

    @property
    def confirmation_id(self) -> str:
        return cast(str, self._pending.confirmation_id)

    @property
    def action(self) -> str:
        return cast(str, self._pending.action)

    @property
    def details(self) -> Any:
        return self._pending.details

    def confirm(self) -> T:
        try:
            value = self._pending.confirm()
        except ConfirmationRequired as error:
            if error.pending is not None and not isinstance(error.pending, _LifecyclePendingAction):
                error.pending = _LifecyclePendingAction(
                    error.pending,
                    self._complete,
                    self._cleanup,
                )
            raise
        except BaseException:
            self._cleanup()
            raise
        try:
            return self._complete(value)
        except ConfirmationRequired as error:
            if error.pending is not None and not isinstance(error.pending, _LifecyclePendingAction):
                error.pending = _LifecyclePendingAction(
                    error.pending,
                    lambda result: result,
                    self._cleanup,
                )
            raise
        except BaseException:
            self._cleanup()
            raise

    def deny(self) -> None:
        try:
            self._pending.deny()
        finally:
            self._cleanup()

    def map(self, complete: Callable[[T], U]) -> _LifecyclePendingAction[U]:
        previous = self._complete

        def composed(value: Any) -> U:
            try:
                intermediate = previous(value)
            except ConfirmationRequired as error:
                if error.pending is not None:
                    error.pending = error.pending.map(complete)
                raise
            return complete(intermediate)

        return _LifecyclePendingAction(self._pending, composed, self._cleanup)


def create(
    name: str = _DEFAULT_CONNECTION,
    *,
    session: SessionOptions | None = None,
) -> Browser:
    """Create and register one module-owned browser controller."""
    connection_name = _connection_name(name)
    options = _session_options(connection_name, session)
    with _CONNECTIONS_LOCK:
        _require_available(connection_name)
        browser = Browser(session=options)
        _CONNECTIONS[connection_name] = _Connection(browser, options, "owned")
    return browser


def open(
    name: str,
    target: OpenTarget,
    *,
    session: SessionOptions | None = None,
) -> Browser:
    """Create a browser, open an application URL, and register it."""
    connection_name = _connection_name(name)
    if not isinstance(target, OpenTarget):
        raise TypeError("target must be OpenTarget")
    browser = create(connection_name, session=session)
    try:
        browser.page.open(target.url)
    except ConfirmationRequired as error:
        _set_lifecycle_pending(
            error,
            complete=lambda _value: browser,
            cleanup=lambda: _close_registered(connection_name, browser),
        )
        raise
    except BaseException:
        _close_registered(connection_name, browser)
        raise
    return browser


def attach(
    name: str,
    target: AttachedTarget,
    *,
    launch: LaunchOptions | None = None,
    session: SessionOptions | None = None,
) -> Browser:
    """Attach to an exact existing page and register its controller."""
    connection_name = _connection_name(name)
    if not isinstance(target, AttachedTarget):
        raise TypeError("target must be AttachedTarget")
    options = _session_options(connection_name, session)
    with _CONNECTIONS_LOCK:
        _require_available(connection_name)
    try:
        browser = Browser.attach(target.connection, launch=launch, session=options)
    except ConfirmationRequired as error:
        pending_controller = getattr(error.pending, "_controller", None)
        cleanup = (
            (lambda: _close_browser(pending_controller))
            if callable(getattr(pending_controller, "close", None))
            else (lambda: None)
        )
        _set_lifecycle_pending(
            error,
            complete=lambda confirmed: _select_and_register_attached(
                connection_name,
                options,
                target,
                cast(Browser, confirmed),
            ),
            cleanup=cleanup,
        )
        raise
    return _select_and_register_attached(connection_name, options, target, browser)


def _select_and_register_attached(
    connection_name: str,
    options: SessionOptions,
    target: AttachedTarget,
    browser: Browser,
) -> Browser:
    try:
        browser.tabs.switch(id=target.target_id)
    except ConfirmationRequired as error:
        _set_lifecycle_pending(
            error,
            complete=lambda _value: _register_attached(
                connection_name,
                options,
                target.target_id,
                browser,
            ),
            cleanup=lambda: _close_browser(browser),
        )
        raise
    except BaseException:
        _close_browser(browser)
        raise
    return _register_attached(connection_name, options, target.target_id, browser)


def _register_attached(
    connection_name: str,
    options: SessionOptions,
    target_id: str,
    browser: Browser,
) -> Browser:
    browser._page_target_id = target_id
    with _CONNECTIONS_LOCK:
        if connection_name in _CONNECTIONS:
            _close_browser(browser)
            raise ValueError(f"browser controller {connection_name!r} is already registered")
        _CONNECTIONS[connection_name] = _Connection(browser, options, "attached")
    return browser


def get(name: str = _DEFAULT_CONNECTION) -> Browser:
    """Return one registered open browser controller."""
    connection_name = _connection_name(name)
    with _CONNECTIONS_LOCK:
        connection = _CONNECTIONS.get(connection_name)
    if connection is None:
        raise KeyError(f"browser controller {connection_name!r} is not registered")
    if connection.browser.closed:
        raise RuntimeError(f"browser controller {connection_name!r} is closed")
    return connection.browser


def names() -> tuple[str, ...]:
    """Return registered controller names in lexical order."""
    with _CONNECTIONS_LOCK:
        return tuple(sorted(_CONNECTIONS))


def status(name: str = _DEFAULT_CONNECTION) -> AgentConnectionStatus:
    """Return process, session, ownership, and current-page identity."""
    connection_name = _connection_name(name)
    with _CONNECTIONS_LOCK:
        connection = _CONNECTIONS.get(connection_name)
    if connection is None:
        raise KeyError(f"browser controller {connection_name!r} is not registered")
    target_id = None
    url = None
    if connection.browser.is_launched and not connection.browser.closed:
        try:
            tabs = connection.browser.tabs.list()
        except ConfirmationRequired as error:
            _set_lifecycle_pending(
                error,
                complete=lambda confirmed: _status_from_tabs(
                    connection_name,
                    connection,
                    confirmed,
                ),
            )
            raise
        return _status_from_tabs(connection_name, connection, tabs)
    return AgentConnectionStatus(
        name=connection_name,
        process_id=os.getpid(),
        ownership=connection.ownership,
        session_id=connection.session.session_id,
        browser_launched=connection.browser.is_launched,
        browser_closed=connection.browser.closed,
        target_id=target_id,
        url=url,
    )


def _status_from_tabs(
    connection_name: str,
    connection: _Connection,
    tabs: Any,
) -> AgentConnectionStatus:
    active = next((tab for tab in tabs if tab.active), None)
    return AgentConnectionStatus(
        name=connection_name,
        process_id=os.getpid(),
        ownership=connection.ownership,
        session_id=connection.session.session_id,
        browser_launched=connection.browser.is_launched,
        browser_closed=connection.browser.closed,
        target_id=active.target_id if active is not None else None,
        url=active.url if active is not None else None,
    )


def close(name: str = _DEFAULT_CONNECTION) -> CloseResult:
    """Close and forget one registered browser controller."""
    connection_name = _connection_name(name)
    with _CONNECTIONS_LOCK:
        connection = _CONNECTIONS.pop(connection_name, None)
    if connection is None:
        raise KeyError(f"browser controller {connection_name!r} is not registered")
    return connection.browser.close()


def close_all() -> dict[str, CloseResult]:
    """Close and forget every registered browser controller."""
    with _CONNECTIONS_LOCK:
        connections = sorted(_CONNECTIONS.items())
        _CONNECTIONS.clear()
    results: dict[str, CloseResult] = {}
    errors: dict[str, BaseException] = {}
    for name, connection in connections:
        try:
            results[name] = connection.browser.close()
        except BaseException as error:
            errors[name] = error
    if errors:
        raise CloseAllError(results, errors)
    return results


def _set_lifecycle_pending(
    error: ConfirmationRequired[Any],
    *,
    complete: Callable[[Any], T],
    cleanup: Callable[[], None] = lambda: None,
) -> None:
    if error.pending is not None:
        error.pending = _LifecyclePendingAction(error.pending, complete, cleanup)


def _close_registered(name: str, browser: Browser) -> None:
    with _CONNECTIONS_LOCK:
        connection = _CONNECTIONS.get(name)
        if connection is not None and connection.browser is browser:
            _CONNECTIONS.pop(name)
    _close_browser(browser)


def _close_browser(browser: Any) -> None:
    with suppress(BaseException):
        browser.close()


def _session_options(name: str, session: SessionOptions | None) -> SessionOptions:
    options = normalize_session(session)
    return replace(options, session_id=name) if options.session_id is None else options


def _require_available(name: str) -> None:
    if name in _CONNECTIONS:
        raise ValueError(f"browser controller {name!r} is already registered")


def _connection_name(name: str) -> str:
    if not isinstance(name, str):
        raise TypeError("connection name must be a string")
    if not 1 <= len(name) <= 64 or any(
        not char.isalnum() and char not in {"-", "_"} for char in name
    ):
        raise ValueError(
            "connection name must contain 1 to 64 alphanumeric, hyphen, or underscore characters"
        )
    return name
