from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.artifacts.core import PackageSmokeError
from scripts.artifacts.release import assert_release_artifact_set, find_artifacts
from scripts.artifacts.sdist import check_sdist
from scripts.artifacts.wheel import check_wheel


def check_dist(dist: Path) -> None:
    wheels, sdist = find_artifacts(dist)
    for wheel in wheels:
        check_wheel(wheel)
        print(f"wheel artifact smoke passed: {wheel}")
    check_sdist(sdist)
    print(f"sdist artifact smoke passed: {sdist}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate pyagentbrowser distributions.")
    parser.add_argument("dist", nargs="?", type=Path, default=Path("target/wheels"))
    parser.add_argument(
        "--release",
        action="store_true",
        help="require the complete five-wheel and source-distribution release set",
    )
    args = parser.parse_args()
    try:
        check_dist(args.dist)
        if args.release:
            assert_release_artifact_set(args.dist)
    except PackageSmokeError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
