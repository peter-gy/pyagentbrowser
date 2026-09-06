---
title: Load agent skills and code-mode guidance
description: Discover pyagentbrowser from marimo code mode and read the instruction files installed with the wheel.
---

# Load agent skills and code-mode guidance

The pyagentbrowser wheel registers an importable marimo code-mode capability and carries an Agent Plugin with Python-specific browser instructions. It also embeds the skills from its pinned `agent-browser` engine for hosts that consume the native engine's instruction set.

## Discover pyagentbrowser in marimo code mode

[Marimo](https://marimo.io/) 0.24.0 or later discovers installed code-mode capabilities through Python package entry points. Install pyagentbrowser in the notebook environment, then inspect the registered module:

```python
import marimo._code_mode as cm

print(cm.capabilities()["pyagentbrowser"])

import agentbrowser.agent as browser_agent

help(browser_agent)
```

`help(browser_agent)` renders a short SDK workflow and the paths to the Agent Plugin resources installed with the same pyagentbrowser version.

Use a named module-owned connection when browser work spans code-mode calls:

```python
browser = browser_agent.connect("research")
browser.open("https://example.com")
page = browser.observe()
print(page.origin)
print(page.text)

# In a later code-mode call
browser = browser_agent.connect("research")

# After the final call
browser_agent.disconnect("research")
```

Use `browser_agent.connections()` to inspect every retained name and controller.
Call `browser_agent.disconnect_all()` after a task that created several named
connections.

Pass `session=agentbrowser.SessionOptions(...)` on the first `connect()` call
when the task needs domain restrictions, confirmation policy, or another
session option. Supplying different options for the same live connection raises
`ValueError` with the `disconnect()` recovery call. If user code closes the
controller directly, the next optionless `connect()` preserves those session
options. `disconnect()` is the explicit boundary for forgetting them.

```python
plugin = browser_agent.agent_plugin()
skill = browser_agent.agent_skill()

print(plugin)
print(skill.file("SKILL.md"))
instructions = skill.body
```

The packaged `pyagentbrowser` skill uses `Browser`, `AsyncBrowser`, typed namespaces, and `browser.native` directly. These Python operations share the embedded native action service with the upstream engine.

## Read the embedded native instruction files

An agent skill is a Markdown instruction set with optional supporting files. The embedded native skills let an application supply version-matched upstream guidance to an agent.

```python
import agentbrowser.skills as skills

print(skills.available())
print(skills.read("core"))
```

The `core` skill teaches the engine's browser interaction workflow. `read(name)` returns its `SKILL.md` content.

### Inspect supporting parts

| Function | Result |
| --- | --- |
| `available(*, include_hidden=False)` | Skill names |
| `list(*, full=False, include_hidden=False)` | Skill metadata, optionally with loaded files |
| `get(name, *, full=False)` | One `Skill` |
| `parts(name)` | `SkillPart` metadata for every file |
| `part(name, path)` | One `SkillFile` |
| `read(name, path="SKILL.md")` | One file's text |
| `markdown(name, *, full=False)` | Main instructions or combined skill Markdown |

Use the main file when the agent needs the normal browser workflow. Load individual parts when a task reaches the capability they describe. Use `full=True` when the host needs to package the complete instruction tree in one operation.

Skill paths reject absolute paths, traversal, empty components, and malformed relative paths. Missing skills or files raise `KeyError`.

`Skill` records its name, frontmatter description, main content, part metadata, loaded files, and hidden state. `SkillPart` records a relative path and kind. `SkillFile` records a relative path and text content.
