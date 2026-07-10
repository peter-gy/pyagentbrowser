from __future__ import annotations

import json
import runpy
import subprocess
import tomllib
from pathlib import Path

import pytest

from scripts import update_upstream

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.packaging


def _gitmodule_value(key: str) -> str:
    return subprocess.check_output(
        ["git", "config", "--file", ".gitmodules", "--get", key],
        cwd=ROOT,
        text=True,
    ).strip()


def test_upstream_source_is_an_official_pinned_submodule() -> None:
    assert _gitmodule_value("submodule.third_party/agent-browser.path") == (
        "third_party/agent-browser"
    )
    assert _gitmodule_value("submodule.third_party/agent-browser.url") == (
        "https://github.com/vercel-labs/agent-browser.git"
    )
    entry = subprocess.check_output(
        ["git", "ls-files", "-s", "third_party/agent-browser"],
        cwd=ROOT,
        text=True,
    ).split()
    assert entry[0] == "160000"


def test_extension_and_adapter_resolve_in_one_locked_workspace() -> None:
    metadata = json.loads(
        subprocess.check_output(
            ["cargo", "metadata", "--locked", "--no-deps", "--format-version", "1"],
            cwd=ROOT,
            text=True,
        )
    )
    packages = {package["name"]: package for package in metadata["packages"]}

    assert {"pyagentbrowser", "agent-browser"} <= packages.keys()
    py_dependencies = {
        dependency["name"]: dependency for dependency in packages["pyagentbrowser"]["dependencies"]
    }
    adapter_manifest = Path(py_dependencies["agent-browser"]["path"]) / "Cargo.toml"
    assert (
        adapter_manifest.resolve() == (ROOT / "crates/agent-browser-adapter/Cargo.toml").resolve()
    )
    assert Path(metadata["workspace_root"]).resolve() == ROOT.resolve()


def test_sdk_version_and_upstream_provenance_are_independent_and_consistent() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    py_cargo = tomllib.loads((ROOT / "crates/pyagentbrowser/Cargo.toml").read_text())
    release = runpy.run_path(str(ROOT / "src/agentbrowser/_version.py"))
    release_tool = runpy.run_path(str(ROOT / "scripts/prepare_prerelease.py"))
    upstream = ROOT / "third_party/agent-browser"
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=upstream,
        text=True,
    ).strip()
    upstream_version = tomllib.loads((upstream / "cli/Cargo.toml").read_text())["package"][
        "version"
    ]
    assert project["name"] == "pyagentbrowser"
    assert project["version"] == release["PACKAGE_VERSION"]
    assert py_cargo["package"]["version"] == release_tool["_cargo_version"](project["version"])
    assert release["UPSTREAM_COMMIT"] == commit
    assert release["UPSTREAM_VERSION"] == upstream_version
    provenance = json.loads((ROOT / "src/agentbrowser/_upstream.json").read_text())
    assert provenance == {"commit": commit, "version": upstream_version}
    assert project["urls"]["Upstream agent-browser"].endswith("vercel-labs/agent-browser")


@pytest.mark.parametrize(
    "python_version,cargo_version",
    [
        ("1.2.3", "1.2.3"),
        ("1.2.3a4", "1.2.3-alpha.4"),
        ("1.2.3b5", "1.2.3-beta.5"),
        ("1.2.3rc6", "1.2.3-rc.6"),
    ],
)
def test_python_package_versions_map_to_cargo_versions(
    python_version: str,
    cargo_version: str,
) -> None:
    release_tool = runpy.run_path(str(ROOT / "scripts/prepare_prerelease.py"))

    assert release_tool["_cargo_version"](python_version) == cargo_version


def _temporary_upstream(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    upstream = tmp_path / "agent-browser"
    (upstream / "cli").mkdir(parents=True)
    (upstream / "cli/Cargo.toml").write_text(
        '[package]\nname = "agent-browser"\nversion = "1.2.3"\n'
    )
    subprocess.run(["git", "init", "-q", str(upstream)], check=True)
    subprocess.run(["git", "-C", str(upstream), "config", "user.name", "Test"], check=True)
    subprocess.run(
        ["git", "-C", str(upstream), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(upstream),
            "remote",
            "add",
            "origin",
            update_upstream.OFFICIAL_REMOTE,
        ],
        check=True,
    )
    subprocess.run(["git", "-C", str(upstream), "add", "cli/Cargo.toml"], check=True)
    subprocess.run(["git", "-C", str(upstream), "commit", "-qm", "fixture"], check=True)
    commit = subprocess.check_output(
        ["git", "-C", str(upstream), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    return upstream, {"commit": commit, "version": "1.2.3"}


def test_upstream_update_check_verifies_live_git_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream, metadata = _temporary_upstream(tmp_path)
    provenance = tmp_path / "_upstream.json"
    provenance.write_text(json.dumps(metadata))
    monkeypatch.setattr(update_upstream, "UPSTREAM", upstream)
    monkeypatch.setattr(update_upstream, "PROVENANCE", provenance)

    assert update_upstream.main(["--check"]) == 0

    provenance.write_text(json.dumps({**metadata, "commit": "stale"}))
    with pytest.raises(SystemExit):
        update_upstream.main(["--check"])


def test_upstream_update_refuses_a_dirty_submodule(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream, _metadata = _temporary_upstream(tmp_path)
    (upstream / "local-change").write_text("dirty")
    monkeypatch.setattr(update_upstream, "UPSTREAM", upstream)

    with pytest.raises(SystemExit):
        update_upstream.main([])
