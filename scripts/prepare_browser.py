"""Prepare the browser selected for development and integration tests."""

from __future__ import annotations

import os

from agentbrowser.install import ensure_installed


def main() -> None:
    if path := os.environ.get("PYAGENTBROWSER_CHROME"):
        os.environ["AGENT_BROWSER_EXECUTABLE_PATH"] = path
    print(ensure_installed().executable_path)


if __name__ == "__main__":
    main()
