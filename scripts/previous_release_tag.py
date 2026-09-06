from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from scripts.release_version import ReleaseVersion, ReleaseVersionError

ROOT = Path(__file__).resolve().parents[1]


def previous_release_tag(
    current_tag: str,
    repository: Path = ROOT,
    current: str = "HEAD",
) -> str:
    release = ReleaseVersion.from_tag(current_tag)
    command = [
        "git",
        "-C",
        str(repository),
        "describe",
        "--tags",
        "--abbrev=0",
        "--match",
        "v[0-9]*",
    ]
    if release.release_candidate is None:
        command.extend(("--exclude", "*rc[0-9]*"))
    command.append(f"{current}^")
    try:
        tag = subprocess.check_output(
            command,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except subprocess.CalledProcessError as error:
        raise ReleaseVersionError(
            f"no previous pyagentbrowser release tag before {current}"
        ) from error
    ReleaseVersion.from_tag(tag)
    return tag


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print the nearest pyagentbrowser release tag before a commit."
    )
    parser.add_argument("--current-tag", required=True, help="pyagentbrowser release tag")
    parser.add_argument("--current", default="HEAD", help="release commit or tag")
    args = parser.parse_args(argv)
    try:
        print(previous_release_tag(args.current_tag, current=args.current))
    except ReleaseVersionError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
