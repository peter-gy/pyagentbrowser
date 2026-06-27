from __future__ import annotations

import builtins
import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from agentbrowser._native import skill_data_json

_MAIN_SKILL_PATH = "SKILL.md"


@dataclass(frozen=True, slots=True)
class SkillFile:
    """One bundled skill file.

    Attributes
    ----------
    path
        Path inside the skill directory.
    content
        Text content of the file.
    """

    path: str
    content: str


@dataclass(frozen=True, slots=True)
class SkillPart:
    """Metadata for one bundled skill part."""

    path: str
    kind: str


@dataclass(frozen=True, slots=True)
class Skill:
    """Bundled agent-browser skill.

    Attributes
    ----------
    name
        Skill name.
    description
        Frontmatter description from `SKILL.md`.
    content
        Main `SKILL.md` content.
    parts
        Available files belonging to this skill.
    files
        Loaded supplementary files when requested with `full=True`.
    hidden
        Whether the skill is hidden from default listings.
    """

    name: str
    description: str
    content: str
    parts: tuple[SkillPart, ...] = ()
    files: tuple[SkillFile, ...] = ()
    hidden: bool = False

    @property
    def markdown(self) -> str:
        """Render the skill as Markdown."""
        return markdown(self.name)

    def read(self, path: str = _MAIN_SKILL_PATH) -> str:
        """Read one file from this skill."""
        return self.part(path).content

    def part(self, path: str) -> SkillFile:
        """Return one file from this skill."""
        normalized = _normalize_part_path(path)
        if normalized == _MAIN_SKILL_PATH:
            return SkillFile(path=normalized, content=self.content)
        for file in self.files:
            if file.path == normalized:
                return file
        return _read_skill_part(self.name, normalized)


def available(*, include_hidden: bool = False) -> tuple[str, ...]:
    """Return available bundled skill names.

    Parameters
    ----------
    include_hidden
        Include skills marked hidden in frontmatter.
    """
    return tuple(skill.name for skill in list(include_hidden=include_hidden))


def list(*, full: bool = False, include_hidden: bool = False) -> tuple[Skill, ...]:
    """Return bundled skills.

    Parameters
    ----------
    full
        Load supplementary files into each returned `Skill`.
    include_hidden
        Include skills marked hidden in frontmatter.
    """
    return tuple(
        skill.with_files() if full else skill.without_files()
        for skill in _skills().values()
        if include_hidden or not skill.hidden
    )


def get(name: str, *, full: bool = False) -> Skill:
    """Return one bundled skill by name.

    Parameters
    ----------
    name
        Skill name.
    full
        Load supplementary files into the returned `Skill`.
    """
    try:
        skill = _skills()[name]
    except KeyError as exc:
        raise KeyError(f"skill not found: {name}") from exc
    return skill.with_files() if full else skill.without_files()


def parts(name: str) -> tuple[SkillPart, ...]:
    """Return file metadata for one skill."""
    return get(name).parts


def part(name: str, path: str) -> SkillFile:
    """Return one file from one skill."""
    return get(name).part(path)


def read(name: str, path: str = _MAIN_SKILL_PATH) -> str:
    """Read one bundled skill file as text."""
    return part(name, path).content


def markdown(name: str, *, full: bool = False) -> str:
    """Render one bundled skill as Markdown.

    Parameters
    ----------
    name
        Skill name.
    full
        Include supplementary files after the main `SKILL.md`.
    """
    skill = get(name)
    content = _ensure_trailing_newline(skill.content)
    if not full:
        return content
    for skill_part in skill.parts:
        if skill_part.path == _MAIN_SKILL_PATH:
            continue
        part_content = _ensure_trailing_newline(skill.part(skill_part.path).content)
        content = f"{content}\n--- {skill_part.path} ---\n\n{part_content}"
    return content


@dataclass(frozen=True, slots=True)
class _SkillRecord:
    name: str
    description: str
    content: str
    parts: tuple[SkillPart, ...]
    files: tuple[SkillFile, ...]
    hidden: bool

    def with_files(self) -> Skill:
        return Skill(
            name=self.name,
            description=self.description,
            content=self.content,
            parts=self.parts,
            files=self.files,
            hidden=self.hidden,
        )

    def without_files(self) -> Skill:
        return Skill(
            name=self.name,
            description=self.description,
            content=self.content,
            parts=self.parts,
            hidden=self.hidden,
        )


@lru_cache(maxsize=1)
def _skills() -> Mapping[str, _SkillRecord]:
    files = _skill_files()
    skill_names = sorted(
        path.removesuffix("/SKILL.md") for path in files if path.endswith("/SKILL.md")
    )
    records = [_load_skill(name, files) for name in skill_names]
    names: set[str] = set()
    for record in records:
        if record.name in names:
            raise ValueError(f"duplicate skill name: {record.name}")
        names.add(record.name)
    return {record.name: record for record in records}


def _load_skill(name: str, files: Mapping[str, str]) -> _SkillRecord:
    content = files[f"{name}/SKILL.md"]
    metadata = _parse_frontmatter(content)
    skill_name = metadata.get("name")
    if skill_name is None:
        raise ValueError(f"{name}/SKILL.md is missing frontmatter field 'name'")
    if skill_name != name:
        raise ValueError(
            f"{name}/SKILL.md frontmatter name {skill_name!r} must match its directory"
        )

    skill_files = {
        path.removeprefix(f"{name}/"): file_content
        for path, file_content in files.items()
        if path.startswith(f"{name}/")
    }
    skill_parts = tuple(SkillPart(path=path, kind=_part_kind(path)) for path in sorted(skill_files))
    supplementary = tuple(
        SkillFile(path=path, content=file_content)
        for path, file_content in skill_files.items()
        if path != _MAIN_SKILL_PATH
    )
    return _SkillRecord(
        name=skill_name,
        description=metadata.get("description", ""),
        content=content,
        parts=skill_parts,
        files=tuple(sorted(supplementary, key=lambda file: file.path)),
        hidden=metadata.get("hidden", "").lower() in {"true", "yes"},
    )


@lru_cache(maxsize=1)
def _skill_files() -> Mapping[str, str]:
    raw = json.loads(skill_data_json())
    if not isinstance(raw, builtins.list):
        raise ValueError("native skill data payload must be a list")

    files: dict[str, str] = {}
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("native skill data entries must be objects")
        path = _string_field(item, "path")
        content = _string_field(item, "content")
        files[path] = content
    return dict(sorted(files.items()))


def _string_field(item: Mapping[str, Any], field: str) -> str:
    value = item.get(field)
    if not isinstance(value, str):
        raise ValueError(f"native skill data entry is missing string field {field!r}")
    return value


def _read_skill_part(name: str, path: str) -> SkillFile:
    normalized = _normalize_part_path(path)
    key = f"{name}/{normalized}"
    try:
        content = _skill_files()[key]
    except KeyError as exc:
        raise KeyError(f"skill {name!r} has no part {normalized!r}") from exc
    return SkillFile(path=normalized, content=content)


def _normalize_part_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]

    parts = normalized.split("/")
    if (
        not normalized
        or normalized.startswith("/")
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise KeyError(f"invalid skill part path: {path!r}")
    return normalized


def _part_kind(path: str) -> str:
    if path == _MAIN_SKILL_PATH:
        return "main"
    if path.startswith("references/"):
        return "reference"
    if path.startswith("templates/"):
        return "template"
    return "file"


def _ensure_trailing_newline(content: str) -> str:
    return content if content.endswith("\n") else f"{content}\n"


def _parse_frontmatter(content: str) -> dict[str, str]:
    content = content.lstrip()
    if not content.startswith("---"):
        return {}

    after_opening = content[3:]
    end = after_opening.find("\n---")
    if end == -1:
        return {}

    fields: dict[str, str] = {}
    lines = after_opening[:end].splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        key, separator, value = line.partition(":")
        if not separator:
            index += 1
            continue

        key = key.strip()
        value = _clean_frontmatter_value(value.strip())
        while index + 1 < len(lines) and _is_continuation(lines[index + 1]):
            index += 1
            value = f"{value} {_clean_frontmatter_value(lines[index].strip())}".strip()
        fields[key] = value
        index += 1

    return fields


def _is_continuation(line: str) -> bool:
    return line.startswith("  ") or line.startswith("\t")


def _clean_frontmatter_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
