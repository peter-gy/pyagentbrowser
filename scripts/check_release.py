from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.release_version import ReleaseVersion, ReleaseVersionError

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "third_party" / "agent-browser"


@dataclass(frozen=True)
class ReleaseMetadata:
    package: ReleaseVersion
    upstream_commit: str


def _git(directory: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(directory), *args],
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip()


def _manifest(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _package_version(root: Path) -> str:
    project: dict[str, Any] = _manifest(root / "pyproject.toml")["project"]
    if not isinstance(project, dict):
        raise ReleaseVersionError("pyproject.toml is missing [project]")
    return str(project["version"])


def _runtime_version(root: Path) -> str:
    source = (root / "src/agentbrowser/_version.py").read_text(encoding="utf-8")
    match = re.search(r'^PACKAGE_VERSION = "([^"]+)"$', source, re.MULTILINE)
    if match is None:
        raise ReleaseVersionError("src/agentbrowser/_version.py is missing PACKAGE_VERSION")
    return match.group(1)


def _cargo_package_version(path: Path) -> str:
    package: dict[str, Any] = _manifest(path)["package"]
    if not isinstance(package, dict):
        raise ReleaseVersionError(f"{path} is missing [package]")
    return str(package["version"])


def check_metadata(root: Path = ROOT, upstream: Path = UPSTREAM) -> ReleaseMetadata:
    package = ReleaseVersion.parse(_package_version(root))
    runtime_version = _runtime_version(root)
    if runtime_version != package.public:
        raise ReleaseVersionError(
            f"runtime package version {runtime_version} must be {package.public}"
        )

    py_cargo_path = root / "crates/pyagentbrowser/Cargo.toml"
    cargo_version = _cargo_package_version(py_cargo_path)
    if cargo_version != package.cargo:
        raise ReleaseVersionError(
            f"crates/pyagentbrowser version {cargo_version} must be {package.cargo}"
        )

    upstream_version = _cargo_package_version(upstream / "cli/Cargo.toml")
    if upstream_version != package.upstream:
        raise ReleaseVersionError(
            f"pyagentbrowser {package.public} must embed agent-browser {package.upstream}, "
            f"found {upstream_version}"
        )

    if dirty := _git(upstream, "status", "--porcelain"):
        raise ReleaseVersionError(f"embedded agent-browser worktree must be clean, found: {dirty}")

    upstream_commit = _git(upstream, "rev-parse", "HEAD")
    upstream_tag = f"v{package.upstream}"
    try:
        tagged_commit = _git(upstream, "rev-parse", f"refs/tags/{upstream_tag}^{{commit}}")
    except subprocess.CalledProcessError as error:
        raise ReleaseVersionError(
            f"embedded agent-browser {package.upstream} must resolve from tag {upstream_tag}; "
            "fetch upstream tags before checking the release"
        ) from error
    if tagged_commit != upstream_commit:
        raise ReleaseVersionError(
            f"embedded agent-browser commit {upstream_commit} must match {upstream_tag} "
            f"at {tagged_commit}"
        )

    upstream_metadata = json.loads(
        (root / "src/agentbrowser/_upstream.json").read_text(encoding="utf-8")
    )
    expected_upstream = {"commit": upstream_commit, "version": upstream_version}
    if upstream_metadata != expected_upstream:
        raise ReleaseVersionError("src/agentbrowser/_upstream.json is not synced")

    adapter_path = root / "crates/agent-browser-adapter/Cargo.toml"
    adapter_version = _cargo_package_version(adapter_path)
    if adapter_version != upstream_version:
        raise ReleaseVersionError(
            f"crates/agent-browser-adapter version {adapter_version} must be {upstream_version}"
        )
    return ReleaseMetadata(package=package, upstream_commit=upstream_commit)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify the pyagentbrowser release version and embedded upstream tag."
    )
    parser.add_argument(
        "--tag",
        help="planned or current pyagentbrowser Git tag, including its leading v",
    )
    args = parser.parse_args(argv)
    try:
        metadata = check_metadata()
        if args.tag is not None:
            tag_version = ReleaseVersion.from_tag(args.tag)
            if tag_version != metadata.package:
                raise ReleaseVersionError(
                    f"package version {metadata.package.public} must match release tag {args.tag}"
                )
    except (
        json.JSONDecodeError,
        KeyError,
        OSError,
        ReleaseVersionError,
        subprocess.CalledProcessError,
        tomllib.TOMLDecodeError,
    ) as error:
        print(error, file=sys.stderr)
        return 1

    print(
        f"verified pyagentbrowser {metadata.package.public} "
        f"(Cargo {metadata.package.cargo}) with agent-browser "
        f"v{metadata.package.upstream} ({metadata.upstream_commit})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
