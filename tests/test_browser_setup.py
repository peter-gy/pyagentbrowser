from __future__ import annotations

import os
from pathlib import Path

import pytest

from agentbrowser.install import InstallResult
from scripts import prepare_browser

pytestmark = pytest.mark.sdk_dx


@pytest.mark.parametrize("override", [None, "", "custom browser/chromium"])
def test_browser_preparation_uses_the_integration_test_override(
    override: str | None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("AGENT_BROWSER_EXECUTABLE_PATH", "existing-browser")
    if override is None:
        monkeypatch.delenv("PYAGENTBROWSER_CHROME", raising=False)
    else:
        monkeypatch.setenv("PYAGENTBROWSER_CHROME", override)
    selected = Path(override or "existing-browser")

    def install() -> InstallResult:
        assert os.environ["AGENT_BROWSER_EXECUTABLE_PATH"] == str(selected)
        return InstallResult(selected, None, "environment", False)

    monkeypatch.setattr(prepare_browser, "ensure_installed", install)
    prepare_browser.main()
    assert capsys.readouterr().out == f"{selected}\n"
