from __future__ import annotations

from pathlib import Path

from .core import _fail
from .metadata import project_metadata


def find_artifacts(dist: Path) -> tuple[list[Path], Path]:
    wheels = sorted(dist.glob("pyagentbrowser-*.whl"))
    sdists = sorted(dist.glob("pyagentbrowser-*.tar.gz"))
    if not wheels:
        _fail(f"expected at least one wheel in {dist}")
    if len(sdists) != 1:
        _fail(f"expected exactly one sdist in {dist}, found {[path.name for path in sdists]}")
    return wheels, sdists[0]


def expected_release_artifact_names(version: str) -> set[str]:
    wheel = f"pyagentbrowser-{version}-cp311-abi3"
    return {
        f"{wheel}-macosx_10_12_x86_64.whl",
        f"{wheel}-macosx_11_0_arm64.whl",
        f"{wheel}-manylinux_2_28_aarch64.whl",
        f"{wheel}-manylinux_2_28_x86_64.whl",
        f"{wheel}-win_amd64.whl",
        f"pyagentbrowser-{version}.tar.gz",
    }


def assert_release_artifact_set(dist: Path) -> None:
    version = str(project_metadata()["version"])
    expected = expected_release_artifact_names(version)
    actual = {path.name for path in dist.iterdir() if path.is_file()}
    if actual != expected:
        _fail(
            "release artifact set does not match the supported platforms: "
            f"missing={sorted(expected - actual)}, unexpected={sorted(actual - expected)}"
        )
