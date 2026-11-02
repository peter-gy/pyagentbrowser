"""Native agent-browser skills embedded in the extension at build time."""

from __future__ import annotations

from dataclasses import dataclass

from agentbrowser._native import skill_file, skill_names, skill_record

MAIN = "SKILL.md"


@dataclass(frozen=True, slots=True)
class Skill:
    """One embedded skill.

    Attributes
    ----------
    name
        Skill directory name.
    description
        Frontmatter description from `SKILL.md`.
    hidden
        Whether the skill is omitted from `available()` by default.
    parts
        Relative paths of every file in the skill, including `SKILL.md`.
    """

    name: str
    description: str
    hidden: bool
    parts: tuple[str, ...]

    def read(self, path: str = MAIN) -> str:
        """Return the text of one file in this skill."""
        return read(self.name, path)

    def markdown(self, *, full: bool = False) -> str:
        """Return `SKILL.md`, followed by every other part when `full` is set."""
        sections = [_with_newline(self.read())]
        if full:
            sections.extend(
                f"\n--- {part} ---\n\n{_with_newline(self.read(part))}"
                for part in self.parts
                if part != MAIN
            )
        return "".join(sections)


def available(*, include_hidden: bool = False) -> tuple[str, ...]:
    """Return embedded skill names in sorted order."""
    return skill_names(include_hidden)


def get(name: str) -> Skill:
    """Return one embedded skill. Raises `KeyError` for an unknown name."""
    record = skill_record(name)
    if record is None:
        raise KeyError(f"skill not found: {name}")
    description, hidden, parts = record
    return Skill(name, description, hidden, parts)


def read(name: str, path: str = MAIN) -> str:
    """Return the text of one skill file. Raises `KeyError` for an unknown skill or part."""
    normalized = _normalize(path)
    content = skill_file(name, normalized)
    if content is not None:
        return content
    if skill_record(name) is None:
        raise KeyError(f"skill not found: {name}")
    raise KeyError(f"skill {name!r} has no part {normalized!r}")


def _normalize(path: str) -> str:
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if (
        not normalized
        or normalized.startswith("/")
        or any(part in {"", ".", ".."} for part in normalized.split("/"))
    ):
        raise KeyError(f"invalid skill part path: {path!r}")
    return normalized


def _with_newline(content: str) -> str:
    return content if content.endswith("\n") else f"{content}\n"
