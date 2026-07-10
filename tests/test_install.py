from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from agentbrowser import BrowserInstallError
from agentbrowser import install as install_mod

pytestmark = pytest.mark.sdk_dx


def test_ensure_installed_returns_environment_executable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chrome = tmp_path / "chrome"
    chrome.write_text("")
    monkeypatch.setenv("AGENT_BROWSER_EXECUTABLE_PATH", str(chrome))
    monkeypatch.setattr(install_mod, "find_chrome_executable", lambda: None)

    result = install_mod.ensure_installed(progress=False)

    assert result.executable_path == chrome
    assert result.source == "environment"
    assert result.installed is False


def test_ensure_installed_returns_discovered_cache_browser(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_dir = tmp_path / ".agent-browser" / "browsers"
    chrome = cache_dir / "chrome-123" / "chrome"
    chrome.parent.mkdir(parents=True)
    chrome.write_text("")
    monkeypatch.delenv("AGENT_BROWSER_EXECUTABLE_PATH", raising=False)
    monkeypatch.setattr(install_mod, "browser_cache_dir", lambda: str(cache_dir))
    monkeypatch.setattr(install_mod, "find_chrome_executable", lambda: str(chrome))

    result = install_mod.ensure_installed(progress=False)

    assert result.executable_path == chrome
    assert result.version == "123"
    assert result.source == "cache"
    assert result.installed is False


def test_ensure_installed_isolates_the_native_installer_in_a_subprocess(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_dir = tmp_path / ".agent-browser" / "browsers"
    chrome = cache_dir / "chrome-123" / "chrome"
    calls = 0
    commands: list[list[str]] = []

    def find_chrome() -> str | None:
        nonlocal calls
        calls += 1
        return str(chrome) if calls > 1 else None

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        chrome.parent.mkdir(parents=True)
        chrome.write_text("")
        assert kwargs["check"] is False
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True
        return subprocess.CompletedProcess(command, 0, stdout="installed", stderr="")

    monkeypatch.delenv("AGENT_BROWSER_EXECUTABLE_PATH", raising=False)
    monkeypatch.setattr(install_mod, "browser_cache_dir", lambda: str(cache_dir))
    monkeypatch.setattr(install_mod, "find_chrome_executable", find_chrome)
    monkeypatch.setattr(install_mod.subprocess, "run", run)

    result = install_mod.ensure_installed(progress=False)

    assert result.executable_path == chrome
    assert result.source == "download"
    assert result.installed is True
    assert len(commands) == 1
    command = commands[0]
    assert command[:2] == [install_mod.sys.executable, "-c"]
    assert "_run_browser_install(False)" in command[2]


def test_ensure_installed_reports_native_install_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def run(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 7, stdout="", stderr="network unavailable")

    monkeypatch.delenv("AGENT_BROWSER_EXECUTABLE_PATH", raising=False)
    monkeypatch.setattr(install_mod, "find_chrome_executable", lambda: None)
    monkeypatch.setattr(install_mod.subprocess, "run", run)

    with pytest.raises(BrowserInstallError, match="network unavailable"):
        install_mod.ensure_installed(progress=False)
