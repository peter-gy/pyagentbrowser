from __future__ import annotations

import json
import runpy
import subprocess
import tomllib
from pathlib import Path

import pytest

from scripts import update_upstream

ROOT = Path(__file__).resolve().parents[2]
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
    adapter_manifest = tmp_path / "adapter.Cargo.toml"
    adapter_manifest.write_text(
        f'[package]\nname = "agent-browser"\nversion = "{metadata["version"]}"\n'
    )
    monkeypatch.setattr(update_upstream, "UPSTREAM", upstream)
    monkeypatch.setattr(update_upstream, "PROVENANCE", provenance)
    monkeypatch.setattr(update_upstream, "ADAPTER_MANIFEST", adapter_manifest)

    assert update_upstream.main(["--check"]) == 0

    provenance.write_text(json.dumps({**metadata, "commit": "stale"}))
    with pytest.raises(SystemExit):
        update_upstream.main(["--check"])

    provenance.write_text(json.dumps(metadata))
    adapter_manifest.write_text('[package]\nname = "agent-browser"\nversion = "0.0.0"\n')
    with pytest.raises(SystemExit):
        update_upstream.main(["--check"])


def test_upstream_update_check_initializes_a_fresh_clone_submodule(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream_source, metadata = _temporary_upstream(tmp_path / "source")
    template = tmp_path / "template"
    subprocess.run(["git", "init", "-q", str(template)], check=True)
    subprocess.run(["git", "-C", str(template), "config", "user.name", "Test"], check=True)
    subprocess.run(
        ["git", "-C", str(template), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-c",
            "protocol.file.allow=always",
            "-C",
            str(template),
            "submodule",
            "add",
            "-q",
            str(upstream_source),
            "third_party/agent-browser",
        ],
        check=True,
    )
    provenance = template / "src/agentbrowser/_upstream.json"
    provenance.parent.mkdir(parents=True)
    provenance.write_text(json.dumps(metadata))
    adapter_manifest = template / "crates/agent-browser-adapter/Cargo.toml"
    adapter_manifest.parent.mkdir(parents=True)
    adapter_manifest.write_text(
        f'[package]\nname = "agent-browser"\nversion = "{metadata["version"]}"\n'
    )
    subprocess.run(["git", "-C", str(template), "add", "."], check=True)
    subprocess.run(["git", "-C", str(template), "commit", "-qm", "fixture"], check=True)

    root = tmp_path / "fresh-clone"
    subprocess.run(
        ["git", "clone", "-q", "--no-recurse-submodules", str(template), str(root)],
        check=True,
    )
    upstream = root / "third_party/agent-browser"
    assert not (upstream / "cli/Cargo.toml").exists()

    monkeypatch.setenv("GIT_ALLOW_PROTOCOL", "file")
    monkeypatch.setattr(update_upstream, "ROOT", root)
    monkeypatch.setattr(update_upstream, "UPSTREAM", upstream)
    monkeypatch.setattr(update_upstream, "PROVENANCE", root / "src/agentbrowser/_upstream.json")
    monkeypatch.setattr(
        update_upstream,
        "ADAPTER_MANIFEST",
        root / "crates/agent-browser-adapter/Cargo.toml",
    )
    monkeypatch.setattr(update_upstream, "OFFICIAL_REMOTE", str(upstream_source))

    assert update_upstream.main(["--check"]) == 0
    assert (upstream / "cli/Cargo.toml").is_file()
    assert (
        subprocess.check_output(
            ["git", "-C", str(upstream), "rev-parse", "HEAD"],
            text=True,
        ).strip()
        == metadata["commit"]
    )


def test_upstream_update_syncs_adapter_version_and_cargo_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream, metadata = _temporary_upstream(tmp_path)
    provenance = tmp_path / "_upstream.json"
    adapter_manifest = tmp_path / "adapter.Cargo.toml"
    adapter_manifest.write_text(
        '[package]\nname = "agent-browser"\nversion = "0.0.0"\n\n[dependencies]\nserde = "1"\n'
    )
    monkeypatch.setattr(update_upstream, "UPSTREAM", upstream)
    monkeypatch.setattr(update_upstream, "PROVENANCE", provenance)
    monkeypatch.setattr(update_upstream, "ADAPTER_MANIFEST", adapter_manifest)

    commands: list[tuple[list[str], dict[str, str] | None]] = []

    def run(
        command: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        del cwd
        commands.append((command, env))

    monkeypatch.setattr(update_upstream, "_run", run)

    assert update_upstream.main(["--ref", "HEAD"]) == 0
    adapter = tomllib.loads(adapter_manifest.read_text())
    assert adapter["package"] == {
        "name": "agent-browser",
        "version": metadata["version"],
    }
    assert adapter["dependencies"] == {"serde": "1"}
    assert json.loads(provenance.read_text()) == metadata
    cargo_commands = [
        item for item in commands if item[0] == ["cargo", "update", "--package", "agent-browser"]
    ]
    assert len(cargo_commands) == 1
    cargo_env = cargo_commands[0][1]
    assert cargo_env is not None
    configured_cargo = subprocess.check_output(
        [
            "rustup",
            "which",
            "--toolchain",
            update_upstream._rust_toolchain(),
            "cargo",
        ],
        text=True,
    ).strip()
    assert (
        Path(cargo_env["PATH"].split(update_upstream.os.pathsep)[0])
        == Path(configured_cargo).parent
    )


def test_upstream_update_rejects_a_non_fast_forward_pin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    upstream, _metadata = _temporary_upstream(tmp_path)
    first_commit = subprocess.check_output(
        ["git", "-C", str(upstream), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    (upstream / "next").write_text("next")
    subprocess.run(["git", "-C", str(upstream), "add", "next"], check=True)
    subprocess.run(["git", "-C", str(upstream), "commit", "-qm", "next"], check=True)
    monkeypatch.setattr(update_upstream, "UPSTREAM", upstream)
    monkeypatch.setattr(update_upstream, "_run", lambda *args, **kwargs: None)

    with pytest.raises(SystemExit):
        update_upstream.main(["--ref", first_commit])
    assert "not a fast-forward" in capsys.readouterr().err


def test_upstream_update_allows_an_explicit_non_fast_forward_pin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    upstream, _metadata = _temporary_upstream(tmp_path)
    first_commit = subprocess.check_output(
        ["git", "-C", str(upstream), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    (upstream / "next").write_text("next")
    subprocess.run(["git", "-C", str(upstream), "add", "next"], check=True)
    subprocess.run(["git", "-C", str(upstream), "commit", "-qm", "next"], check=True)
    second_commit = subprocess.check_output(
        ["git", "-C", str(upstream), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    provenance = tmp_path / "_upstream.json"
    adapter_manifest = tmp_path / "adapter.Cargo.toml"
    adapter_manifest.write_text('[package]\nname = "agent-browser"\nversion = "1.2.3"\n')
    monkeypatch.setattr(update_upstream, "UPSTREAM", upstream)
    monkeypatch.setattr(update_upstream, "PROVENANCE", provenance)
    monkeypatch.setattr(update_upstream, "ADAPTER_MANIFEST", adapter_manifest)
    monkeypatch.setattr(update_upstream, "_rust_environment", lambda: {})

    def run(
        command: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        del env
        if command[:4] == ["git", "-C", str(upstream), "checkout"]:
            subprocess.run(command, cwd=cwd, check=True)

    monkeypatch.setattr(update_upstream, "_run", run)

    assert update_upstream.main(["--ref", first_commit, "--allow-non-fast-forward"]) == 0
    pinned_commit = subprocess.check_output(
        ["git", "-C", str(upstream), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    assert pinned_commit == first_commit
    assert json.loads(provenance.read_text())["commit"] == first_commit
    assert f"{second_commit}..{first_commit}" in capsys.readouterr().out


def test_upstream_update_reports_an_already_pinned_checkout_without_rewriting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    upstream, metadata = _temporary_upstream(tmp_path)
    provenance = tmp_path / "_upstream.json"
    provenance.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    adapter_manifest = tmp_path / "adapter.Cargo.toml"
    adapter_manifest.write_text(
        f'[package]\nname = "agent-browser"\nversion = "{metadata["version"]}"\n'
    )
    monkeypatch.setattr(update_upstream, "UPSTREAM", upstream)
    monkeypatch.setattr(update_upstream, "PROVENANCE", provenance)
    monkeypatch.setattr(update_upstream, "ADAPTER_MANIFEST", adapter_manifest)
    before = (provenance.read_bytes(), adapter_manifest.read_bytes())
    commands: list[list[str]] = []
    monkeypatch.setattr(
        update_upstream,
        "_run",
        lambda command, **_kwargs: commands.append(command),
    )

    assert update_upstream.main(["--ref", "HEAD"]) == 0
    assert (provenance.read_bytes(), adapter_manifest.read_bytes()) == before
    assert not any("checkout" in command or command[0] in {"cargo", "uv"} for command in commands)
    assert "already pinned" in capsys.readouterr().out


def test_upstream_update_refuses_a_dirty_submodule(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream, _metadata = _temporary_upstream(tmp_path)
    (upstream / "local-change").write_text("dirty")
    monkeypatch.setattr(update_upstream, "UPSTREAM", upstream)

    with pytest.raises(SystemExit):
        update_upstream.main([])
