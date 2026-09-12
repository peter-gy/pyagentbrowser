"""Keep named browser controllers alive across code-mode calls."""

from __future__ import annotations

from dataclasses import replace
from threading import RLock

from agentbrowser._agent.help import help as help
from agentbrowser._agent.resources import agent_plugin as agent_plugin
from agentbrowser._agent.resources import agent_skill as agent_skill
from agentbrowser.browser import Browser
from agentbrowser.features.session.models import CloseResult, SessionStatus
from agentbrowser.launch import SessionOptions, normalize_session

_DEFAULT_CONNECTION = "default"
_CONNECTIONS: dict[str, Browser] = {}
_CONNECTIONS_LOCK = RLock()
__all__ = [
    "CloseAllError",
    "agent_plugin",
    "agent_skill",
    "close",
    "close_all",
    "create",
    "get",
    "help",
    "names",
    "status",
]


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
        _CONNECTIONS[connection_name] = browser
    return browser


def get(name: str = _DEFAULT_CONNECTION) -> Browser:
    """Return one registered open browser controller."""
    connection_name = _connection_name(name)
    with _CONNECTIONS_LOCK:
        connection = _CONNECTIONS.get(connection_name)
    if connection is None:
        raise KeyError(f"browser controller {connection_name!r} is not registered")
    if connection.closed:
        raise RuntimeError(f"browser controller {connection_name!r} is closed")
    return connection


def names() -> tuple[str, ...]:
    """Return registered controller names in lexical order."""
    with _CONNECTIONS_LOCK:
        return tuple(sorted(_CONNECTIONS))


def close(name: str = _DEFAULT_CONNECTION) -> CloseResult:
    """Close and forget one registered browser controller."""
    connection_name = _connection_name(name)
    with _CONNECTIONS_LOCK:
        connection = _CONNECTIONS.pop(connection_name, None)
    if connection is None:
        raise KeyError(f"browser controller {connection_name!r} is not registered")
    return connection.close()


def close_all() -> dict[str, CloseResult]:
    """Close and forget every registered browser controller."""
    with _CONNECTIONS_LOCK:
        connections = sorted(_CONNECTIONS.items())
        _CONNECTIONS.clear()
    results: dict[str, CloseResult] = {}
    errors: dict[str, BaseException] = {}
    for name, connection in connections:
        try:
            results[name] = connection.close()
        except BaseException as error:
            errors[name] = error
    if errors:
        raise CloseAllError(results, errors)
    return results


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


def status(name: str = _DEFAULT_CONNECTION) -> SessionStatus:
    """Return native session identity and lifecycle for a registered controller."""
    return get(name).session.status()
