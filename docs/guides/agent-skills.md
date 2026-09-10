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

Create a named module-owned controller when browser work spans code-mode calls:

```python
browser = browser_agent.create("research")
browser.open("https://example.com")
page = browser.observe()
print(page.origin)
print(page.text)

# In a later code-mode call
browser = browser_agent.get("research")

# After the final call
browser_agent.close("research")
```

Use `browser_agent.names()` to inspect registered controller names. Call
`browser_agent.close_all()` after a task that created several controllers.

Pass `session=agentbrowser.SessionOptions(...)` to `create()`, `open()`, or
`attach()` when the task needs domain restrictions, confirmation policy, or
another session option. Duplicate names raise `ValueError`. `get()` retrieves
one open controller and `close()` releases it.

## Connect through an agent host

An `AgentHost` provides the application target, model-facing image delivery,
and the current execution limit. The target distinguishes a URL to open in a
new automation browser from an authorized connection to an exact existing
page.

```python
import agentbrowser.agent as browser_agent
from agentbrowser import AttachedTarget, OpenTarget

target = host.current_target()
if isinstance(target, OpenTarget):
    browser = browser_agent.open("review", target)
elif isinstance(target, AttachedTarget):
    browser = browser_agent.attach("review", target)

timeout_ms = host.execution_context().limit(10_000)
browser.page.wait_for_text("Ready", timeout_ms=timeout_ms)
screenshot = browser.page.capture.screenshot("artifacts/ready.png")
delivery = host.emit_image(screenshot.content())
```

`ExecutionContext.limit()` reserves one second for tool cleanup by default.
Hosts that support work across calls report `managed_tasks=True`. A Python
background task remains bound to its Python process unless the host documents
stronger ownership.

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
