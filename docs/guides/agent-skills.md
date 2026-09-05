---
title: Load embedded agent skills
description: Read the agent-browser instruction files embedded in the installed pyagentbrowser wheel.
---

# Load embedded agent skills

An agent skill is a Markdown instruction set with optional supporting files. The pyagentbrowser wheel embeds the skills from its pinned `agent-browser` engine so an application can supply version-matched browser guidance to an agent.

## Read the main instruction file

```python
import agentbrowser.skills as skills

print(skills.available())
print(skills.read("core"))
```

The `core` skill teaches the engine's browser interaction workflow. `read(name)` returns its `SKILL.md` content.

## Inspect supporting parts

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
