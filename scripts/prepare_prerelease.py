from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "third_party" / "agent-browser"


class ReleaseVersionError(RuntimeError):
    pass


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(UPSTREAM), *args],
        text=True,
    ).strip()


def _cargo_version(python_version: str) -> str:
    match = re.fullmatch(r"(\d+\.\d+\.\d+)(?:(a|b|rc)(\d+))?", python_version)
    if match is None:
        raise ReleaseVersionError(f"unsupported Python package version: {python_version}")
    base, phase, number = match.groups()
    if phase is None:
        return base
    cargo_phase = {"a": "alpha", "b": "beta", "rc": "rc"}[phase]
    return f"{base}-{cargo_phase}.{number}"


def check_metadata() -> tuple[str, str, str]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    py_cargo = tomllib.loads((ROOT / "crates/pyagentbrowser/Cargo.toml").read_text())
    adapter = tomllib.loads((ROOT / "crates/agent-browser-adapter/Cargo.toml").read_text())
    upstream_manifest = tomllib.loads((UPSTREAM / "cli/Cargo.toml").read_text())
    upstream_metadata = json.loads((ROOT / "src/agentbrowser/_upstream.json").read_text())
    runtime_source = (ROOT / "src/agentbrowser/_version.py").read_text()

    package_version = str(project["version"])
    expected_cargo = _cargo_version(package_version)
    if py_cargo["package"]["version"] != expected_cargo:
        raise ReleaseVersionError(f"crates/pyagentbrowser version must be {expected_cargo}")
    runtime_match = re.search(r'^PACKAGE_VERSION = "([^"]+)"$', runtime_source, re.MULTILINE)
    if runtime_match is None or runtime_match.group(1) != package_version:
        raise ReleaseVersionError("src/agentbrowser/_version.py package version is not synced")

    commit = _git("rev-parse", "HEAD")
    upstream_version = str(upstream_manifest["package"]["version"])
    expected_upstream = {
        "commit": commit,
        "version": upstream_version,
    }
    if upstream_metadata != expected_upstream:
        raise ReleaseVersionError("src/agentbrowser/_upstream.json is not synced")
    if adapter["package"]["version"] != upstream_version:
        raise ReleaseVersionError(
            f"crates/agent-browser-adapter version must be {upstream_version}"
        )
    return package_version, upstream_version, commit


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify independent SDK versioning and embedded upstream provenance."
    )
    parser.add_argument("--check", action="store_true", help="verify release metadata")
    parser.parse_args()
    try:
        package_version, upstream_version, commit = check_metadata()
    except (ReleaseVersionError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        return 1
    print(
        f"verified pyagentbrowser {package_version} with "
        f"agent-browser {upstream_version} ({commit})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
