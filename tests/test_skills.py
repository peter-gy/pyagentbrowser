from __future__ import annotations

import pytest

import agentbrowser.skills as skills

pytestmark = pytest.mark.sdk_dx


def test_available_lists_visible_skills_in_sorted_order() -> None:
    names = skills.available()

    assert "core" in names
    assert list(names) == sorted(names)
    assert set(names) <= set(skills.available(include_hidden=True))
    assert all(not skills.get(name).hidden for name in names)


def test_get_returns_frontmatter_and_part_paths() -> None:
    core = skills.get("core")

    assert core.name == "core"
    assert core.description
    assert "SKILL.md" in core.parts
    assert any(part.startswith("references/") for part in core.parts)


def test_read_returns_main_and_supplementary_parts() -> None:
    core = skills.get("core")
    reference = next(part for part in core.parts if part.startswith("references/"))

    assert core.read().startswith("---")
    assert skills.read("core") == core.read("SKILL.md")
    assert skills.read("core", reference) == core.read(reference)
    assert core.read(f"./{reference}") == core.read(reference)


def test_markdown_appends_every_part_when_full() -> None:
    core = skills.get("core")

    assert core.markdown() == core.read()
    full = core.markdown(full=True)
    for part in core.parts:
        assert core.read(part) in full
        if part != "SKILL.md":
            assert f"--- {part} ---" in full


def test_read_rejects_missing_and_invalid_parts() -> None:
    with pytest.raises(KeyError, match="no part"):
        skills.read("core", "references/missing.md")
    with pytest.raises(KeyError, match="invalid skill part path"):
        skills.read("core", "../SKILL.md")


def test_unknown_skill_raises_key_error() -> None:
    with pytest.raises(KeyError, match="skill not found"):
        skills.get("missing")
    with pytest.raises(KeyError, match="skill not found"):
        skills.read("missing")
