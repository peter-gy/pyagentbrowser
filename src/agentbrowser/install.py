from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias

from agentbrowser._native import browser_cache_dir, find_chrome_executable
from agentbrowser.models import AgentBrowserError

InstallSource: TypeAlias = Literal["environment", "cache", "system", "download"]


class BrowserInstallError(AgentBrowserError):
    """Raised when pyagentbrowser cannot prepare a local Chrome executable."""


@dataclass(frozen=True, slots=True)
class InstallResult:
    """Chrome executable selected or installed for pyagentbrowser."""

    executable_path: Path
    version: str | None
    source: InstallSource
    installed: bool


def ensure_installed(*, progress: bool = True) -> InstallResult:
    """Return a local Chrome executable, installing Chrome for Testing when needed.

    The installer uses the native Rust `agent-browser install` implementation
    bundled in pyagentbrowser. `progress=True` lets that installer write its
    normal progress output to the current terminal.
    """
    existing = _existing_browser()
    if existing is not None:
        return existing

    command = [
        sys.executable,
        "-c",
        "from agentbrowser._native import _run_browser_install; _run_browser_install(False)",
    ]
    if progress:
        result = subprocess.run(command, check=False)
        output = ""
    else:
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        output = _install_output(result)

    if result.returncode != 0:
        detail = f" with exit code {result.returncode}"
        if output:
            detail = f"{detail}: {output}"
        raise BrowserInstallError(f"Chrome installation failed{detail}")

    installed = _existing_browser()
    if installed is None:
        raise BrowserInstallError("Chrome installation completed without an executable")

    return InstallResult(
        executable_path=installed.executable_path,
        version=installed.version,
        source="download" if installed.source == "cache" else installed.source,
        installed=installed.source == "cache",
    )


def _existing_browser() -> InstallResult | None:
    env_path = _existing_env_executable()
    if env_path is not None:
        return InstallResult(
            executable_path=env_path,
            version=None,
            source="environment",
            installed=False,
        )

    raw_path = find_chrome_executable()
    if raw_path is None:
        return None
    path = Path(raw_path).expanduser()
    if not path.exists():
        return None

    cache_dir = Path(browser_cache_dir()).expanduser()
    source: InstallSource = "cache" if _is_relative_to(path, cache_dir) else "system"
    return InstallResult(
        executable_path=path,
        version=_version_from_cache_path(path, cache_dir) if source == "cache" else None,
        source=source,
        installed=False,
    )


def _existing_env_executable() -> Path | None:
    raw_path = os.environ.get("AGENT_BROWSER_EXECUTABLE_PATH")
    if raw_path is None or raw_path.strip() == "":
        return None
    path = Path(raw_path).expanduser()
    return path if path.exists() else None


def _install_output(result: subprocess.CompletedProcess[str]) -> str:
    text = "\n".join(part.strip() for part in [result.stdout, result.stderr] if part)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines[-12:])


def _version_from_cache_path(path: Path, cache_dir: Path) -> str | None:
    try:
        relative = path.resolve().relative_to(cache_dir.resolve())
    except ValueError:
        return None
    first = relative.parts[0] if relative.parts else ""
    return first.removeprefix("chrome-") if first.startswith("chrome-") else None


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True
