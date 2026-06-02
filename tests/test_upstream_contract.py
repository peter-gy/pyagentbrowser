from __future__ import annotations

import re
import runpy
import subprocess
from pathlib import Path

import pytest
import tomli

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.packaging


def test_agent_browser_is_tracked_as_official_submodule() -> None:
    def gitmodule_value(key: str) -> str:
        return subprocess.check_output(
            ["git", "config", "--file", ".gitmodules", "--get", key],
            cwd=ROOT,
            text=True,
        ).strip()

    assert gitmodule_value("submodule.third_party/agent-browser.path") == (
        "third_party/agent-browser"
    )
    assert gitmodule_value("submodule.third_party/agent-browser.url") == (
        "https://github.com/vercel-labs/agent-browser.git"
    )
    submodule_entry = subprocess.check_output(
        ["git", "ls-files", "-s", "third_party/agent-browser"],
        cwd=ROOT,
        text=True,
    ).split()
    assert submodule_entry[0] == "160000"


def test_rust_dependency_uses_clean_adapter_over_submodule() -> None:
    workspace_cargo = tomli.loads((ROOT / "Cargo.toml").read_text())
    py_cargo = tomli.loads((ROOT / "crates/pyagentbrowser/Cargo.toml").read_text())

    assert "crates/pyagentbrowser" in workspace_cargo["workspace"]["members"]
    assert "crates/agent-browser-adapter" in workspace_cargo["workspace"]["exclude"]
    assert "third_party/agent-browser" in workspace_cargo["workspace"]["exclude"]
    assert py_cargo["dependencies"]["agent-browser"]["path"] == "../agent-browser-adapter"


def test_prerelease_version_tracks_pinned_upstream_tag() -> None:
    project = tomli.loads((ROOT / "pyproject.toml").read_text())["project"]
    py_cargo = tomli.loads((ROOT / "crates/pyagentbrowser/Cargo.toml").read_text())
    adapter_cargo = tomli.loads((ROOT / "crates/agent-browser-adapter/Cargo.toml").read_text())
    release = runpy.run_path(str(ROOT / "src/pyagentbrowser/_version.py"))

    upstream_tag = subprocess.check_output(
        ["git", "describe", "--tags", "--exact-match", "HEAD"],
        cwd=ROOT / "third_party/agent-browser",
        text=True,
    ).strip()
    upstream_commit = subprocess.check_output(
        ["git", "rev-parse", "--short=7", "HEAD"],
        cwd=ROOT / "third_party/agent-browser",
        text=True,
    ).strip()
    upstream_version = upstream_tag.removeprefix("v")
    release_match = re.fullmatch(rf"{re.escape(upstream_version)}rc(\d+)", project["version"])

    assert project["name"] == "pyagentbrowser"
    assert release_match is not None
    assert "+" not in project["version"]
    assert py_cargo["package"]["version"] == (f"{upstream_version}-rc.{release_match.group(1)}")
    assert adapter_cargo["package"]["version"] == upstream_version
    assert release["PACKAGE_NAME"] == "pyagentbrowser"
    assert release["PACKAGE_VERSION"] == project["version"]
    assert release["UPSTREAM_TAG"] == upstream_tag
    assert release["UPSTREAM_VERSION"] == upstream_version
    assert release["UPSTREAM_COMMIT"] == upstream_commit
    assert project["urls"]["Upstream agent-browser commit"].endswith(upstream_commit)


@pytest.mark.timeout(300)
def test_adapter_builds_and_exposes_upstream_behavior(tmp_path: Path) -> None:
    adapter = ROOT / "crates" / "agent-browser-adapter"
    target_dir = tmp_path / "target"

    subprocess.run(
        [
            "rustup",
            "run",
            "stable",
            "cargo",
            "test",
            "--manifest-path",
            str(adapter / "Cargo.toml"),
            "--target-dir",
            str(target_dir),
            "--test",
            "smoke",
        ],
        cwd=ROOT,
        check=True,
    )
