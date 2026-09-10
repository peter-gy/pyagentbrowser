---
title: Load agent skills and code-mode guidance
description: Bind application targets, image delivery, execution limits, and version-matched browser instructions to a code-mode agent.
---

# Load agent skills and code-mode guidance

The `agentbrowser.agent` module keeps named browser controllers across calls in
one Python process. An `AgentHost` supplies the current application target,
image delivery, and execution limits. The wheel carries an Agent Plugin with
Python-specific browser instructions and the pinned engine's native skills.

## Keep a controller across calls

```python
import agentbrowser.agent as browser_agent

print(browser_agent.help())
```

`browser_agent.help()` returns a short SDK workflow and the paths to the Agent Plugin resources installed with the same pyagentbrowser version.

Create a named module-owned controller when browser work spans code-mode calls:

```python
browser = browser_agent.create("research")
browser.page.open("https://example.com")
page = browser.page.observe()
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

Read [Code-mode integration](/guides/code-mode) to supply an application target,
return model-facing screenshot content, and manage work across tool calls.

## Load the Python instructions

```python
plugin = browser_agent.agent_plugin()
skill = browser_agent.agent_skill()

print(plugin)
print(skill.file("SKILL.md"))
instructions = skill.body
```

The packaged `pyagentbrowser` skill uses `Browser`, `AsyncBrowser`, typed namespaces, and `browser.native` directly. These Python operations share the embedded native action service with the upstream engine.

## Discover the capability in Marimo

[Marimo](https://marimo.io/), a Python notebook environment, discovers installed
code-mode capabilities through package entry points in version 0.24.0 or later.
Install pyagentbrowser in the notebook environment, then inspect its entry:

```python
import marimo._code_mode as cm

print(cm.capabilities()["pyagentbrowser"])
```

Capability discovery exposes the Python module and its instructions. The
code-execution host must also bind an `AgentHost` and forward image content to
the model for `current_host()` and visual assessment to work.

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
