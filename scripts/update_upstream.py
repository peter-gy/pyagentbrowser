from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import tomllib
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "third_party" / "agent-browser"
PROVENANCE = ROOT / "src" / "agentbrowser" / "_upstream.json"
ADAPTER_MANIFEST = ROOT / "crates" / "agent-browser-adapter" / "Cargo.toml"
RUST_TOOLCHAIN = ROOT / "rust-toolchain.toml"
OFFICIAL_REMOTE = "https://github.com/vercel-labs/agent-browser.git"


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(UPSTREAM), *args],
        text=True,
    ).strip()


def _run(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> None:
    subprocess.run(command, cwd=cwd, env=env, check=True)


def _metadata() -> dict[str, str]:
    version = str(tomllib.loads((UPSTREAM / "cli/Cargo.toml").read_text())["package"]["version"])
    return {
        "commit": _git("rev-parse", "HEAD"),
        "version": version,
    }


def _metadata_is_synced(metadata: dict[str, str]) -> bool:
    try:
        provenance = json.loads(PROVENANCE.read_text(encoding="utf-8"))
        return provenance == metadata and _adapter_version() == metadata["version"]
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False


def _is_ancestor(ancestor: str, descendant: str) -> bool:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(UPSTREAM),
            "merge-base",
            "--is-ancestor",
            ancestor,
            descendant,
        ],
        check=False,
    )
    if result.returncode not in {0, 1}:
        result.check_returncode()
    return result.returncode == 0


def _description() -> str:
    return _git("describe", "--tags", "--always", "--match", "v[0-9]*")


def _ensure_upstream_checkout() -> None:
    manifest = UPSTREAM / "cli" / "Cargo.toml"
    if manifest.is_file():
        return
    relative = UPSTREAM.relative_to(ROOT)
    _run(
        [
            "git",
            "-C",
            str(ROOT),
            "submodule",
            "update",
            "--init",
            "--recursive",
            str(relative),
        ],
    )
    if not manifest.is_file():
        raise RuntimeError(f"upstream manifest was not initialized at {manifest}")


def _adapter_version() -> str:
    manifest = tomllib.loads(ADAPTER_MANIFEST.read_text(encoding="utf-8"))
    return str(manifest["package"]["version"])


def _rust_toolchain() -> str:
    document = tomllib.loads(RUST_TOOLCHAIN.read_text(encoding="utf-8"))
    return str(document["toolchain"]["channel"])


def _rust_environment() -> dict[str, str]:
    cargo = subprocess.check_output(
        ["rustup", "which", "--toolchain", _rust_toolchain(), "cargo"],
        text=True,
    ).strip()
    rust_bin = str(Path(cargo).parent)
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join(part for part in (rust_bin, env.get("PATH")) if part)
    return env


def _set_adapter_version(version: str) -> None:
    from tomlkit import dumps, parse
    from tomlkit.items import Table

    document = parse(ADAPTER_MANIFEST.read_text(encoding="utf-8"))
    package = document.get("package")
    if not isinstance(package, Table):
        raise RuntimeError(f"{ADAPTER_MANIFEST} is missing [package]")
    package["version"] = version
    ADAPTER_MANIFEST.write_text(dumps(document), encoding="utf-8")


def _require_update_dependencies() -> None:
    importlib.import_module("tomlkit")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Pin the embedded engine and regenerate its provenance."
    )
    parser.add_argument("--ref", default="origin/main", help="upstream ref to pin")
    parser.add_argument("--check", action="store_true", help="verify the current pin")
    parser.add_argument(
        "--allow-non-fast-forward",
        action="store_true",
        help="allow an older or divergent upstream ref",
    )
    args = parser.parse_args(argv)

    _ensure_upstream_checkout()
    remote = _git("remote", "get-url", "origin")
    if remote != OFFICIAL_REMOTE:
        parser.error(f"origin must be {OFFICIAL_REMOTE}, found {remote}")
    if not args.check:
        dirty = _git("status", "--porcelain")
        if dirty:
            parser.error("upstream submodule must be clean before updating")
        previous_commit = _git("rev-parse", "HEAD")
        _run(["git", "-C", str(UPSTREAM), "fetch", "origin"])
        commit = _git("rev-parse", f"{args.ref}^{{commit}}")
        current_metadata = _metadata()
        if commit == previous_commit and _metadata_is_synced(current_metadata):
            print(
                f"agent-browser {current_metadata['version']} already pinned at "
                f"{current_metadata['commit']} ({_description()})"
            )
            return 0
        if (
            commit != previous_commit
            and not args.allow_non_fast_forward
            and not _is_ancestor(previous_commit, commit)
        ):
            parser.error(
                f"{args.ref} is not a fast-forward from {previous_commit}; "
                "pass --allow-non-fast-forward to move backward or across branches"
            )
        _require_update_dependencies()
        _run(["git", "-C", str(UPSTREAM), "checkout", "--detach", commit])

    metadata = _metadata()
    if args.check:
        current = json.loads(PROVENANCE.read_text())
        if current != metadata:
            parser.error("embedded upstream provenance is not synced")
        adapter_version = _adapter_version()
        if adapter_version != metadata["version"]:
            parser.error(
                "adapter package version is not synced: "
                f"expected {metadata['version']}, found {adapter_version}"
            )
    else:
        _set_adapter_version(metadata["version"])
        PROVENANCE.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
        _run(
            ["cargo", "update", "--package", "agent-browser"],
            cwd=ROOT,
            env=_rust_environment(),
        )

    if args.check:
        print(f"agent-browser {metadata['version']} pinned at {metadata['commit']}")
    else:
        print(
            f"agent-browser {metadata['version']} updated "
            f"{previous_commit}..{metadata['commit']} ({_description()})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
