from __future__ import annotations

import re
import sys
import tarfile
import tomllib
import zipfile
from collections.abc import Iterable, Mapping
from email.message import Message
from email.parser import Parser
from pathlib import Path
from typing import NoReturn


class PackageSmokeError(AssertionError):
    pass


ROOT = Path(__file__).resolve().parents[1]


def _relative_files(base: str, suffixes: tuple[str, ...] | None = None) -> frozenset[str]:
    root = ROOT / base
    if not root.exists():
        return frozenset()
    return frozenset(
        path.relative_to(ROOT).as_posix()
        for path in root.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and (suffixes is None or path.name == "py.typed" or path.suffix in suffixes)
    )


def _wheel_runtime_files() -> frozenset[str]:
    return frozenset(
        path.removeprefix("src/") for path in _relative_files("src/agentbrowser", (".py", ".pyi"))
    )


def _docs_and_example_files() -> frozenset[str]:
    return _relative_files("docs", (".md", ".json")) | _relative_files("examples", (".py",))


def _sdk_source_files() -> frozenset[str]:
    return _relative_files("src/agentbrowser", (".py", ".pyi"))


def _upstream_skill_data_files() -> frozenset[str]:
    return _relative_files("third_party/agent-browser/skill-data")


WHEEL_REQUIRED_FILES = _wheel_runtime_files()
WHEEL_REQUIRED_PYTHON_MODULES = frozenset(
    name for name in WHEEL_REQUIRED_FILES if name.endswith((".py", ".pyi"))
)
WHEEL_FORBIDDEN_EXACT = frozenset(
    {
        "agentbrowser/cli.py",
        "agentbrowser/__main__.py",
        "agentbrowser/upstream.py",
        "agentbrowser.py",
        "agentbrowser.pyi",
        "pyagentbrowser.py",
        "pyagentbrowser.pyi",
        "Cargo.lock",
        "rust-toolchain.toml",
    }
)
WHEEL_FORBIDDEN_PREFIXES = (
    "agentbrowser/_skill_data/",
    "pyagentbrowser/",
    "third_party/",
    "crates/",
    "docs/figures/",
    "target/",
    "tests/",
    "examples/",
)

SDIST_REQUIRED_BUILD_FILES = (
    frozenset(
        {
            "pyproject.toml",
            "LICENSE",
            "NOTICE",
            "Cargo.toml",
            "Cargo.lock",
            "rust-toolchain.toml",
            "crates/pyagentbrowser/Cargo.toml",
            "crates/pyagentbrowser/build.rs",
            "crates/pyagentbrowser/src/lib.rs",
            "crates/agent-browser-adapter/Cargo.toml",
            "crates/agent-browser-adapter/build.rs",
            "crates/agent-browser-adapter/src/lib.rs",
            "crates/agent-browser-adapter/tests/smoke.rs",
        }
    )
    | _sdk_source_files()
)
SDIST_REQUIRED_DOCS_AND_EXAMPLES = _docs_and_example_files()
SDIST_REQUIRED_UPSTREAM_SOURCE = (
    frozenset(
        {
            "third_party/agent-browser/LICENSE",
            "third_party/agent-browser/cli/Cargo.toml",
            "third_party/agent-browser/cli/src/commands.rs",
            "third_party/agent-browser/cli/src/plugins.rs",
            "third_party/agent-browser/cli/src/read.rs",
            "third_party/agent-browser/cli/src/native/actions.rs",
            "third_party/agent-browser/cli/src/native/stream/http.rs",
            "third_party/agent-browser/cli/src/native/stream/mod.rs",
            "third_party/agent-browser/cli/cdp-protocol/browser_protocol.json",
            "third_party/agent-browser/cli/cdp-protocol/js_protocol.json",
        }
    )
    | _upstream_skill_data_files()
)

ALLOWED_UPSTREAM_ROOTS = frozenset(
    {
        "third_party/agent-browser",
        "third_party/agent-browser/cli",
        "third_party/agent-browser/cli/cdp-protocol",
        "third_party/agent-browser/cli/src",
        "third_party/agent-browser/cli/src/native",
        "third_party/agent-browser/skill-data",
    }
)
ALLOWED_UPSTREAM_EXACT = frozenset(
    {
        "third_party/agent-browser/LICENSE",
        "third_party/agent-browser/cli/Cargo.toml",
        "third_party/agent-browser/cli/src/color.rs",
        "third_party/agent-browser/cli/src/commands.rs",
        "third_party/agent-browser/cli/src/connection.rs",
        "third_party/agent-browser/cli/src/flags.rs",
        "third_party/agent-browser/cli/src/install.rs",
        "third_party/agent-browser/cli/src/plugins.rs",
        "third_party/agent-browser/cli/src/read.rs",
        "third_party/agent-browser/cli/src/native/actions.rs",
        "third_party/agent-browser/cli/src/native/auth.rs",
        "third_party/agent-browser/cli/src/native/browser.rs",
        "third_party/agent-browser/cli/src/native/cookies.rs",
        "third_party/agent-browser/cli/src/native/diff.rs",
        "third_party/agent-browser/cli/src/native/element.rs",
        "third_party/agent-browser/cli/src/native/inspect_server.rs",
        "third_party/agent-browser/cli/src/native/interaction.rs",
        "third_party/agent-browser/cli/src/native/network.rs",
        "third_party/agent-browser/cli/src/native/policy.rs",
        "third_party/agent-browser/cli/src/native/providers.rs",
        "third_party/agent-browser/cli/src/native/recording.rs",
        "third_party/agent-browser/cli/src/native/screenshot.rs",
        "third_party/agent-browser/cli/src/native/snapshot.rs",
        "third_party/agent-browser/cli/src/native/state.rs",
        "third_party/agent-browser/cli/src/native/storage.rs",
        "third_party/agent-browser/cli/src/native/tracing.rs",
        "third_party/agent-browser/cli/src/test_utils.rs",
        "third_party/agent-browser/cli/src/validation.rs",
    }
)
ALLOWED_UPSTREAM_PREFIXES = (
    "third_party/agent-browser/cli/cdp-protocol/",
    "third_party/agent-browser/cli/src/native/cdp/",
    "third_party/agent-browser/cli/src/native/react/",
    "third_party/agent-browser/cli/src/native/stream/",
    "third_party/agent-browser/cli/src/native/test_fixtures/",
    "third_party/agent-browser/cli/src/native/webdriver/",
    "third_party/agent-browser/skill-data/",
)
FORBIDDEN_SUPPORT_PREFIXES = (
    ".github/",
    "crates/agent-browser-adapter/target/",
    "docs/figures/",
    "target/",
    "tests/",
)
FORBIDDEN_SUPPORT_EXACT = frozenset(
    {
        "crates/agent-browser-adapter/Cargo.lock",
    }
)
FORBIDDEN_UPSTREAM_PREFIXES = (
    "third_party/agent-browser/.claude-plugin/",
    "third_party/agent-browser/.github/",
    "third_party/agent-browser/.husky/",
    "third_party/agent-browser/benchmarks/",
    "third_party/agent-browser/bin/",
    "third_party/agent-browser/docker/",
    "third_party/agent-browser/docs/",
    "third_party/agent-browser/evals/",
    "third_party/agent-browser/examples/",
    "third_party/agent-browser/packages/",
    "third_party/agent-browser/scripts/",
    "third_party/agent-browser/skills/",
)
FORBIDDEN_UPSTREAM_EXACT = frozenset(
    {
        "third_party/agent-browser/AGENTS.md",
        "third_party/agent-browser/CHANGELOG.md",
        "third_party/agent-browser/README.md",
        "third_party/agent-browser/agent-browser.schema.json",
        "third_party/agent-browser/package.json",
        "third_party/agent-browser/pnpm-lock.yaml",
        "third_party/agent-browser/pnpm-workspace.yaml",
    }
)


def _fail(message: str) -> NoReturn:
    raise PackageSmokeError(message)


def project_metadata() -> Mapping[str, object]:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    project = pyproject.get("project")
    if not isinstance(project, Mapping):
        _fail("pyproject.toml is missing [project]")
    return project


def wheel_names(path: Path) -> set[str]:
    with zipfile.ZipFile(path) as archive:
        return set(archive.namelist())


def wheel_file_sizes(path: Path) -> dict[str, int]:
    with zipfile.ZipFile(path) as archive:
        return {info.filename: info.file_size for info in archive.infolist()}


def sdist_names(path: Path) -> set[str]:
    with tarfile.open(path) as archive:
        return {name.split("/", 1)[1] for name in archive.getnames() if "/" in name}


def _assert_present(names: set[str], required: Iterable[str], category: str) -> None:
    missing = sorted(set(required) - names)
    if missing:
        _fail(f"{category} missing required files: {missing}")


def _is_native_extension(name: str) -> bool:
    return name.startswith("agentbrowser/_native.") and name.endswith((".so", ".pyd"))


def _native_extensions(names: set[str]) -> list[str]:
    return sorted(name for name in names if _is_native_extension(name))


def _wheel_python_and_abi_tags(artifact_name: str) -> tuple[str, str] | None:
    match = re.match(r"^pyagentbrowser-[^-]+-(cp\d+)-([^-]+)-", artifact_name)
    if match is None:
        return None
    return match.group(1), match.group(2)


def _native_extension_matches_wheel_tags(name: str, python_tag: str, abi_tag: str) -> bool:
    tag_digits = python_tag.removeprefix("cp")
    basename = name.rsplit("/", 1)[-1]
    if abi_tag == "abi3":
        return ".abi3." in basename or (
            basename.endswith(".pyd") and "cpython-" not in basename and ".cp" not in basename
        )
    return f"cpython-{tag_digits}" in basename or f".{python_tag}-" in basename


def _is_distribution_name_import_payload(name: str) -> bool:
    return name.startswith("pyagentbrowser/") or (
        name.startswith("pyagentbrowser.") and name.endswith((".py", ".pyi", ".so", ".pyd"))
    )


def _is_distribution_name_source_payload(name: str) -> bool:
    return name.startswith("src/pyagentbrowser/") or (
        name.startswith("src/pyagentbrowser.") and name.endswith((".py", ".pyi", ".so", ".pyd"))
    )


def assert_wheel_runtime_payload(
    names: set[str],
    sizes: Mapping[str, int],
    artifact_name: str,
) -> None:
    _assert_present(names, WHEEL_REQUIRED_FILES, "wheel")
    native_extensions = _native_extensions(names)
    if not native_extensions:
        _fail("wheel is missing native extension")
    if len(native_extensions) != 1:
        _fail(f"wheel contains multiple native extensions: {native_extensions}")
    native_extension = native_extensions[0]
    if sizes.get(native_extension, 0) <= 0:
        _fail(f"wheel contains empty native extension: {native_extension}")
    wheel_tags = _wheel_python_and_abi_tags(artifact_name)
    if wheel_tags and not _native_extension_matches_wheel_tags(native_extension, *wheel_tags):
        python_tag, abi_tag = wheel_tags
        _fail(
            f"wheel native extension {native_extension} does not match "
            f"wheel Python tag {python_tag} and ABI tag {abi_tag}"
        )


def assert_wheel_python_modules_are_nonempty(sizes: Mapping[str, int]) -> None:
    empty = sorted(name for name in WHEEL_REQUIRED_PYTHON_MODULES if sizes.get(name, 0) <= 0)
    if empty:
        _fail(f"wheel contains empty Python modules: {empty}")


def assert_wheel_excludes_source_and_junk(names: set[str]) -> None:
    for name in names:
        if (
            name in WHEEL_FORBIDDEN_EXACT
            or name.startswith(WHEEL_FORBIDDEN_PREFIXES)
            or _is_distribution_name_import_payload(name)
        ):
            _fail(f"wheel contains forbidden payload: {name}")
        if name.endswith((".pth", ".pyc", ".pyo")) or "__pycache__/" in name:
            _fail(f"wheel contains development artifact: {name}")


def _metadata_from_wheel(path: Path) -> Message:
    with zipfile.ZipFile(path) as archive:
        metadata_names = [
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_names) != 1:
            _fail(f"wheel should contain exactly one METADATA file, found {metadata_names}")
        return Parser().parsestr(archive.read(metadata_names[0]).decode("utf-8"))


def _metadata_from_sdist(path: Path) -> Message:
    with tarfile.open(path) as archive:
        pkg_info_names = [name for name in archive.getnames() if name.endswith("/PKG-INFO")]
        if len(pkg_info_names) != 1:
            _fail(f"sdist should contain exactly one PKG-INFO file, found {pkg_info_names}")
        member = archive.extractfile(pkg_info_names[0])
        if member is None:
            _fail("sdist PKG-INFO could not be read")
        return Parser().parsestr(member.read().decode("utf-8"))


def _artifact_version(artifact_name: str) -> str | None:
    wheel_match = re.match(r"^pyagentbrowser-([^-]+)-", artifact_name)
    if wheel_match:
        return wheel_match.group(1)
    sdist_match = re.match(r"^pyagentbrowser-(.+)\.tar\.gz$", artifact_name)
    if sdist_match:
        return sdist_match.group(1)
    return None


def _version_tuple(version: str) -> tuple[int, int]:
    major, minor = version.split(".", 1)
    return int(major), int(minor)


def _requires_python_allows(requires_python: str, version: str) -> bool:
    requested = _version_tuple(version)
    for clause in (part.strip() for part in requires_python.split(",")):
        if not clause:
            continue
        match = re.match(r"(>=|>|<=|<|==)\s*(\d+\.\d+)$", clause)
        if match is None:
            _fail(f"unsupported Requires-Python clause: {clause}")
        operator, boundary_text = match.groups()
        boundary = _version_tuple(boundary_text)
        if operator == ">=" and not requested >= boundary:
            return False
        if operator == ">" and not requested > boundary:
            return False
        if operator == "<=" and not requested <= boundary:
            return False
        if operator == "<" and not requested < boundary:
            return False
        if operator == "==" and requested != boundary:
            return False
    return True


def _classifier_python_versions(classifiers: Iterable[object]) -> tuple[str, ...]:
    versions = {
        match.group(1)
        for classifier in classifiers
        if (match := re.fullmatch(r"Programming Language :: Python :: (\d+\.\d+)", str(classifier)))
    }
    if not versions:
        _fail("pyproject.toml is missing Python version classifiers")
    return tuple(sorted(versions, key=_version_tuple))


def _first_rejected_python_version(requires_python: str) -> str | None:
    rejected: list[str] = []
    for clause in (part.strip() for part in requires_python.split(",")):
        if not clause:
            continue
        match = re.match(r"(<=|<)\s*(\d+\.\d+)$", clause)
        if match is None:
            continue
        operator, boundary_text = match.groups()
        if operator == "<":
            rejected.append(boundary_text)
        else:
            major, minor = _version_tuple(boundary_text)
            rejected.append(f"{major}.{minor + 1}")
    if not rejected:
        return None
    return min(rejected, key=_version_tuple)


def _normalize_requires_python(requires_python: str) -> str:
    return ",".join(part.strip() for part in requires_python.split(",") if part.strip())


def _project_url_pairs(metadata: Message) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for value in metadata.get_all("Project-URL") or []:
        if ", " not in value:
            _fail(f"metadata has malformed Project-URL: {value}")
        label, url = value.split(", ", 1)
        pairs.add((label, url))
    return pairs


def _assert_prerelease_version(version: str, artifact_name: str) -> None:
    if "+" in version:
        _fail(f"{artifact_name} uses a local version label: {version}")
    if not re.fullmatch(r"\d+\.\d+\.\d+rc\d+", version):
        _fail(f"{artifact_name} is not an rc prerelease: {version}")


def assert_metadata_invariants(metadata: Message, artifact_name: str) -> None:
    project = project_metadata()
    if metadata["Name"] != "pyagentbrowser":
        _fail(f"{artifact_name} metadata has wrong Name: {metadata['Name']}")
    project_version = str(project["version"])
    _assert_prerelease_version(project_version, artifact_name)
    artifact_version = _artifact_version(artifact_name)
    if metadata["Version"] != project_version:
        _fail(
            f"{artifact_name} metadata Version {metadata['Version']} "
            f"does not match pyproject version {project_version}"
        )
    if artifact_version != project_version:
        _fail(
            f"{artifact_name} filename version {artifact_version} "
            f"does not match pyproject version {project_version}"
        )
    requires_python = metadata["Requires-Python"]
    if _normalize_requires_python(requires_python) != _normalize_requires_python(
        str(project["requires-python"])
    ):
        _fail(f"{artifact_name} metadata has wrong Requires-Python: {metadata['Requires-Python']}")
    project_classifiers = project.get("classifiers")
    if not isinstance(project_classifiers, list):
        _fail("pyproject.toml is missing project classifiers")
    for python_version in _classifier_python_versions(project_classifiers):
        if not _requires_python_allows(requires_python, python_version):
            _fail(f"{artifact_name} metadata does not allow Python {python_version}")
    rejected_version = _first_rejected_python_version(requires_python)
    if rejected_version and _requires_python_allows(requires_python, rejected_version):
        _fail(f"{artifact_name} metadata allows unsupported Python {rejected_version}")
    if metadata["Summary"] != project["description"]:
        _fail(f"{artifact_name} metadata has wrong Summary: {metadata['Summary']}")
    classifiers = set(metadata.get_all("Classifier") or [])
    missing_classifiers = {
        str(classifier) for classifier in project_classifiers if str(classifier) not in classifiers
    }
    if missing_classifiers:
        _fail(f"{artifact_name} metadata is missing classifiers: {sorted(missing_classifiers)}")
    extras = set(metadata.get_all("Provides-Extra") or [])
    optional_dependencies = project.get("optional-dependencies")
    if not isinstance(optional_dependencies, Mapping):
        _fail("pyproject.toml is missing [project.optional-dependencies]")
    expected_extras = {str(extra) for extra in optional_dependencies}
    if extras != expected_extras:
        missing_extras = sorted(expected_extras - extras)
        unexpected_extras = sorted(extras - expected_extras)
        _fail(
            f"{artifact_name} metadata optional extras drifted: "
            f"missing={missing_extras}, unexpected={unexpected_extras}"
        )
    project_urls = project.get("urls")
    if not isinstance(project_urls, Mapping):
        _fail("pyproject.toml is missing [project.urls]")
    missing_urls = {
        (str(label), str(url))
        for label, url in project_urls.items()
        if (str(label), str(url)) not in _project_url_pairs(metadata)
    }
    if missing_urls:
        _fail(f"{artifact_name} metadata is missing Project-URL pairs: {sorted(missing_urls)}")
    description = metadata.get_payload()
    if not isinstance(description, str):
        _fail(f"{artifact_name} metadata is missing the README long description")
    readme = (ROOT / str(project["readme"])).read_text()
    if description.strip() != readme.strip():
        _fail(f"{artifact_name} metadata long description does not match README.md")


def assert_sdist_required_categories(names: set[str]) -> None:
    _assert_present(names, SDIST_REQUIRED_BUILD_FILES, "sdist build payload")
    _assert_present(names, SDIST_REQUIRED_DOCS_AND_EXAMPLES, "sdist docs/examples payload")
    _assert_present(names, SDIST_REQUIRED_UPSTREAM_SOURCE, "sdist upstream payload")


def _is_allowed_upstream_source(name: str) -> bool:
    return (
        name in ALLOWED_UPSTREAM_ROOTS
        or name in ALLOWED_UPSTREAM_EXACT
        or name.startswith(ALLOWED_UPSTREAM_PREFIXES)
    )


def assert_sdist_excludes_junk_and_dashboard_payload(names: set[str]) -> None:
    for name in names:
        if (
            name in FORBIDDEN_SUPPORT_EXACT
            or name.startswith(FORBIDDEN_SUPPORT_PREFIXES)
            or name.endswith((".pyc", ".pyo"))
            or "__pycache__/" in name
        ):
            _fail(f"sdist contains support/development junk: {name}")
        if _is_distribution_name_source_payload(name) or _is_distribution_name_import_payload(name):
            _fail(f"sdist contains forbidden import payload: {name}")
        if name in {
            "src/agentbrowser.py",
            "src/agentbrowser.pyi",
            "src/pyagentbrowser.py",
            "src/pyagentbrowser.pyi",
        }:
            _fail(f"sdist contains forbidden import payload: {name}")
        if name in FORBIDDEN_UPSTREAM_EXACT or name.startswith(FORBIDDEN_UPSTREAM_PREFIXES):
            _fail(f"sdist contains forbidden upstream dashboard/assets/docs payload: {name}")
        if name.startswith("third_party/agent-browser/") and not _is_allowed_upstream_source(name):
            _fail(f"sdist contains unnecessary upstream submodule file: {name}")


def check_wheel(path: Path) -> None:
    names = wheel_names(path)
    sizes = wheel_file_sizes(path)
    assert_wheel_runtime_payload(names, sizes, path.name)
    assert_wheel_python_modules_are_nonempty(sizes)
    assert_wheel_excludes_source_and_junk(names)
    assert_metadata_invariants(_metadata_from_wheel(path), path.name)


def check_sdist(path: Path) -> None:
    names = sdist_names(path)
    assert_sdist_required_categories(names)
    assert_sdist_excludes_junk_and_dashboard_payload(names)
    assert_metadata_invariants(_metadata_from_sdist(path), path.name)


def find_artifacts(dist: Path) -> tuple[list[Path], Path]:
    wheels = sorted(dist.glob("pyagentbrowser-*.whl"))
    sdists = sorted(dist.glob("pyagentbrowser-*.tar.gz"))
    if not wheels:
        _fail(f"expected at least one wheel in {dist}")
    if len(sdists) != 1:
        _fail(f"expected exactly one sdist in {dist}, found {[path.name for path in sdists]}")
    return wheels, sdists[0]


def check_dist(dist: Path) -> None:
    wheels, sdist = find_artifacts(dist)
    for wheel in wheels:
        check_wheel(wheel)
        print(f"wheel artifact smoke passed: {wheel}")
    check_sdist(sdist)
    print(f"sdist artifact smoke passed: {sdist}")


def main() -> int:
    dist = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("target/wheels")
    try:
        check_dist(dist)
    except PackageSmokeError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
