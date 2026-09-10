"""On-demand API and installed-resource guidance for code-mode agents."""

from __future__ import annotations

from textwrap import indent

import agent_plugins

from agentbrowser._agent.resources import agent_plugin, agent_skill


def _sdk_help(summary: str) -> str:
    return f"""{summary}

Create one browser controller for a code-mode task:

    import agentbrowser.agent as browser_agent

    browser = browser_agent.create("research")
    browser.page.open("https://example.com")

Retrieve it in a later call with `browser_agent.get("research")`. Inspect
native session identity and lifecycle with
`browser_agent.status("research")`. End the task with
`browser_agent.close("research")`.

Open a supplied application URL with `browser.page.open(url)`. For an existing
browser connection, use `Browser.attach(CDPTarget(...))` and select its page
with `browser.tabs.switch(id=...)`.

Task map:

    inspect page          browser.page.observe()
    inspect frames        browser.page.frames.tree()
    target a frame        browser.page.frames.get(...)
    find an element       page.find.role(...)
    resize viewport       browser.emulation.viewport(...)
    emulate media         browser.emulation.media(...)
    measure layout        page.geometry(...)
    measure scrolling     page.scroll.by(...)
    capture screenshot    page.capture.screenshot(...)
    image bytes           shot.content()

Published documentation:

    https://peter-gy.github.io/pyagentbrowser/llms.txt
"""


def help() -> str:
    """Return the SDK task map and paths to installed skill resources."""
    sdk = _sdk_help("Keep browser controllers alive across code-mode calls.")
    try:
        plugin = agent_plugin()
        skill = agent_skill()
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
