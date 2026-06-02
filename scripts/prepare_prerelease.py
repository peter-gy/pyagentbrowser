from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "third_party" / "agent-browser"


class ReleaseVersionError(RuntimeError):
    pass


def git(args: list[str]) -> str:
    return subprocess.check_output(["git", "-C", str(UPSTREAM), *args], text=True).strip()


def replace_once(path: Path, pattern: str, replacement: str, *, check: bool) -> None:
    text = path.read_text()
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise ReleaseVersionError(f"{path.relative_to(ROOT)} did not match {pattern!r}")
    if check and updated != text:
        raise ReleaseVersionError(f"{path.relative_to(ROOT)} is not synced")
    if not check:
        path.write_text(updated)


def exact_upstream_tag() -> str:
    try:
        tag = git(["describe", "--tags", "--exact-match", "HEAD"])
    except subprocess.CalledProcessError as exc:
        raise ReleaseVersionError(
            "third_party/agent-browser must be checked out at an exact upstream tag"
        ) from exc
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        raise ReleaseVersionError(f"unsupported upstream tag format: {tag}")
    return tag


def current_project_version() -> str:
    match = re.search(r'^version = "([^"]+)"$', (ROOT / "pyproject.toml").read_text(), re.MULTILINE)
    if not match:
        raise ReleaseVersionError("pyproject.toml does not declare a project version")
    return match.group(1)


def resolve_rc(upstream_version: str, rc: int | None) -> int:
    if rc is not None:
        return rc

    current = current_project_version()
    match = re.fullmatch(rf"{re.escape(upstream_version)}rc(\d+)", current)
    if match:
        return int(match.group(1))
    return 0


def sync_versions(*, rc: int | None, check: bool) -> tuple[str, str, str]:
    tag = exact_upstream_tag()
    upstream_version = tag.removeprefix("v")
    rc = resolve_rc(upstream_version, rc)
    short_commit = git(["rev-parse", "--short=7", "HEAD"])
    python_version = f"{upstream_version}rc{rc}"
    rust_prerelease_version = f"{upstream_version}-rc.{rc}"

    replace_once(
        ROOT / "pyproject.toml",
        r'^version = "[^"]+"$',
        f'version = "{python_version}"',
        check=check,
    )
    replace_once(
        ROOT / "pyproject.toml",
        r'^"Upstream agent-browser commit" = "[^"]+"$',
        (
            '"Upstream agent-browser commit" = '
            f'"https://github.com/vercel-labs/agent-browser/commit/{short_commit}"'
        ),
        check=check,
    )
    replace_once(
        ROOT / "crates" / "pyagentbrowser" / "Cargo.toml",
        r'^version = "[^"]+"$',
        f'version = "{rust_prerelease_version}"',
        check=check,
    )
    replace_once(
        ROOT / "crates" / "agent-browser-adapter" / "Cargo.toml",
        r'^version = "[^"]+"$',
        f'version = "{upstream_version}"',
        check=check,
    )

    release_module = ROOT / "src" / "pyagentbrowser" / "_version.py"
    release_module_text = "\n".join(
        [
            '"""Release metadata for the Python distribution and vendored upstream engine."""',
            "",
            'PACKAGE_NAME = "pyagentbrowser"',
            f'PACKAGE_VERSION = "{python_version}"',
            f'UPSTREAM_TAG = "{tag}"',
            f'UPSTREAM_VERSION = "{upstream_version}"',
            f'UPSTREAM_COMMIT = "{short_commit}"',
            "",
        ]
    )
    if check:
        if release_module.read_text() != release_module_text:
            raise ReleaseVersionError("src/pyagentbrowser/_version.py is not synced")
    else:
        release_module.write_text(release_module_text)

    return python_version, tag, short_commit


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync pyagentbrowser prerelease metadata with the pinned upstream tag."
    )
    parser.add_argument(
        "--rc",
        type=int,
        default=None,
        help="pre-release rc number, defaulting to the current pyproject rc",
    )
    parser.add_argument("--check", action="store_true", help="verify files without editing")
    args = parser.parse_args()
    if args.rc is not None and args.rc < 0:
        parser.error("--rc must be non-negative")

    try:
        version, tag, commit = sync_versions(rc=args.rc, check=args.check)
    except ReleaseVersionError as exc:
        print(exc, file=sys.stderr)
        return 1

    action = "verified" if args.check else "synced"
    print(f"{action} pyagentbrowser {version} from agent-browser {tag} ({commit})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
