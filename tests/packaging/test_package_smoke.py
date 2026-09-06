from __future__ import annotations

import importlib.util
import io
import tarfile
import zipfile
from pathlib import Path
from types import ModuleType

import agent_plugins
import pytest

import _agent_plugins_maturin as agent_plugin_backend
from scripts import package_smoke

pytestmark = pytest.mark.packaging
ROOT = Path(__file__).resolve().parents[2]
VERIFY_INSTALL = ROOT / "scripts/verify-install-artifacts.py"


def _load_verifier() -> ModuleType:
    spec = importlib.util.spec_from_file_location("verify_install_artifacts", VERIFY_INSTALL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_install_verifier_selects_a_compatible_abi3_wheel(tmp_path: Path) -> None:
    verifier = _load_verifier()
    wheel = tmp_path / "pyagentbrowser-1.0.0-cp311-abi3-macosx_11_0_arm64.whl"
    wheel.write_bytes(b"wheel")

    assert verifier.wheel_for_version(tmp_path, "3.14") == wheel


def test_install_verifier_rejects_abi3_below_its_python_floor(tmp_path: Path) -> None:
    verifier = _load_verifier()
    (tmp_path / "pyagentbrowser-1.0.0-cp312-abi3-macosx_11_0_arm64.whl").write_bytes(b"wheel")

    with pytest.raises(RuntimeError, match="compatible abi3 wheel"):
        verifier.wheel_for_version(tmp_path, "3.11")


@pytest.mark.parametrize(
    ("native_extension", "artifact_name"),
    [
        (
            "agentbrowser/_native.abi3.so",
            "pyagentbrowser-1.0.0-cp311-abi3-macosx_11_0_arm64.whl",
        ),
        ("agentbrowser/_native.pyd", "pyagentbrowser-1.0.0-cp311-abi3-win_amd64.whl"),
    ],
)
def test_wheel_payload_checks_runtime_anchors_and_one_native_extension(
    native_extension: str,
    artifact_name: str,
) -> None:
    names = {
        "agentbrowser/__init__.py",
        "agentbrowser/_upstream.json",
        "agentbrowser/py.typed",
        native_extension,
        "agentbrowser/_native.pyi",
    }
    sizes = {name: 1 for name in names}

    package_smoke.assert_wheel_runtime_payload(
        names,
        sizes,
        artifact_name,
    )


@pytest.mark.parametrize(
    "native_extensions,match",
    [
        ({}, "missing native extension"),
        (
            {
                "agentbrowser/_native.abi3.so": 1,
                "agentbrowser/_native.cp311.so": 1,
            },
            "multiple native extensions",
        ),
        ({"agentbrowser/_native.abi3.so": 0}, "empty native extension"),
    ],
)
def test_wheel_payload_rejects_invalid_native_boundaries(
    native_extensions: dict[str, int],
    match: str,
) -> None:
    names = {
        "agentbrowser/__init__.py",
        "agentbrowser/_upstream.json",
        "agentbrowser/py.typed",
        *native_extensions,
    }
    sizes = {name: 1 for name in names}
    sizes.update(native_extensions)

    with pytest.raises(package_smoke.PackageSmokeError, match=match):
        package_smoke.assert_wheel_runtime_payload(
            names,
            sizes,
            "pyagentbrowser-1.0.0-cp311-abi3-macosx_11_0_arm64.whl",
        )


def test_wheel_rejects_source_and_development_payloads() -> None:
    with pytest.raises(package_smoke.PackageSmokeError, match="forbidden payload"):
        package_smoke.assert_wheel_excludes_source_and_junk(
            {"agentbrowser/__init__.py", "tests/test_runtime.py"}
        )


def test_wheel_rejects_empty_python_modules() -> None:
    with pytest.raises(package_smoke.PackageSmokeError, match="empty Python modules"):
        package_smoke.assert_wheel_python_modules_are_nonempty(
            {"agentbrowser/__init__.py": 0, "agentbrowser/py.typed": 0}
        )


@pytest.mark.parametrize(
    "leaked_path",
    [str(ROOT).encode(), b"/io/crates/pyagentbrowser/src/lib.rs"],
)
def test_native_artifact_scan_rejects_build_paths(
    tmp_path: Path,
    leaked_path: bytes,
) -> None:
    wheel = tmp_path / "pyagentbrowser-1.0.0-cp311-abi3-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("agentbrowser/_native.abi3.so", leaked_path)

    with pytest.raises(package_smoke.PackageSmokeError, match="local build paths"):
        package_smoke.assert_native_extension_excludes_local_build_paths(wheel)


def test_native_artifact_scan_allows_dependency_io_modules(tmp_path: Path) -> None:
    wheel = tmp_path / "pyagentbrowser-1.0.0-cp311-abi3-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(
            "agentbrowser/_native.abi3.so",
            b"/cargo/registry/src/tokio/src/io/registration.rs",
        )

    package_smoke.assert_native_extension_excludes_local_build_paths(wheel)


def test_cross_platform_wheel_step_attaches_the_complete_agent_plugin(tmp_path: Path) -> None:
    wheel = tmp_path / "pyagentbrowser-0.36.0-cp311-abi3-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("pyagentbrowser-0.36.0.dist-info/WHEEL", "Wheel-Version: 1.0\n")
        archive.writestr(
            "pyagentbrowser-0.36.0.dist-info/METADATA",
            "Metadata-Version: 2.4\nName: pyagentbrowser\nVersion: 0.36.0\n",
        )
        archive.writestr("pyagentbrowser-0.36.0.dist-info/RECORD", "")

    attachment = agent_plugins.attach_wheel(wheel, project=ROOT)
    names = package_smoke.wheel_names(wheel)

    assert attachment.output == wheel.resolve()
    assert attachment.plugin_root.as_posix() == "pyagentbrowser-0.36.0.agent-plugin"
    assert {path.as_posix() for path in attachment.files} == set(package_smoke.AGENT_PLUGIN_FILES)
    assert attachment.replaced_existing_plugin is False
    assert attachment.removed_signatures == ()
    package_smoke.assert_wheel_agent_plugin(wheel, names)
    package_smoke.assert_wheel_record(wheel)
    assert "pyagentbrowser-0.36.0.dist-info/agent_plugins.json" in names


def test_agent_plugin_build_plan_contains_only_authored_resources() -> None:
    plan = agent_plugins.build_plan(ROOT)

    assert plan.root == ROOT
    assert {mapping.target.as_posix() for mapping in plan.files} == set(
        package_smoke.AGENT_PLUGIN_FILES
    )


def test_sdist_agent_plugin_check_rejects_an_incomplete_inventory() -> None:
    with pytest.raises(package_smoke.PackageSmokeError, match="payload drifted"):
        package_smoke.assert_sdist_agent_plugin(
            {".agent-plugin/plugin.json", ".agent-plugin/skills/pyagentbrowser/SKILL.md"}
        )


def test_agent_plugin_backend_preserves_maturin_metadata_hooks() -> None:
    assert callable(agent_plugin_backend.prepare_metadata_for_build_wheel)
    assert callable(agent_plugin_backend.prepare_metadata_for_build_editable)


def test_agent_plugin_backend_normalizes_sdist_member_timestamps(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdist = tmp_path / "pyagentbrowser-1.0.0.tar.gz"
    content = b"content"
    with tarfile.open(sdist, "w:gz") as archive:
        member = tarfile.TarInfo("pyagentbrowser-1.0.0/plugin.json")
        member.size = len(content)
        member.mtime = 123
        archive.addfile(member, io.BytesIO(content))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "456")

    agent_plugin_backend._normalize_sdist(sdist)

    with tarfile.open(sdist) as archive:
        members = archive.getmembers()
        assert [member.mtime for member in members] == [456]
        extracted = archive.extractfile(members[0])
        assert extracted is not None
        assert extracted.read() == content


def test_sdist_rejects_ci_and_upstream_support_payloads() -> None:
    for forbidden in (
        ".github/workflows/release.yml",
        "third_party/agent-browser/docs/internal.md",
    ):
        with pytest.raises(package_smoke.PackageSmokeError):
            package_smoke.assert_sdist_excludes_junk_and_dashboard_payload({forbidden})


@pytest.mark.parametrize("version", ["0.32.0", "0.32.0a1", "0.32.0b1", "0.32.0rc1"])
def test_package_gate_accepts_supported_release_versions(version: str) -> None:
    package_smoke._assert_release_version(version, "artifact")
