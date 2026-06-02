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
PATH_COMMANDS = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")
BROWSER_CACHE_PATTERN = (
    "chrome-*/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
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
    candidates.extend(
        sorted(
            (home / ".agent-browser" / "browsers").glob(BROWSER_CACHE_PATTERN),
            reverse=True,
        )
    )
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
