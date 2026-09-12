from __future__ import annotations

import os
import re
import zipfile
from pathlib import Path

from .core import ROOT, _fail

CONTAINER_BUILD_PATHS = (
    b"/io/crates/",
    b"/io/src/",
    b"/io/third_party/",
    b"/io/target/",
    b"/root/.cargo/",
    b"/usr/local/cargo/",
)


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


def assert_native_extension_excludes_local_build_paths(path: Path) -> None:
    cargo_home = Path(os.environ.get("CARGO_HOME", Path.home() / ".cargo"))
    forbidden_paths = (os.fsencode(ROOT), os.fsencode(cargo_home), *CONTAINER_BUILD_PATHS)
    with zipfile.ZipFile(path) as archive:
        native_extensions = _native_extensions(set(archive.namelist()))
        if len(native_extensions) != 1:
            _fail(f"wheel contains unexpected native extensions: {native_extensions}")
        native = archive.read(native_extensions[0])
    leaked = [build_path for build_path in forbidden_paths if build_path in native]
    if leaked:
        _fail(f"wheel native extension contains local build paths: {leaked}")
