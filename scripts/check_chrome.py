from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Callable, Mapping
from pathlib import Path

MACOS_APP_CANDIDATES = (
    Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    Path("/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary"),
    Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
)
WINDOWS_INSTALL_SUFFIX = Path("Google") / "Chrome" / "Application" / "chrome.exe"
WINDOWS_INSTALL_ROOTS = ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")
PATH_COMMANDS = (
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "chrome",
    "chrome.exe",
    "chromium.exe",
)
BROWSER_CACHE_PATTERNS = (
    "chrome-*/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
    "chrome-*/chrome-linux64/chrome",
    "chrome-*/chrome-win64/chrome.exe",
    "chrome-*/chrome.exe",
)


def chrome_candidates(
    *,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> list[Path]:
    environ = os.environ if environ is None else environ
    if raw_path := environ.get("PYAGENTBROWSER_CHROME"):
        return [Path(raw_path).expanduser()]

    home = Path.home() if home is None else home
    candidates = list(MACOS_APP_CANDIDATES)
    for variable in WINDOWS_INSTALL_ROOTS:
        if root := environ.get(variable):
            candidates.append(Path(root) / WINDOWS_INSTALL_SUFFIX)
    browser_cache = home / ".agent-browser" / "browsers"
    for pattern in BROWSER_CACHE_PATTERNS:
        candidates.extend(sorted(browser_cache.glob(pattern), reverse=True))
    for command in PATH_COMMANDS:
        if resolved := which(command):
            candidates.append(Path(resolved))
    return candidates


def chrome_executable(
    *,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
    which: Callable[[str], str | None] = shutil.which,
    exists: Callable[[Path], bool] | None = None,
) -> Path | None:
    exists = Path.exists if exists is None else exists
    for path in chrome_candidates(environ=environ, home=home, which=which):
        if exists(path):
            return path
    return None


def main() -> int:
    path = chrome_executable()
    if path is None:
        print(
            "Chrome executable not found. Set PYAGENTBROWSER_CHROME or install Chrome/Chromium.",
            file=sys.stderr,
        )
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
