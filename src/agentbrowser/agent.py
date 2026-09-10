"""Keep browser controllers alive across code-mode calls."""

from __future__ import annotations

import sys
from dataclasses import dataclass, replace
from textwrap import indent
from threading import RLock
from types import ModuleType
from typing import TYPE_CHECKING

import agent_plugins

from agentbrowser import _evidence
from agentbrowser.browser import Browser
from agentbrowser.host import AttachedTarget, OpenTarget
from agentbrowser.launch import LaunchOptions, SessionOptions, normalize_session
from agentbrowser.models import CloseResult

if TYPE_CHECKING:
    from agentbrowser._evidence import Ref as Ref
    from agentbrowser._evidence import Snapshot as Snapshot
    from agentbrowser._evidence import StaleRefError as StaleRefError

_DISTRIBUTION_NAME = "pyagentbrowser"
_SKILL_NAME = "pyagentbrowser"
_DEFAULT_CONNECTION = "default"

__all__ = [
    "Ref",
    "Snapshot",
    "StaleRefError",
    "agent_plugin",
    "agent_skill",
    "attach",
    "close",
    "close_all",
    "create",
    "get",
    "names",
    "open",
]


@dataclass(frozen=True, slots=True)
class _Connection:
    browser: Browser
    session: SessionOptions
    ownership: str


_CONNECTIONS: dict[str, _Connection] = {}
_CONNECTIONS_LOCK = RLock()


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
    if not isinstance(target, OpenTarget):
        raise TypeError("target must be OpenTarget")
    browser = create(name, session=session)
    try:
        browser.open(target.url)
    except BaseException:
        close(name)
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
    browser = Browser.attach(target.connection, launch=launch, session=options)
    try:
        browser.tabs.switch(id=target.page_id)
        browser.page = browser.tabs.get(id=target.page_id)
        browser.find = browser.page.find
        browser.capture = browser.page.capture
    except BaseException:
        browser.close()
        raise
    with _CONNECTIONS_LOCK:
        if connection_name in _CONNECTIONS:
            browser.close()
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
    return {name: connection.browser.close() for name, connection in connections}


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


def agent_plugin() -> agent_plugins.Plugin:
    """Return the Agent Plugin installed with this pyagentbrowser version."""
    return agent_plugins.locate(_DISTRIBUTION_NAME)


def agent_skill() -> agent_plugins.Skill:
    """Return the packaged pyagentbrowser Agent Skill."""
    return agent_plugin().skill(_SKILL_NAME)


def _sdk_help(summary: str) -> str:
    return f"""{summary}

Create one browser controller for a code-mode task:

    import agentbrowser.agent as browser_agent

    browser = browser_agent.create("research")
    browser.open("https://example.com")

Retrieve it in a later call with `browser_agent.get("research")`. Inspect
registered names with `browser_agent.names()`. End the task with
`browser_agent.close("research")`.

Use `browser_agent.open(name, OpenTarget(url))` when a host provides an
application URL. Use `browser_agent.attach(name, AttachedTarget(...))` when a
host provides an authorized browser connection and exact page identity.

Task map:

    inspect page          browser.observe()
    find an element       browser.find.role(...)
    resize viewport       browser.emulation.viewport(...)
    emulate media         browser.emulation.media(...)
    capture screenshot    browser.capture.screenshot(...)
    inspect frames        browser.page.frames.tree()

Published documentation:

    https://peter-gy.github.io/pyagentbrowser/llms.txt
"""


def _module_help(summary: str) -> str:
    sdk = _sdk_help(summary)
    try:
        plugin = agent_plugin()
        skill = plugin.skill(_SKILL_NAME)
        tree = indent(plugin.tree(max_depth=4, max_files=50), "    ")
    except agent_plugins.AgentPluginError as error:
        return f"""{sdk}

The installed Agent Plugin could not be resolved: {error}
Reinstall pyagentbrowser to restore its version-matched skill resources.
"""

    return f"""{sdk}

Installed Agent Plugin resources:

{tree}

Skill instructions:

    {skill.file("SKILL.md")}
"""


class _AgentModule(ModuleType):
    def __getattr__(self, name: str) -> object:
        try:
            return {
                "Ref": _evidence.Ref,
                "Snapshot": _evidence.Snapshot,
                "StaleRefError": _evidence.StaleRefError,
            }[name]
        except KeyError:
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None

    @property
    def __doc__(self) -> str | None:
        summary = self.__dict__.get("__doc__")
        return _module_help(summary) if isinstance(summary, str) else None

    @__doc__.setter
    def __doc__(self, value: str | None) -> None:
        self.__dict__["__doc__"] = value

    def __dir__(self) -> list[str]:
        return sorted(
            {
                "__doc__",
                "__name__",
                "__package__",
                "__spec__",
                "agent_plugin",
                "agent_skill",
                "attach",
                "close",
                "close_all",
                "create",
                "get",
                "names",
                "open",
            }
        )


sys.modules[__name__].__class__ = _AgentModule
