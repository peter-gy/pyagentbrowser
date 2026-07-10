from __future__ import annotations

from pathlib import Path

import pytest

import agentbrowser.skills as skills
from agentbrowser.skills import Skill, SkillFile, SkillPart

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.sdk_dx


def test_skills_module_lists_native_embedded_skill_data() -> None:
    available = skills.available()
    listed = skills.list()

    assert "core" in available
    assert all(isinstance(skill, Skill) for skill in listed)
    assert {skill.name for skill in listed} == set(available)


def test_skills_get_loads_core_skill_payload() -> None:
    core = skills.get("core")

    assert core.name == "core"
    assert core.description
    assert core.content
    assert core.parts
    assert SkillPart(path="SKILL.md", kind="main") in core.parts
    assert core.files == ()


def test_skills_full_load_includes_supplementary_parts() -> None:
    skill = skills.get("core", full=True)
    file_by_path = {file.path: file for file in skill.files}
    supplementary_parts = [part for part in skill.parts if part.path != "SKILL.md"]

    assert all(isinstance(file, SkillFile) for file in skill.files)
    assert skill.files
    for part in supplementary_parts:
        assert skill.part(part.path) == file_by_path[part.path]
        assert skill.part(part.path).content


def test_skills_read_returns_main_part_content() -> None:
    skill = skills.get("core")
    part_paths = [part.path for part in skill.parts]

    assert "SKILL.md" in part_paths
    assert skills.parts("core") == skill.parts
    assert skills.read("core") == skill.content


@pytest.mark.parametrize(
    "part_path",
    [part.path for part in skills.get("core").parts if part.path != "SKILL.md"],
)
def test_skills_read_resolves_supplementary_part(part_path: str) -> None:
    skill = skills.get("core")

    supplementary_file = skill.part(part_path)
    assert supplementary_file == skills.part("core", part_path)
    assert supplementary_file.path == part_path
    assert supplementary_file.content


def test_skills_read_normalizes_relative_part_path() -> None:
    skill = skills.get("core")
    part_path = next(part.path for part in skill.parts if part.path != "SKILL.md")
    supplementary_file = skill.part(part_path)

    assert skill.read(f"./{part_path}") == supplementary_file.content


def test_skills_markdown_renders_main_skill_content() -> None:
    skill = skills.get("core")

    markdown = skills.markdown("core")
    assert markdown == skill.markdown
    assert markdown == skill.content
    assert skills.markdown("core", full=False) == skill.content


def test_skills_markdown_full_includes_supplementary_files() -> None:
    skill = skills.get("core")

    full_markdown = skills.markdown("core", full=True)
    assert skill.content in full_markdown
    for file in skills.get("core", full=True).files:
        assert file.path in full_markdown
        assert file.content in full_markdown


def test_skill_part_rejects_missing_part() -> None:
    skill = skills.get("core")

    with pytest.raises(KeyError, match="no part"):
        skill.part("references/missing.md")


def test_skills_read_rejects_invalid_part_path() -> None:
    with pytest.raises(KeyError, match="invalid skill part path"):
        skills.read("core", "../SKILL.md")


def test_skills_get_missing_name_raises_key_error() -> None:
    with pytest.raises(KeyError, match="skill not found"):
        skills.get("missing")


def test_native_skill_data_matches_upstream_submodule_snapshot() -> None:
    upstream = ROOT / "third_party" / "agent-browser" / "skill-data"
    assert upstream.is_dir()

    upstream_files = {
        path.relative_to(upstream): path.read_text()
        for path in upstream.rglob("*")
        if path.is_file()
    }
    public_files: dict[Path, str] = {}
    for skill in skills.list(include_hidden=True, full=True):
        public_files[Path(skill.name) / "SKILL.md"] = skills.read(skill.name)
        for file in skill.files:
            public_files[Path(skill.name) / file.path] = skills.read(skill.name, file.path)

    assert public_files == upstream_files
