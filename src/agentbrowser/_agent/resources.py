"""Resolve the plugin resources installed with this package."""

from __future__ import annotations

import agent_plugins

_DISTRIBUTION_NAME = "pyagentbrowser"
_SKILL_NAME = "pyagentbrowser"


def agent_plugin() -> agent_plugins.Plugin:
    """Return the Agent Plugin installed with this pyagentbrowser version."""
    return agent_plugins.locate(_DISTRIBUTION_NAME)


def agent_skill() -> agent_plugins.Skill:
    """Return the packaged pyagentbrowser Agent Skill."""
    return agent_plugin().skill(_SKILL_NAME)
