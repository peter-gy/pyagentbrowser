from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
UPSTREAM = ROOT / "third_party/agent-browser"
pytestmark = pytest.mark.packaging


def run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "scripts.check_upstream", *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=660,
        check=False,
    )


def live_state() -> tuple[dict[str, str], str, str]:
    paths = (
        "Cargo.toml",
        "Cargo.lock",
        "crates/agent-browser-adapter/Cargo.toml",
        "src/agentbrowser/_upstream.json",
    )
    hashes = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths}
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=UPSTREAM, text=True)
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=UPSTREAM, text=True)
    return hashes, head, status


@pytest.mark.timeout(720)
def test_pinned_candidate_audits_and_compiles_with_live_state_preserved(tmp_path: Path) -> None:
    before = live_state()
    output = tmp_path / "audit"
    result = run_cli("--ref", "HEAD", "--compile", "--output", str(output))
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["success"]
    assert report["generation"]["success"]
    assert report["compilation"] == {"requested": True, "success": True}
    assert report["source"]["commit"] == before[1].strip()
    assert report["review_required"] == []
    assert json.loads((output / "report.json").read_text()) == report
    assert live_state() == before


def test_source_drift_reports_failed_transformation(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate"
    shutil.copytree(UPSTREAM / "cli", candidate / "cli")
    browser = candidate / "cli/src/native/browser.rs"
    browser.write_text(
        browser.read_text().replace('"targetId": p.target_id', '"pageId": p.target_id')
    )
    before = live_state()
    result = run_cli("--source", str(candidate))
    assert result.returncode == 1, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["success"] is False
    assert report["generation"]["success"] is False
    assert "target id contract changed" in report["generation"]["error"]
    assert "cli/src/native/browser.rs" in report["changes"]["modules"]["changed"]
    assert live_state() == before


@pytest.mark.parametrize("kind", ["dependencies", "modules", "generator"])
def test_upstream_inputs_require_explicit_review(tmp_path: Path, kind: str) -> None:
    candidate = tmp_path / "candidate"
    shutil.copytree(UPSTREAM / "cli", candidate / "cli")
    if kind == "dependencies":
        manifest = candidate / "cli/Cargo.toml"
        manifest.write_text(
            manifest.read_text().replace('serde_json = "1.0"', 'serde_json = "2.0"')
        )
    elif kind == "modules":
        (candidate / "cli/src/native/inspector.rs").write_text("pub fn inspect() {}\n")
    else:
        build = candidate / "cli/build.rs"
        build.write_text(build.read_text() + "\nconst PROTOCOL_VERSION: u32 = 2;\n")
    result = run_cli("--source", str(candidate))
    assert result.returncode == 1, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["generation"]["success"] is (kind != "generator")
    assert report["success"] is False
    assert report["review_required"] == [kind]


def test_existing_report_directory_is_rejected_before_writing(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    report.write_text("keep this result")
    result = run_cli("--ref", "HEAD", "--output", str(tmp_path))
    assert result.returncode == 2
    assert result.stdout == ""
    assert "--output must name a new directory" in result.stderr
    assert report.read_text() == "keep this result"


@pytest.mark.parametrize("setting", ["features", "edition", "rust-version"])
def test_upstream_manifest_configuration_requires_review(tmp_path: Path, setting: str) -> None:
    candidate = tmp_path / "candidate"
    shutil.copytree(UPSTREAM / "cli", candidate / "cli")
    manifest = candidate / "cli/Cargo.toml"
    contents = manifest.read_text()
    if setting == "features":
        contents += '\n[features]\ndefault = ["new-engine"]\nnew-engine = []\n'
    elif setting == "edition":
        contents = contents.replace('edition = "2021"', 'edition = "2024"')
    else:
        contents = contents.replace("[package]", '[package]\nrust-version = "1.99"')
    manifest.write_text(contents)
    result = run_cli("--source", str(candidate))
    assert result.returncode == 1, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["generation"]["success"] is True
    assert report["success"] is False
    assert report["review_required"] == ["configuration"]
    changes = report["changes"]["configuration"]
    if setting == "features":
        assert changes["changed"]["features"]["after"] == {
            "default": ["new-engine"],
            "new-engine": [],
        }
    elif setting == "edition":
        assert changes["changed"]["package.edition"]["after"] == "2024"
    else:
        assert changes["added"]["package.rust-version"] == "1.99"


def test_checkout_line_endings_preserve_source_compatibility(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate"
    shutil.copytree(UPSTREAM / "cli", candidate / "cli")
    for relative in ("cli/build.rs", "cli/src/native/browser.rs"):
        path = candidate / relative
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    result = run_cli("--source", str(candidate))
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["generation"]["success"] is True
    assert report["review_required"] == []
