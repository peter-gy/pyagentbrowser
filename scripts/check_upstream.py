from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import tomlkit

from scripts.update_upstream import ROOT, UPSTREAM, _rust_environment


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        command, cwd=cwd, env=env, capture_output=True, text=True, timeout=600, check=False
    )
    if result.returncode:
        diagnostic = result.stdout if result.stdout.lstrip().startswith("{") else result.stderr
        raise RuntimeError(diagnostic.strip() or result.stdout.strip())
    return result.stdout


def _export(commit: str, destination: Path) -> None:
    archive = subprocess.run(
        ["git", "archive", "--format=tar", commit],
        cwd=UPSTREAM,
        capture_output=True,
        timeout=60,
        check=True,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as files:
        files.extractall(destination, filter="data")


def _dependencies(manifest: dict[str, Any]) -> dict[str, Any]:
    dependencies = {
        name: value for name, value in manifest.items() if name.endswith("dependencies")
    }
    for platform, config in manifest.get("target", {}).items():
        for name, value in config.items():
            if name.endswith("dependencies"):
                dependencies[f"target.{platform}.{name}"] = value
    return dependencies


def _configuration(manifest: dict[str, Any]) -> dict[str, Any]:
    package = manifest.get("package", {})
    return {
        "features": manifest.get("features", {}),
        **{
            f"package.{name}": package[name]
            for name in ("name", "edition", "rust-version", "links", "build")
            if name in package
        },
    }


def _inventory(root: Path, pattern: str) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(
            path.read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest()
        for path in sorted(root.glob(pattern))
        if path.is_file()
    }


def _changes(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    return {
        "added": {key: after[key] for key in sorted(after.keys() - before.keys())},
        "deleted": {key: before[key] for key in sorted(before.keys() - after.keys())},
        "changed": {
            key: {"before": before[key], "after": after[key]}
            for key in sorted(before.keys() & after.keys())
            if before[key] != after[key]
        },
    }


def _workspace(destination: Path, candidate: Path) -> None:
    manifest = tomlkit.parse((ROOT / "Cargo.toml").read_text(encoding="utf-8"))
    manifest["workspace"]["members"] = [  # type: ignore[index]
        "crates/agent-browser-build",
        "crates/agent-browser-adapter",
    ]
    (destination / "Cargo.toml").write_text(tomlkit.dumps(manifest), encoding="utf-8")
    shutil.copy2(ROOT / "Cargo.lock", destination / "Cargo.lock")
    for name in ("agent-browser-build", "agent-browser-adapter"):
        shutil.copytree(
            ROOT / "crates" / name,
            destination / "crates" / name,
            ignore=shutil.ignore_patterns("target", "Cargo.lock"),
        )
    shutil.copytree(
        candidate / "cli",
        destination / "third_party/agent-browser/cli",
        ignore=shutil.ignore_patterns(".git", "target", "node_modules"),
    )


def audit(candidate: Path, *, compile_adapter: bool) -> dict[str, Any]:
    """Audit source transformations and optionally compile an isolated adapter."""
    report: dict[str, Any] = {
        "schema_version": 1,
        "success": False,
        "source": str(candidate),
        "baseline": json.loads((ROOT / "src/agentbrowser/_upstream.json").read_text()),
        "changes": {},
        "generation": None,
        "compilation": {"requested": compile_adapter, "success": None},
        "review_required": [],
        "error": None,
    }
    with tempfile.TemporaryDirectory(prefix="pyagentbrowser-upstream-") as temporary:
        work = Path(temporary)
        baseline = work / "baseline"
        _export(report["baseline"]["commit"], baseline)
        before = tomllib.loads((baseline / "cli/Cargo.toml").read_text())
        after = tomllib.loads((candidate / "cli/Cargo.toml").read_text())
        report["version"] = after["package"]["version"]
        changes = report["changes"]
        changes["dependencies"] = _changes(_dependencies(before), _dependencies(after))
        changes["configuration"] = _changes(_configuration(before), _configuration(after))
        changes["modules"] = _changes(
            _inventory(baseline, "cli/src/**/*.rs"), _inventory(candidate, "cli/src/**/*.rs")
        )
        changes["generator"] = _changes(
            _inventory(baseline, "cli/build.rs") | _inventory(baseline, "cli/cdp-protocol/**/*"),
            _inventory(candidate, "cli/build.rs") | _inventory(candidate, "cli/cdp-protocol/**/*"),
        )
        for kind in ("dependencies", "configuration", "generator"):
            if any(changes[kind].values()):
                report["review_required"].append(kind)
        if changes["modules"]["added"] or changes["modules"]["deleted"]:
            report["review_required"].append("modules")
        workspace = work / "workspace"
        workspace.mkdir()
        _workspace(workspace, candidate)
        env = _rust_environment()
        env["CARGO_TARGET_DIR"] = str(ROOT / "target/upstream-check")
        # Cargo can prune workspace packages from the copied lockfile. Offline
        # resolution keeps the probe bounded to dependencies already installed.
        try:
            generated = _run(
                [
                    "cargo",
                    "run",
                    "--offline",
                    "--quiet",
                    "-p",
                    "agent-browser-build",
                    "--",
                    str(workspace / "third_party/agent-browser"),
                    str(work / "generated"),
                ],
                cwd=workspace,
                env=env,
            )
            report["generation"] = json.loads(generated)
        except RuntimeError as error:
            try:
                report["generation"] = json.loads(str(error))
            except json.JSONDecodeError:
                report["error"] = str(error)
        if compile_adapter and report["generation"] and report["generation"]["success"]:
            try:
                _run(
                    ["cargo", "check", "--offline", "--locked", "-p", "agent-browser", "--lib"],
                    cwd=workspace,
                    env=env,
                )
                report["compilation"]["success"] = True
            except RuntimeError as error:
                report["compilation"] = {"requested": True, "success": False, "error": str(error)}
        report["success"] = bool(
            report["generation"]
            and report["generation"]["success"]
            and not report["review_required"]
            and (not compile_adapter or report["compilation"]["success"])
        )
        # Generated paths belong to the temporary workspace. Report stable
        # upstream-relative inputs so saved audits survive its cleanup.
        if report["generation"]:
            details = report["generation"].get("report", {})
            details["source"] = str(candidate)
            prefix = str(workspace / "third_party/agent-browser") + os.sep
            details["inputs"] = [path.removeprefix(prefix) for path in details.get("inputs", [])]
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit an upstream candidate in an isolated workspace. Emit JSON on stdout."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--source", type=Path, help="local upstream checkout containing cli/Cargo.toml"
    )
    source.add_argument("--ref", help="commit or ref already available in the upstream submodule")
    parser.add_argument(
        "--compile", action="store_true", help="also compile the adapter using cached dependencies"
    )
    parser.add_argument("--output", type=Path, help="create a directory containing report.json")
    args = parser.parse_args(argv)
    if args.source:
        args.source = args.source.expanduser().resolve()
        if not (args.source / "cli/Cargo.toml").is_file():
            parser.error("--source must contain cli/Cargo.toml")
    if args.output:
        args.output = args.output.expanduser().resolve()
        if args.output.exists():
            parser.error("--output must name a new directory")
    commit = None
    if args.ref:
        try:
            commit = _run(
                ["git", "rev-parse", "--verify", "--end-of-options", f"{args.ref}^{{commit}}"],
                cwd=UPSTREAM,
            ).strip()
        except (RuntimeError, subprocess.SubprocessError) as error:
            parser.error(f"--ref must resolve in the local upstream submodule: {error}")
    with tempfile.TemporaryDirectory(prefix="pyagentbrowser-candidate-") as temporary:
        work = Path(temporary)
        try:
            candidate = args.source
            if commit:
                candidate = work / "candidate"
                _export(commit, candidate)
            output = args.output or work / "output"
            output.mkdir(parents=True)
            report = audit(candidate, compile_adapter=args.compile)
            if commit:
                report["source"] = {"ref": args.ref, "commit": commit}
                if report["generation"]:
                    report["generation"]["report"]["source"] = report["source"]
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            RuntimeError,
            tarfile.TarError,
            subprocess.SubprocessError,
        ) as error:
            report = {"schema_version": 1, "success": False, "error": str(error)}
        encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.output and args.output.is_dir():
            (args.output / "report.json").write_text(encoded, encoding="utf-8")
        print(encoded, end="")
        return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
