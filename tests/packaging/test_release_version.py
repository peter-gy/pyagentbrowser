from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from packaging.version import Version

from scripts import check_release, previous_release_tag
from scripts.release_version import ReleaseVersion, ReleaseVersionError

ROOT = Path(__file__).resolve().parents[2]


def package_version() -> str:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    return str(project["version"])


def run_release_check(tag: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "scripts.check_release", "--tag", tag],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )


def release_tree(tmp_path: Path) -> tuple[Path, Path, str]:
    root = tmp_path / "pyagentbrowser"
    upstream = root / "third_party/agent-browser"
    (root / "src/agentbrowser").mkdir(parents=True)
    (root / "crates/pyagentbrowser").mkdir(parents=True)
    (root / "crates/agent-browser-adapter").mkdir(parents=True)
    (upstream / "cli").mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "pyagentbrowser"\nversion = "1.2.3.1"\n'
    )
    (root / "src/agentbrowser/_version.py").write_text('PACKAGE_VERSION = "1.2.3.1"\n')
    (root / "crates/pyagentbrowser/Cargo.toml").write_text(
        '[package]\nname = "pyagentbrowser"\nversion = "1.2.3+py.1"\n'
    )
    (root / "crates/agent-browser-adapter/Cargo.toml").write_text(
        '[package]\nname = "agent-browser"\nversion = "1.2.3"\n'
    )
    (upstream / "cli/Cargo.toml").write_text(
        '[package]\nname = "agent-browser"\nversion = "1.2.3"\n'
    )
    subprocess.run(["git", "init", "-q", str(upstream)], check=True)
    subprocess.run(["git", "-C", str(upstream), "config", "user.name", "Test"], check=True)
    subprocess.run(
        ["git", "-C", str(upstream), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(["git", "-C", str(upstream), "add", "cli/Cargo.toml"], check=True)
    subprocess.run(["git", "-C", str(upstream), "commit", "-qm", "upstream release"], check=True)
    subprocess.run(["git", "-C", str(upstream), "tag", "v1.2.3"], check=True)
    commit = subprocess.check_output(
        ["git", "-C", str(upstream), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    (root / "src/agentbrowser/_upstream.json").write_text(
        json.dumps({"commit": commit, "version": "1.2.3"})
    )
    return root, upstream, commit


def tagged_repository(tmp_path: Path, tags: tuple[str, ...]) -> Path:
    repository = tmp_path / "repository"
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    subprocess.run(["git", "-C", str(repository), "config", "user.name", "Test"], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "config", "user.email", "test@example.com"],
        check=True,
    )
    tracked = repository / "release"
    for tag in tags:
        tracked.write_text(f"{tag}\n")
        subprocess.run(["git", "-C", str(repository), "add", "release"], check=True)
        subprocess.run(["git", "-C", str(repository), "commit", "-qm", tag], check=True)
        subprocess.run(["git", "-C", str(repository), "tag", tag], check=True)
    return repository


@pytest.mark.parametrize(
    "public,upstream,revision,release_candidate,cargo",
    [
        ("1.2.3", "1.2.3", 0, None, "1.2.3"),
        ("1.2.3rc4", "1.2.3", 0, 4, "1.2.3-rc.4"),
        ("1.2.3.1", "1.2.3", 1, None, "1.2.3+py.1"),
        ("1.2.3.12rc4", "1.2.3", 12, 4, "1.2.3-rc.4+py.12"),
    ],
)
def test_release_version_preserves_upstream_and_downstream_identity(
    public: str,
    upstream: str,
    revision: int,
    release_candidate: int | None,
    cargo: str,
) -> None:
    release = ReleaseVersion.parse(public)

    assert release.public == public
    assert release.upstream == upstream
    assert release.revision == revision
    assert release.release_candidate == release_candidate
    assert release.cargo == cargo
    assert ReleaseVersion.from_tag(f"v{public}") == release


@pytest.mark.parametrize(
    "version",
    [
        "1.2",
        "1.2.3.0",
        "1.2.3.post1",
        "1.2.3+py.1",
        "1.2.3a1",
        "1.2.3b1",
        "01.2.3",
        "1.2.3.1٢",
    ],
)
def test_release_version_rejects_versions_outside_the_public_contract(version: str) -> None:
    with pytest.raises(ReleaseVersionError):
        ReleaseVersion.parse(version)


def test_release_versions_follow_pep_440_ordering() -> None:
    public_versions = [
        "0.36.0rc1",
        "0.36.0",
        "0.36.0.1rc1",
        "0.36.0.1",
        "0.36.0.2rc1",
        "0.36.0.2",
        "0.37.0rc1",
        "0.37.0",
    ]

    assert [Version(version) for version in public_versions] == sorted(
        Version(version) for version in public_versions
    )


def test_release_metadata_accepts_an_exact_official_upstream_tag(tmp_path: Path) -> None:
    root, upstream, commit = release_tree(tmp_path)

    metadata = check_release.check_metadata(root, upstream)

    assert metadata.package.public == "1.2.3.1"
    assert metadata.package.cargo == "1.2.3+py.1"
    assert metadata.upstream_commit == commit


def test_release_metadata_rejects_a_commit_past_the_encoded_upstream_tag(tmp_path: Path) -> None:
    root, upstream, _commit = release_tree(tmp_path)
    (upstream / "change").write_text("after release\n")
    subprocess.run(["git", "-C", str(upstream), "add", "change"], check=True)
    subprocess.run(["git", "-C", str(upstream), "commit", "-qm", "after release"], check=True)

    with pytest.raises(ReleaseVersionError, match=r"must match v1\.2\.3"):
        check_release.check_metadata(root, upstream)


def test_release_metadata_rejects_modified_upstream_source(tmp_path: Path) -> None:
    root, upstream, _commit = release_tree(tmp_path)
    (upstream / "cli/Cargo.toml").write_text(
        '[package]\nname = "agent-browser"\nversion = "1.2.3"\n# modified\n'
    )

    with pytest.raises(ReleaseVersionError, match="worktree must be clean"):
        check_release.check_metadata(root, upstream)


def test_previous_release_tag_follows_git_ancestry_across_downstream_revisions(
    tmp_path: Path,
) -> None:
    repository = tagged_repository(tmp_path, ("v1.2.3", "v1.2.3.1", "v1.2.3.2"))

    assert previous_release_tag.previous_release_tag("v1.2.3.2", repository) == "v1.2.3.1"


def test_final_release_notes_compare_with_the_previous_final_release(tmp_path: Path) -> None:
    repository = tagged_repository(tmp_path, ("v1.2.3", "v1.2.3.1rc1", "v1.2.3.1"))

    assert previous_release_tag.previous_release_tag("v1.2.3.1", repository) == "v1.2.3"


def test_release_candidate_notes_compare_with_the_nearest_release_tag(tmp_path: Path) -> None:
    repository = tagged_repository(tmp_path, ("v1.2.3", "v1.2.3.1rc1", "v1.2.3.1rc2"))

    assert previous_release_tag.previous_release_tag("v1.2.3.1rc2", repository) == "v1.2.3.1rc1"


def test_release_check_accepts_current_package_tag() -> None:
    version = package_version()
    upstream = json.loads((ROOT / "src/agentbrowser/_upstream.json").read_text())
    result = run_release_check(f"v{version}")

    assert result.returncode == 0
    assert f"verified pyagentbrowser {version}" in result.stdout
    assert f"with agent-browser v{upstream['version']} ({upstream['commit']})" in result.stdout


@pytest.mark.parametrize("tag", ["0.36.0.1", "v0.36.0.0", "v0.36.0.post1"])
def test_release_check_rejects_invalid_tag(tag: str) -> None:
    result = run_release_check(tag)

    assert result.returncode == 1
    assert "invalid pyagentbrowser" in result.stderr


def test_release_check_rejects_mismatched_package_tag() -> None:
    version = package_version()
    tag = f"v{Version(version).major + 1}.0.0"
    result = run_release_check(tag)

    assert result.returncode == 1
    assert f"package version {version} must match release tag {tag}" in result.stderr
