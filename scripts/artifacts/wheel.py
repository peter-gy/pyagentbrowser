from __future__ import annotations

import base64
import csv
import hashlib
import io
import zipfile
from collections.abc import Mapping
from email.message import Message
from email.parser import Parser
from pathlib import Path

from .core import _assert_present, _fail, _is_distribution_name_import_payload
from .metadata import WHEEL_REQUIRED_LICENSE_FILES, assert_metadata_invariants
from .native import (
    _native_extension_matches_wheel_tags,
    _native_extensions,
    _wheel_python_and_abi_tags,
    assert_native_extension_excludes_local_build_paths,
)
from .plugin import assert_wheel_agent_plugin

AXE_CORE_SOURCE_URL = "https://github.com/dequelabs/axe-core/tree/v4.12.1"


WHEEL_REQUIRED_FILES = frozenset(
    {
        "agentbrowser/__init__.py",
        "agentbrowser/_upstream.json",
        "agentbrowser/py.typed",
    }
)


WHEEL_FORBIDDEN_EXACT = frozenset(
    {
        "agentbrowser/AGENTS.md",
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


def wheel_names(path: Path) -> set[str]:
    with zipfile.ZipFile(path) as archive:
        return set(archive.namelist())


def wheel_file_sizes(path: Path) -> dict[str, int]:
    with zipfile.ZipFile(path) as archive:
        return {info.filename: info.file_size for info in archive.infolist()}


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


def assert_wheel_module_payloads(sizes: Mapping[str, int]) -> None:
    empty = sorted(
        name
        for name, size in sizes.items()
        if name.startswith("agentbrowser/")
        and name.endswith((".py", ".pyi"))
        and not name.endswith("/__init__.py")
        and size <= 0
    )
    if empty:
        _fail(f"wheel contains empty Python modules: {empty}")


def assert_wheel_license_files(path: Path, names: set[str]) -> None:
    resolved: dict[str, str] = {}
    for relative_path in WHEEL_REQUIRED_LICENSE_FILES:
        suffix = f".dist-info/licenses/{relative_path}"
        matches = [name for name in names if name.endswith(suffix)]
        if len(matches) != 1:
            _fail(f"wheel should contain one license file at {relative_path}: {matches}")
        resolved[relative_path] = matches[0]
    with zipfile.ZipFile(path) as archive:
        notice = archive.read(resolved["NOTICE"]).decode("utf-8")
    if AXE_CORE_SOURCE_URL not in notice:
        _fail("wheel NOTICE is missing the axe-core source URL")


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


def assert_wheel_record(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        names = {info.filename for info in archive.infolist() if not info.is_dir()}
        record_names = [name for name in names if name.endswith(".dist-info/RECORD")]
        if len(record_names) != 1:
            _fail(f"wheel should contain one RECORD file: {record_names}")
        record_name = record_names[0]
        rows = {
            name: (digest, size)
            for name, digest, size in csv.reader(
                io.StringIO(archive.read(record_name).decode("utf-8"))
            )
        }
        if set(rows) != names:
            _fail(
                "wheel RECORD inventory drifted: "
                f"missing={sorted(names - set(rows))}, extra={sorted(set(rows) - names)}"
            )
        for name in sorted(names - {record_name}):
            content = archive.read(name)
            encoded = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=")
            expected_digest = f"sha256={encoded.decode('ascii')}"
            digest, size = rows[name]
            if digest != expected_digest or size != str(len(content)):
                _fail(f"wheel RECORD entry does not match {name}")
        if rows[record_name] != ("", ""):
            _fail("wheel RECORD self-entry must have empty hash and size")


def _metadata_from_wheel(path: Path) -> Message:
    with zipfile.ZipFile(path) as archive:
        metadata_names = [
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_names) != 1:
            _fail(f"wheel should contain exactly one METADATA file, found {metadata_names}")
        return Parser().parsestr(archive.read(metadata_names[0]).decode("utf-8"))


def check_wheel(path: Path) -> None:
    names = wheel_names(path)
    sizes = wheel_file_sizes(path)
    assert_wheel_runtime_payload(names, sizes, path.name)
    assert_wheel_module_payloads(sizes)
    assert_wheel_license_files(path, names)
    assert_wheel_excludes_source_and_junk(names)
    assert_wheel_agent_plugin(path, names)
    assert_wheel_record(path)
    assert_native_extension_excludes_local_build_paths(path)
    assert_metadata_invariants(_metadata_from_wheel(path), path.name)
