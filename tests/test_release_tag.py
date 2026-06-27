from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def package_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', text, re.MULTILINE)
    assert match
    return match.group(1)


def run_release_tag_check(tag: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["./scripts/release.sh", "check-version", tag],
        check=False,
        text=True,
        capture_output=True,
    )


@pytest.mark.packaging
def test_release_tag_check_accepts_current_package_version():
    version = package_version()
    result = run_release_tag_check(f"v{version}")

    assert result.returncode == 0
    assert f"Verified pyagentbrowser {version}" in result.stdout


@pytest.mark.packaging
def test_release_tag_check_rejects_mismatched_version():
    version = package_version()
    result = run_release_tag_check("v0.0.0")

    assert result.returncode == 1
    assert f"Package version {version} does not match release tag v0.0.0" in result.stderr
