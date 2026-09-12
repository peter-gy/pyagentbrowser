from __future__ import annotations

import re
import tomllib
from collections.abc import Iterable, Mapping
from email.message import Message

from scripts.release_version import ReleaseVersion, ReleaseVersionError

from .core import ROOT, _fail

WHEEL_REQUIRED_LICENSE_FILES = frozenset(
    {
        "LICENSE",
        "NOTICE",
        "third_party/agent-browser/LICENSE",
        "third_party/agent-browser/cli/src/native/a11y/LICENSE-axe-core-THIRD-PARTY.txt",
        "third_party/agent-browser/cli/src/native/a11y/LICENSE-axe-core.txt",
    }
)


def _normalized_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def project_metadata() -> Mapping[str, object]:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject.get("project")
    if not isinstance(project, Mapping):
        _fail("pyproject.toml is missing [project]")
    return project


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


def _assert_release_version(version: str, artifact_name: str) -> None:
    try:
        ReleaseVersion.parse(version)
    except ReleaseVersionError as error:
        _fail(f"{artifact_name} has an invalid release version: {error}")


def assert_metadata_invariants(metadata: Message, artifact_name: str) -> None:
    project = project_metadata()
    if metadata["Name"] != "pyagentbrowser":
        _fail(f"{artifact_name} metadata has wrong Name: {metadata['Name']}")
    project_version = str(project["version"])
    _assert_release_version(project_version, artifact_name)
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
    license_files = set(metadata.get_all("License-File") or [])
    if license_files != WHEEL_REQUIRED_LICENSE_FILES:
        _fail(
            f"{artifact_name} metadata license files drifted: "
            f"expected={sorted(WHEEL_REQUIRED_LICENSE_FILES)}, actual={sorted(license_files)}"
        )
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
    readme = (ROOT / str(project["readme"])).read_text(encoding="utf-8")
    if _normalized_newlines(description).strip() != _normalized_newlines(readme).strip():
        _fail(f"{artifact_name} metadata long description does not match README.md")
