from __future__ import annotations

import os
import tarfile
import tomllib
from email.message import Message
from email.parser import Parser
from pathlib import Path

from .core import ROOT, _assert_present, _fail, _is_distribution_name_import_payload
from .metadata import assert_metadata_invariants
from .plugin import assert_sdist_agent_plugin

SDIST_REQUIRED_BUILD_FILES = frozenset(
    {
        "_agent_plugins_maturin.py",
        "pyproject.toml",
        "LICENSE",
        "NOTICE",
        "Cargo.toml",
        "Cargo.lock",
        "rust-toolchain.toml",
        "src/agentbrowser/__init__.py",
        "src/agentbrowser/_upstream.json",
        "crates/pyagentbrowser/Cargo.toml",
        "crates/pyagentbrowser/build.rs",
        "crates/pyagentbrowser/src/lib.rs",
        "crates/agent-browser-adapter/Cargo.toml",
        "crates/agent-browser-adapter/build.rs",
        "crates/agent-browser-adapter/src/lib.rs",
        "crates/agent-browser-build/Cargo.toml",
        "crates/agent-browser-build/src/lib.rs",
    }
)


SDIST_REQUIRED_DOCS_AND_EXAMPLES = frozenset(
    {
        "README.md",
        "docs/index.md",
        "docs/getting-started.md",
        "docs/concepts/runtime-model.md",
        "docs/concepts/evidence.md",
        "docs/reference/browser.md",
        "docs/reference/namespaces.md",
        "docs/reference/models.md",
        "docs/troubleshooting.md",
        "examples/basic_navigation.py",
    }
)


SDIST_REQUIRED_UPSTREAM_SOURCE = frozenset(
    {
        "third_party/agent-browser/LICENSE",
        "third_party/agent-browser/cli/Cargo.toml",
        "third_party/agent-browser/cli/build.rs",
        "third_party/agent-browser/cli/src/native/a11y/LICENSE-axe-core-THIRD-PARTY.txt",
        "third_party/agent-browser/cli/src/native/a11y/LICENSE-axe-core.txt",
        "third_party/agent-browser/cli/src/native/a11y/axe.min.js",
        "third_party/agent-browser/cli/src/native/a11y/mod.rs",
        "third_party/agent-browser/cli/src/ca_bundle.rs",
        "third_party/agent-browser/cli/src/native/actions.rs",
        "third_party/agent-browser/cli/src/native/cdp/windows_process.rs",
        "third_party/agent-browser/cli/src/native/tab_binding.rs",
        "third_party/agent-browser/cli/src/native/webmcp.rs",
        "third_party/agent-browser/cli/cdp-protocol/browser_protocol.json",
        "third_party/agent-browser/skill-data/core/SKILL.md",
        "third_party/agent-browser/skill-data/derive-client/SKILL.md",
        "third_party/agent-browser/skill-data/protected-vercel-deployments/SKILL.md",
        "third_party/agent-browser/skill-data/webmcp-gen/SKILL.md",
    }
)


FORBIDDEN_SUPPORT_PREFIXES = (
    ".github/",
    "crates/agent-browser-adapter/target/",
    "development_docs/",
    "docs/figures/",
    "target/",
    "tests/",
)


FORBIDDEN_SUPPORT_EXACT = frozenset(
    {
        ".gitattributes",
        "AGENTS.md",
        "CLAUDE.md",
        "crates/AGENTS.md",
        "crates/agent-browser-adapter/Cargo.lock",
        "src/agentbrowser/AGENTS.md",
    }
)


FORBIDDEN_UPSTREAM_PREFIXES = (
    "third_party/agent-browser/.claude-plugin/",
    "third_party/agent-browser/.github/",
    "third_party/agent-browser/.husky/",
    "third_party/agent-browser/benchmarks/",
    "third_party/agent-browser/bin/",
    "third_party/agent-browser/docker/",
    "third_party/agent-browser/docs/",
    "third_party/agent-browser/evals/",
    "third_party/agent-browser/examples/",
    "third_party/agent-browser/packages/",
    "third_party/agent-browser/scripts/",
    "third_party/agent-browser/skills/",
)


FORBIDDEN_UPSTREAM_EXACT = frozenset(
    {
        "third_party/agent-browser/AGENTS.md",
        "third_party/agent-browser/CHANGELOG.md",
        "third_party/agent-browser/README.md",
        "third_party/agent-browser/agent-browser.schema.json",
        "third_party/agent-browser/package.json",
        "third_party/agent-browser/pnpm-lock.yaml",
        "third_party/agent-browser/pnpm-workspace.yaml",
    }
)


def sdist_names(path: Path) -> set[str]:
    with tarfile.open(path) as archive:
        return {name.split("/", 1)[1] for name in archive.getnames() if "/" in name}


def _is_distribution_name_source_payload(name: str) -> bool:
    return name.startswith("src/pyagentbrowser/") or (
        name.startswith("src/pyagentbrowser.") and name.endswith((".py", ".pyi", ".so", ".pyd"))
    )


def assert_sdist_reproducible_timestamps(path: Path) -> None:
    value = os.environ.get("SOURCE_DATE_EPOCH")
    if value is None:
        return
    expected = int(value)
    with tarfile.open(path) as archive:
        drifted = sorted(member.name for member in archive.getmembers() if member.mtime != expected)
    if drifted:
        _fail(f"sdist members do not use SOURCE_DATE_EPOCH: {drifted}")


def _metadata_from_sdist(path: Path) -> Message:
    with tarfile.open(path) as archive:
        pkg_info_names = [name for name in archive.getnames() if name.endswith("/PKG-INFO")]
        if len(pkg_info_names) != 1:
            _fail(f"sdist should contain exactly one PKG-INFO file, found {pkg_info_names}")
        member = archive.extractfile(pkg_info_names[0])
        if member is None:
            _fail("sdist PKG-INFO could not be read")
        return Parser().parsestr(member.read().decode("utf-8"))


def assert_sdist_required_categories(names: set[str]) -> None:
    _assert_present(names, SDIST_REQUIRED_BUILD_FILES, "sdist build payload")
    _assert_present(names, SDIST_REQUIRED_DOCS_AND_EXAMPLES, "sdist docs/examples payload")
    _assert_present(names, SDIST_REQUIRED_UPSTREAM_SOURCE, "sdist upstream payload")
    assert_sdist_build_sources(names)


def assert_sdist_build_sources(names: set[str], root: Path = ROOT) -> None:
    manifest = tomllib.loads((root / "Cargo.toml").read_text(encoding="utf-8"))
    required = set()
    for member in manifest["workspace"]["members"]:
        crate = root / member
        required.add(f"{member}/Cargo.toml")
        required.update(
            path.relative_to(root).as_posix()
            for path in (crate / "src").rglob("*.*")
            if path.is_file()
        )
        if (crate / "build.rs").is_file():
            required.add(f"{member}/build.rs")
    _assert_present(names, required, "sdist owned build sources")


def assert_sdist_excludes_junk_and_dashboard_payload(names: set[str]) -> None:
    for name in names:
        if (
            name in FORBIDDEN_SUPPORT_EXACT
            or name.startswith(FORBIDDEN_SUPPORT_PREFIXES)
            or name.endswith((".pyc", ".pyo"))
            or "__pycache__/" in name
        ):
            _fail(f"sdist contains support/development junk: {name}")
        if _is_distribution_name_source_payload(name) or _is_distribution_name_import_payload(name):
            _fail(f"sdist contains forbidden import payload: {name}")
        if name in {
            "src/agentbrowser.py",
            "src/agentbrowser.pyi",
            "src/pyagentbrowser.py",
            "src/pyagentbrowser.pyi",
        }:
            _fail(f"sdist contains forbidden import payload: {name}")
        if name in FORBIDDEN_UPSTREAM_EXACT or name.startswith(FORBIDDEN_UPSTREAM_PREFIXES):
            _fail(f"sdist contains forbidden upstream dashboard/assets/docs payload: {name}")


def check_sdist(path: Path) -> None:
    names = sdist_names(path)
    assert_sdist_required_categories(names)
    assert_sdist_excludes_junk_and_dashboard_payload(names)
    assert_sdist_agent_plugin(names)
    assert_sdist_reproducible_timestamps(path)
    assert_metadata_invariants(_metadata_from_sdist(path), path.name)
