from __future__ import annotations

import importlib.util
import tarfile
import zipfile
from collections.abc import Set as AbstractSet
from io import BytesIO
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

from scripts import package_smoke

pytestmark = pytest.mark.packaging

PROJECT = package_smoke.project_metadata()
PROJECT_VERSION = str(PROJECT["version"])
PROJECT_CLASSIFIERS = cast(list[str], PROJECT["classifiers"])
ROOT = Path(__file__).resolve().parents[1]
VERIFY_INSTALL = ROOT / "scripts/verify-install-artifacts.py"
WHEEL_PAYLOAD = package_smoke.WHEEL_REQUIRED_FILES
SDIST_BUILD_PAYLOAD = package_smoke.SDIST_REQUIRED_BUILD_FILES
SDIST_DOCS_AND_EXAMPLES = package_smoke.SDIST_REQUIRED_DOCS_AND_EXAMPLES
SDIST_UPSTREAM_PAYLOAD = package_smoke.SDIST_REQUIRED_UPSTREAM_SOURCE


def _artifact(name: str) -> str:
    return name.format(version=PROJECT_VERSION)


def _metadata(*, exclude_classifiers: set[str] | None = None) -> str:
    exclude_classifiers = set(exclude_classifiers or ())
    lines = [
        "Metadata-Version: 2.4",
        "Name: pyagentbrowser",
        f"Version: {PROJECT_VERSION}",
        f"Summary: {PROJECT['description']}",
        f"Requires-Python: {PROJECT['requires-python']}",
    ]
    classifiers = PROJECT["classifiers"]
    assert isinstance(classifiers, list)
    for classifier in classifiers:
        if classifier not in exclude_classifiers:
            lines.append(f"Classifier: {classifier}")
    optional_dependencies = cast(dict[str, list[str]], PROJECT["optional-dependencies"])
    for extra in sorted(optional_dependencies):
        lines.append(f"Provides-Extra: {extra}")
    urls = PROJECT["urls"]
    assert isinstance(urls, dict)
    for label, url in urls.items():
        lines.append(f"Project-URL: {label}, {url}")
    return "\n".join([*lines, "", Path(str(PROJECT["readme"])).read_text()])


def _metadata_with_requires_python(value: str) -> str:
    return "\n".join(
        f"Requires-Python: {value}" if line.startswith("Requires-Python: ") else line
        for line in _metadata().splitlines()
    )


def _metadata_with_provides_extras(extras: tuple[str, ...]) -> str:
    lines = [line for line in _metadata().splitlines() if not line.startswith("Provides-Extra: ")]
    summary_index = next(index for index, line in enumerate(lines) if line.startswith("Summary: "))
    return "\n".join(
        [
            *lines[: summary_index + 1],
            *(f"Provides-Extra: {extra}" for extra in extras),
            *lines[summary_index + 1 :],
        ]
    )


def _write_wheel(
    path: Path,
    names: AbstractSet[str],
    *,
    empty: set[str] | None = None,
    metadata: str | None = None,
    native_extensions: dict[str, bytes] | None = None,
) -> None:
    empty = set(empty or ())
    native_extensions = native_extensions or {"agentbrowser/_native.abi3.so": b"native extension"}
    with zipfile.ZipFile(path, "w") as archive:
        for name in sorted(names):
            if name == "agentbrowser/py.typed" or name in empty:
                archive.writestr(name, "")
            elif name.endswith((".py", ".pyi")):
                archive.writestr(name, "# synthetic Python module\n")
            else:
                archive.writestr(name, "")
        archive.writestr(
            f"pyagentbrowser-{PROJECT_VERSION}.dist-info/METADATA", metadata or _metadata()
        )
        for name, data in native_extensions.items():
            archive.writestr(name, data)


def _write_sdist(path: Path, names: AbstractSet[str], *, metadata: str | None = None) -> None:
    with tarfile.open(path, "w:gz") as archive:
        for name in sorted(set(names) | {"PKG-INFO"}):
            data = (metadata or _metadata()).encode() if name == "PKG-INFO" else b""
            info = tarfile.TarInfo(f"pyagentbrowser-{PROJECT_VERSION}/{name}")
            info.size = len(data)
            archive.addfile(info, BytesIO(data))


def _load_verify_install_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("verify_install_artifacts", VERIFY_INSTALL)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_install_verifier_selects_python_311_abi3_wheel_for_newer_python(
    tmp_path: Path,
) -> None:
    verifier = _load_verify_install_module()
    wheel = tmp_path / _artifact("pyagentbrowser-{version}-cp311-abi3-macosx_11_0_arm64.whl")
    wheel.write_bytes(b"wheel")

    assert verifier.wheel_for_version(tmp_path, "3.11") == wheel
    assert verifier.wheel_for_version(tmp_path, "3.14") == wheel


def test_install_verifier_rejects_abi3_wheel_below_its_python_floor(
    tmp_path: Path,
) -> None:
    verifier = _load_verify_install_module()
    wheel = tmp_path / _artifact("pyagentbrowser-{version}-cp311-abi3-macosx_11_0_arm64.whl")
    wheel.write_bytes(b"wheel")
    python_major = 3
    python_floor_minor = 11

    with pytest.raises(RuntimeError, match="compatible abi3 wheel"):
        verifier.wheel_for_version(tmp_path, f"{python_major}.{python_floor_minor - 1}")


def test_wheel_smoke_accepts_required_runtime_payload(tmp_path: Path) -> None:
    wheel = tmp_path / _artifact("pyagentbrowser-{version}-cp311-abi3-macosx_11_0_arm64.whl")
    _write_wheel(wheel, WHEEL_PAYLOAD)

    package_smoke.check_wheel(wheel)


def test_wheel_smoke_rejects_support_junk(tmp_path: Path) -> None:
    wheel = tmp_path / _artifact("pyagentbrowser-{version}-cp311-abi3-macosx_11_0_arm64.whl")
    _write_wheel(wheel, WHEEL_PAYLOAD | {"docs/figures/figure.png"})

    with pytest.raises(package_smoke.PackageSmokeError, match="forbidden payload"):
        package_smoke.check_wheel(wheel)


def test_wheel_smoke_rejects_empty_python_modules(tmp_path: Path) -> None:
    wheel = tmp_path / _artifact("pyagentbrowser-{version}-cp311-abi3-macosx_11_0_arm64.whl")
    _write_wheel(
        wheel,
        WHEEL_PAYLOAD,
        empty={"agentbrowser/browser.py"},
    )

    with pytest.raises(package_smoke.PackageSmokeError, match="empty Python modules"):
        package_smoke.check_wheel(wheel)


def test_wheel_smoke_rejects_distribution_name_as_import_package(tmp_path: Path) -> None:
    wheel = tmp_path / _artifact("pyagentbrowser-{version}-cp311-abi3-macosx_11_0_arm64.whl")
    _write_wheel(wheel, WHEEL_PAYLOAD | {"pyagentbrowser/__init__.py"})

    with pytest.raises(package_smoke.PackageSmokeError, match="forbidden payload"):
        package_smoke.check_wheel(wheel)


@pytest.mark.parametrize("payload", ["agentbrowser.py", "pyagentbrowser.py"])
def test_wheel_smoke_rejects_module_payload(tmp_path: Path, payload: str) -> None:
    wheel = tmp_path / _artifact("pyagentbrowser-{version}-cp311-abi3-macosx_11_0_arm64.whl")
    _write_wheel(wheel, WHEEL_PAYLOAD | {payload})

    with pytest.raises(package_smoke.PackageSmokeError, match="forbidden payload"):
        package_smoke.check_wheel(wheel)


def test_wheel_smoke_rejects_empty_native_extension(tmp_path: Path) -> None:
    wheel = tmp_path / _artifact("pyagentbrowser-{version}-cp311-abi3-macosx_11_0_arm64.whl")
    _write_wheel(
        wheel,
        WHEEL_PAYLOAD,
        native_extensions={"agentbrowser/_native.abi3.so": b""},
    )

    with pytest.raises(package_smoke.PackageSmokeError, match="empty native extension"):
        package_smoke.check_wheel(wheel)


def test_wheel_smoke_rejects_multiple_native_extensions(tmp_path: Path) -> None:
    wheel = tmp_path / _artifact("pyagentbrowser-{version}-cp311-abi3-macosx_11_0_arm64.whl")
    _write_wheel(
        wheel,
        WHEEL_PAYLOAD,
        native_extensions={
            "agentbrowser/_native.abi3.so": b"native extension",
            "agentbrowser/_native.cpython-313-darwin.so": b"native extension",
        },
    )

    with pytest.raises(package_smoke.PackageSmokeError, match="multiple native extensions"):
        package_smoke.check_wheel(wheel)


def test_wheel_smoke_rejects_native_extension_tag_mismatch(tmp_path: Path) -> None:
    wheel = tmp_path / _artifact("pyagentbrowser-{version}-cp311-abi3-macosx_11_0_arm64.whl")
    _write_wheel(
        wheel,
        WHEEL_PAYLOAD,
        native_extensions={"agentbrowser/_native.cpython-313-darwin.so": b"native extension"},
    )

    with pytest.raises(package_smoke.PackageSmokeError, match="wheel Python tag"):
        package_smoke.check_wheel(wheel)


@pytest.mark.parametrize("missing", sorted(WHEEL_PAYLOAD))
def test_wheel_smoke_rejects_missing_required_runtime_file(
    tmp_path: Path,
    missing: str,
) -> None:
    wheel = tmp_path / _artifact("pyagentbrowser-{version}-cp311-abi3-macosx_11_0_arm64.whl")
    _write_wheel(wheel, WHEEL_PAYLOAD - {missing})

    with pytest.raises(package_smoke.PackageSmokeError, match="wheel missing required files"):
        package_smoke.check_wheel(wheel)


def test_sdist_smoke_accepts_required_categories(tmp_path: Path) -> None:
    sdist = tmp_path / _artifact("pyagentbrowser-{version}.tar.gz")
    names = SDIST_BUILD_PAYLOAD | SDIST_DOCS_AND_EXAMPLES | SDIST_UPSTREAM_PAYLOAD
    _write_sdist(sdist, names)

    package_smoke.check_sdist(sdist)


@pytest.mark.parametrize(
    "payload",
    ["src/pyagentbrowser/__init__.py", "src/pyagentbrowser.py", "pyagentbrowser/__init__.py"],
)
def test_sdist_smoke_rejects_distribution_name_as_import_payload(
    tmp_path: Path,
    payload: str,
) -> None:
    sdist = tmp_path / _artifact("pyagentbrowser-{version}.tar.gz")
    names = SDIST_BUILD_PAYLOAD | SDIST_DOCS_AND_EXAMPLES | SDIST_UPSTREAM_PAYLOAD | {payload}
    _write_sdist(sdist, names)

    with pytest.raises(package_smoke.PackageSmokeError, match="forbidden import payload"):
        package_smoke.check_sdist(sdist)


@pytest.mark.parametrize(
    ("missing", "error_pattern"),
    [
        *[(missing, "sdist build payload") for missing in sorted(SDIST_BUILD_PAYLOAD)],
        *[(missing, "sdist docs/examples payload") for missing in sorted(SDIST_DOCS_AND_EXAMPLES)],
        *[(missing, "sdist upstream payload") for missing in sorted(SDIST_UPSTREAM_PAYLOAD)],
    ],
)
def test_sdist_smoke_rejects_each_missing_required_file(
    tmp_path: Path,
    missing: str,
    error_pattern: str,
) -> None:
    all_names = SDIST_BUILD_PAYLOAD | SDIST_DOCS_AND_EXAMPLES | SDIST_UPSTREAM_PAYLOAD
    sdist = tmp_path / _artifact("pyagentbrowser-{version}.tar.gz")
    _write_sdist(sdist, all_names - {missing})

    with pytest.raises(package_smoke.PackageSmokeError, match=error_pattern):
        package_smoke.check_sdist(sdist)


def test_sdist_smoke_rejects_upstream_dashboard_payload(tmp_path: Path) -> None:
    sdist = tmp_path / _artifact("pyagentbrowser-{version}.tar.gz")
    names = (
        SDIST_BUILD_PAYLOAD
        | SDIST_DOCS_AND_EXAMPLES
        | SDIST_UPSTREAM_PAYLOAD
        | {"third_party/agent-browser/packages/dashboard/index.ts"}
    )
    _write_sdist(sdist, names)

    with pytest.raises(package_smoke.PackageSmokeError, match="dashboard/assets/docs"):
        package_smoke.check_sdist(sdist)


def test_install_verifier_uses_temp_copy_for_local_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    verifier = _load_verify_install_module()
    source_dir = tmp_path / "dist"
    source_dir.mkdir()
    source = source_dir / _artifact("pyagentbrowser-{version}.tar.gz")
    source.write_bytes(b"sdist")
    seen: list[tuple[Path, dict[str, object]]] = []

    def create_clean_venv(root: Path, python_version: str) -> None:
        assert python_version == python_version_under_test
        bin_dir = root / "bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "python").write_text("")

    def pip_install(python: Path, artifact: Path, **kwargs: object) -> None:
        assert python.exists()
        assert artifact.name == source.name
        assert artifact.parent != source.parent
        assert artifact.exists()
        seen.append((artifact, kwargs))
        artifact.unlink()

    monkeypatch.setattr(verifier, "create_clean_venv", create_clean_venv)
    monkeypatch.setattr(verifier, "pip_install", pip_install)
    monkeypatch.setattr(verifier.subprocess, "check_call", lambda command: None)

    python_version_under_test = "sentinel-python-version"
    verifier.verify_install(
        source,
        python_version=python_version_under_test,
        no_binary=True,
        check_extras=False,
    )

    assert source.exists()
    assert len(seen) == 1
    assert seen[0][1]["no_binary"] is True


def test_install_verifier_installs_advertised_extras(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    verifier = _load_verify_install_module()
    source = tmp_path / _artifact("pyagentbrowser-{version}-cp311-abi3-macosx_11_0_arm64.whl")
    advertised_extras = ("synthetic-browser",)
    _write_wheel(
        source,
        WHEEL_PAYLOAD,
        metadata=_metadata_with_provides_extras(advertised_extras),
    )
    installs: list[dict[str, object]] = []

    def create_clean_venv(root: Path, python_version: str) -> None:
        del python_version
        bin_dir = root / "bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "python").write_text("")

    def pip_install(python: Path, artifact: Path, **kwargs: object) -> None:
        assert python.exists()
        assert artifact.exists()
        installs.append(kwargs)

    monkeypatch.setattr(verifier, "create_clean_venv", create_clean_venv)
    monkeypatch.setattr(verifier, "pip_install", pip_install)
    monkeypatch.setattr(verifier.subprocess, "check_call", lambda command: None)

    verifier.verify_install(source, python_version="sentinel-python-version")

    assert installs[0].get("extras", ()) == ()
    assert installs[1]["extras"] == advertised_extras


@pytest.mark.parametrize(
    "missing_classifier",
    [str(classifier) for classifier in PROJECT_CLASSIFIERS],
)
@pytest.mark.parametrize("artifact_kind", ["wheel", "sdist"])
def test_metadata_smoke_requires_project_classifiers(
    tmp_path: Path,
    artifact_kind: str,
    missing_classifier: str,
) -> None:
    metadata = _metadata(exclude_classifiers={missing_classifier})
    names = SDIST_BUILD_PAYLOAD | SDIST_DOCS_AND_EXAMPLES | SDIST_UPSTREAM_PAYLOAD

    if artifact_kind == "wheel":
        artifact = tmp_path / _artifact("pyagentbrowser-{version}-cp311-abi3-macosx_11_0_arm64.whl")
        _write_wheel(artifact, WHEEL_PAYLOAD, metadata=metadata)
        check = package_smoke.check_wheel
    else:
        artifact = tmp_path / _artifact("pyagentbrowser-{version}.tar.gz")
        _write_sdist(artifact, names, metadata=metadata)
        check = package_smoke.check_sdist

    with pytest.raises(package_smoke.PackageSmokeError, match="missing classifiers"):
        check(artifact)


def test_metadata_smoke_rejects_filename_version_drift(tmp_path: Path) -> None:
    bad_version = "0.0.0" if PROJECT_VERSION != "0.0.0" else "0.0.1"
    wheel = tmp_path / f"pyagentbrowser-{bad_version}-cp311-abi3-macosx_11_0_arm64.whl"
    _write_wheel(wheel, WHEEL_PAYLOAD)

    with pytest.raises(package_smoke.PackageSmokeError, match="filename version"):
        package_smoke.check_wheel(wheel)


def test_metadata_smoke_accepts_requires_python_spacing_normalization(tmp_path: Path) -> None:
    wheel = tmp_path / _artifact("pyagentbrowser-{version}-cp311-abi3-macosx_11_0_arm64.whl")
    requires_python = str(PROJECT["requires-python"])
    metadata = _metadata_with_requires_python(requires_python.replace(",", ", "))
    _write_wheel(wheel, WHEEL_PAYLOAD, metadata=metadata)

    package_smoke.check_wheel(wheel)


def test_metadata_smoke_rejects_project_url_drift(tmp_path: Path) -> None:
    urls = cast(dict[str, Any], PROJECT["urls"])
    label, url = next(iter(urls.items()))
    metadata = _metadata().replace(
        f"Project-URL: {label}, {url}",
        f"Project-URL: {label}, https://example.com/repo",
    )
    wheel = tmp_path / _artifact("pyagentbrowser-{version}-cp311-abi3-macosx_11_0_arm64.whl")
    _write_wheel(wheel, WHEEL_PAYLOAD, metadata=metadata)

    with pytest.raises(package_smoke.PackageSmokeError, match="Project-URL pairs"):
        package_smoke.check_wheel(wheel)


def test_metadata_smoke_rejects_readme_description_drift(tmp_path: Path) -> None:
    headers, _description = _metadata().split("\n\n", 1)
    metadata = f"{headers}\n\n# pyagentbrowser\n"
    sdist = tmp_path / _artifact("pyagentbrowser-{version}.tar.gz")
    names = SDIST_BUILD_PAYLOAD | SDIST_DOCS_AND_EXAMPLES | SDIST_UPSTREAM_PAYLOAD
    _write_sdist(sdist, names, metadata=metadata)

    with pytest.raises(package_smoke.PackageSmokeError, match="long description"):
        package_smoke.check_sdist(sdist)
