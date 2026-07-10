from __future__ import annotations

import argparse
import json
import subprocess
import tomllib
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "third_party" / "agent-browser"
PROVENANCE = ROOT / "src" / "agentbrowser" / "_upstream.json"
OFFICIAL_REMOTE = "https://github.com/vercel-labs/agent-browser.git"


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(UPSTREAM), *args],
        text=True,
    ).strip()


def _metadata() -> dict[str, str]:
    return {
        "commit": _git("rev-parse", "HEAD"),
        "tag": _git(
            "describe",
            "--tags",
            "--match",
            "v[0-9]*.[0-9]*.[0-9]*",
            "--abbrev=0",
            "HEAD",
        ),
        "version": str(
            tomllib.loads((UPSTREAM / "cli/Cargo.toml").read_text())["package"]["version"]
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Pin the embedded engine and regenerate its provenance."
    )
    parser.add_argument("--ref", default="origin/main", help="upstream ref to pin")
    parser.add_argument("--check", action="store_true", help="verify the current pin")
    args = parser.parse_args(argv)

    remote = _git("remote", "get-url", "origin")
    if remote != OFFICIAL_REMOTE:
        parser.error(f"origin must be {OFFICIAL_REMOTE}, found {remote}")
    if not args.check:
        dirty = _git("status", "--porcelain")
        if dirty:
            parser.error("upstream submodule must be clean before updating")
        subprocess.run(["git", "-C", str(UPSTREAM), "fetch", "origin"], check=True)
        commit = _git("rev-parse", f"{args.ref}^{{commit}}")
        subprocess.run(
            ["git", "-C", str(UPSTREAM), "checkout", "--detach", commit],
            check=True,
        )

    metadata = _metadata()
    if args.check:
        current = json.loads(PROVENANCE.read_text())
        if current != metadata:
            parser.error("embedded upstream provenance is not synced")
    else:
        PROVENANCE.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
        subprocess.run(["cargo", "generate-lockfile"], cwd=ROOT, check=True)
        subprocess.run(["uv", "lock"], cwd=ROOT, check=True)

    print(f"agent-browser pinned at {metadata['commit']} ({metadata['tag']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
