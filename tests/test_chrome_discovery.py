from __future__ import annotations

from pathlib import Path

import pytest

from scripts import check_chrome

pytestmark = pytest.mark.sdk_dx


def test_chrome_discovery_uses_env_override(tmp_path: Path) -> None:
    chrome = tmp_path / "chrome"
    chrome.write_text("")

    assert (
        check_chrome.chrome_executable(
            environ={"PYAGENTBROWSER_CHROME": str(chrome)},
            home=tmp_path,
            which=lambda _command: None,
        )
        == chrome
    )


def test_chrome_discovery_rejects_missing_env_override(tmp_path: Path) -> None:
    assert (
        check_chrome.chrome_executable(
            environ={"PYAGENTBROWSER_CHROME": str(tmp_path / "missing")},
            home=tmp_path,
            which=lambda _command: None,
        )
        is None
    )


def test_chrome_discovery_checks_agent_browser_browser_cache(tmp_path: Path) -> None:
    cached = (
        tmp_path
        / ".agent-browser"
        / "browsers"
        / "chrome-123"
        / "Google Chrome for Testing.app"
        / "Contents"
        / "MacOS"
        / "Google Chrome for Testing"
    )
    cached.parent.mkdir(parents=True)
    cached.write_text("")

    assert (
        check_chrome.chrome_executable(
            environ={},
            home=tmp_path,
            which=lambda _command: None,
            exists=lambda path: path == cached,
        )
        == cached
    )


def test_chrome_discovery_checks_path_commands(tmp_path: Path) -> None:
    path_chrome = tmp_path / "bin" / "chromium"
    path_chrome.parent.mkdir()
    path_chrome.write_text("")

    def which(command: str) -> str | None:
        return str(path_chrome) if command == "chromium" else None

    assert (
        check_chrome.chrome_executable(
            environ={},
            home=tmp_path,
            which=which,
            exists=lambda path: path == path_chrome,
        )
        == path_chrome
    )
