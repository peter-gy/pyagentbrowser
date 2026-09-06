"""Use pyagentbrowser from notebook and code-mode agents."""

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
from agentbrowser.launch import SessionOptions, normalize_session
from agentbrowser.models import CloseResult

if TYPE_CHECKING:
    from agentbrowser._evidence import Ref as Ref
    from agentbrowser._evidence import Snapshot as Snapshot
    from agentbrowser._evidence import StaleRefError as StaleRefError

_DISTRIBUTION_NAME = "pyagentbrowser"
_SKILL_NAME = "pyagentbrowser"
_DEFAULT_CONNECTION = "default"


@dataclass(frozen=True, slots=True)
class _Connection:
    browser: Browser
    session: SessionOptions


_CONNECTIONS: dict[str, _Connection] = {}
_CONNECTIONS_LOCK = RLock()


def connect(
    name: str = _DEFAULT_CONNECTION,
    *,
    session: SessionOptions | None = None,
) -> Browser:
    """Return a module-owned browser that persists across code-mode calls.

    The first call creates a lazy `Browser`. Later calls with the same name and
    session options return that controller. Call `disconnect()` when the task
    ends.

    Args:
        name: Connection name within the current Python process.
        session: Browser session options. The default uses `name` as the native
            session identifier when `session.session_id` is unset.

    Raises:
        TypeError: `name` is not a string or `session` is not `SessionOptions`.
        ValueError: `name` is not a valid session component or an existing
            connection uses other session options.
    """
    connection_name = _connection_name(name)
    requested = None if session is None else normalize_session(session)
    if requested is not None and requested.session_id is None:
        requested = replace(requested, session_id=connection_name)
    with _CONNECTIONS_LOCK:
        existing = _CONNECTIONS.get(connection_name)
        if existing is not None and not existing.browser.closed:
            if requested is not None and existing.session != requested:
                raise ValueError(
                    f"connection {connection_name!r} already uses other session options"
                )
            return existing.browser

        options = requested or SessionOptions(session_id=connection_name)
        browser = Browser(session=options)
        _CONNECTIONS[connection_name] = _Connection(browser, options)
        return browser


def disconnect(name: str = _DEFAULT_CONNECTION) -> CloseResult:
    """Close and forget one module-owned code-mode browser.

    Closing a missing connection succeeds and returns an already-closed result.
    """
    connection_name = _connection_name(name)
    with _CONNECTIONS_LOCK:
        connection = _CONNECTIONS.pop(connection_name, None)
        return CloseResult(closed=True) if connection is None else connection.browser.close()


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


def _agent_skill(plugin: agent_plugins.Plugin) -> agent_plugins.Skill:
    for skill in plugin.skills:
        if skill.path.name == _SKILL_NAME:
            return skill
    raise agent_plugins.AgentPluginError(
        "The pyagentbrowser Agent Plugin has no pyagentbrowser skill. Reinstall pyagentbrowser."
    )


def agent_skill() -> agent_plugins.Skill:
    """Return the packaged pyagentbrowser Agent Skill."""
    return _agent_skill(agent_plugin())


def _sdk_help(summary: str) -> str:
    return f"""{summary}

Start with a module-owned browser. Its connection survives between marimo
code-mode scratchpad calls:

    import agentbrowser as ab
    import agentbrowser.agent as browser_agent

    browser = browser_agent.connect("research")
    browser.open("https://example.com")
    before = browser.observe()
    print(before.text)

    result = before.one(role="link", name="More information...").click(
        wait=ab.Wait.loaded()
    )
    print(result.after.text)
    print(result.diff)

In a later kernel call, `browser_agent.connect("research")` returns the same
controller. End the task with `browser_agent.disconnect("research")`. Use the
public Browser directly when the complete lifecycle fits in one call. The typed
namespaces and `browser.native.execute()` use the same ordered native action
service as the pinned agent-browser engine.

Browse the published documentation map at:

    https://peter-gy.github.io/pyagentbrowser/llms.txt
"""


def _module_help(summary: str) -> str:
    sdk = _sdk_help(summary)
    try:
        plugin = agent_plugin()
        skill = _agent_skill(plugin)
        tree = indent(plugin.tree(max_depth=3, max_files=50), "    ")
    except agent_plugins.AgentPluginError as error:
        return f"""{sdk}

The installed Agent Plugin could not be resolved: {error}
Reinstall pyagentbrowser to restore its version-matched skill resources.
"""

    return f"""{sdk}

The installed Agent Plugin carries the complete Python browser workflow and
resources that match this package version:

{tree}

Read the pyagentbrowser skill instructions at:

    {skill / "SKILL.md"}

Traverse the same resources programmatically:

    resources = browser_agent.agent_plugin()
    skill = browser_agent.agent_skill()
    print(resources)
    print(skill.body)
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


sys.modules[__name__].__class__ = _AgentModule
