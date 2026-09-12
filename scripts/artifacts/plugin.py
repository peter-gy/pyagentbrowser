from __future__ import annotations

import json
import zipfile
from pathlib import Path

from .core import _fail

AGENT_PLUGIN_FILES = frozenset(
    {
        "plugin.json",
        "skills/pyagentbrowser/SKILL.md",
        "skills/pyagentbrowser/agents/openai.yaml",
        "skills/pyagentbrowser/references/api-map.md",
        "skills/pyagentbrowser/references/lifecycle-and-safety.md",
    }
)


def assert_wheel_agent_plugin(path: Path, names: set[str]) -> None:
    marker_names = [name for name in names if name.endswith(".dist-info/agent_plugins.json")]
    if len(marker_names) != 1:
        _fail(f"wheel should contain one Agent Plugin marker: {marker_names}")
    marker_name = marker_names[0]
    dist_info = marker_name.rsplit("/", 1)[0]
    expected_root = f"{dist_info.removesuffix('.dist-info')}.agent-plugin"
    with zipfile.ZipFile(path) as archive:
        marker = json.loads(archive.read(marker_name))
    if marker.get("root") != expected_root:
        _fail(f"wheel Agent Plugin marker has wrong root: {marker.get('root')!r}")
    files = marker.get("files")
    if (
        not isinstance(files, list)
        or not all(isinstance(name, str) for name in files)
        or len(files) != len(AGENT_PLUGIN_FILES)
        or set(files) != AGENT_PLUGIN_FILES
    ):
        _fail(
            "wheel Agent Plugin marker file inventory drifted: "
            f"expected={sorted(AGENT_PLUGIN_FILES)}, actual={files!r}"
        )
    payload = {
        name.removeprefix(f"{expected_root}/")
        for name in names
        if name.startswith(f"{expected_root}/")
    }
    if payload != AGENT_PLUGIN_FILES:
        _fail(
            "wheel Agent Plugin payload drifted: "
            f"expected={sorted(AGENT_PLUGIN_FILES)}, actual={sorted(payload)}"
        )
    unmanaged = sorted(
        name for name in names if name == "plugin.json" or name.startswith("skills/")
    )
    if unmanaged:
        _fail(f"wheel contains unmanaged Agent Plugin files: {unmanaged}")


def assert_sdist_agent_plugin(names: set[str]) -> None:
    prefix = ".agent-plugin/"
    payload = {name.removeprefix(prefix) for name in names if name.startswith(prefix)}
    if payload != AGENT_PLUGIN_FILES:
        _fail(
            "sdist Agent Plugin payload drifted: "
            f"expected={sorted(AGENT_PLUGIN_FILES)}, actual={sorted(payload)}"
        )
    unmanaged = sorted(
        name for name in names if name == "plugin.json" or name.startswith("skills/")
    )
    if unmanaged:
        _fail(f"sdist contains unmanaged Agent Plugin files: {unmanaged}")
