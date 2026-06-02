from __future__ import annotations

import importlib
import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

chrome_executable = importlib.import_module("scripts.check_chrome").chrome_executable

_skipped_integration: list[str] = []


@pytest.fixture(autouse=True)
def clean_default_browser() -> Iterator[None]:
    import pyagentbrowser as ab

    ab.reset(force=True)
    yield
    ab.reset(force=True)


@pytest.fixture
def chrome_path() -> Path:
    path = chrome_executable()
    if path is None:
        pytest.skip("Chrome executable not available. Set PYAGENTBROWSER_CHROME or install Chrome")
    return path


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if os.environ.get("PYAGENTBROWSER_FAIL_ON_SKIP") != "1":
        return
    if getattr(report, "wasxfail", None):
        return
    if "integration" not in report.keywords or not report.skipped:
        return
    reason = str(report.longrepr)
    _skipped_integration.append(f"{report.nodeid}: {reason}")


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if os.environ.get("PYAGENTBROWSER_FAIL_ON_SKIP") != "1" or not _skipped_integration:
        return
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        reporter.section("skipped integration coverage")
        for skipped in _skipped_integration:
            reporter.line(skipped)
    session.exitstatus = pytest.ExitCode.TESTS_FAILED
