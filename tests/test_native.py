from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from agentbrowser import (
    Browser,
    ConfirmationRequired,
    DashboardOptions,
    RestoreOptions,
    SessionOptions,
)
from agentbrowser._native import NativeBrowser, __agent_browser_version__
from agentbrowser._version import UPSTREAM_VERSION

pytestmark = pytest.mark.native_smoke


def _wait_until(predicate: Callable[[], bool], timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("condition was not met before timeout")


def _sidecars(socket_dir: Path, session: str) -> list[Path]:
    return list(socket_dir.glob(f"{session}.*"))


def test_native_extension_reports_exact_upstream_provenance() -> None:
    assert __agent_browser_version__ == UPSTREAM_VERSION


@pytest.mark.parametrize(
    "options,command,match",
    [
        ("{not-json", None, "invalid native options JSON"),
        ("{}", "not-json", "invalid command JSON"),
        ("{}", "[]", "command JSON must be an object"),
    ],
)
def test_pyo3_boundary_rejects_invalid_json(
    options: str,
    command: str | None,
    match: str,
) -> None:
    if command is None:
        with pytest.raises(ValueError, match=match):
            NativeBrowser(options)
        return

    native = NativeBrowser(options)
    with pytest.raises(ValueError, match=match):
        native.execute_json(command)


def test_pyo3_boundary_preserves_python_command_ids() -> None:
    native = NativeBrowser("{}")
    response = json.loads(
        native.execute_json(json.dumps({"id": "python-id", "action": "stream_status"}))
    )
    assert response["id"] == "python-id"


def test_restore_and_namespace_options_reach_generated_adapter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    socket_dir = tmp_path / "sockets"
    monkeypatch.setenv("AGENT_BROWSER_SOCKET_DIR", str(socket_dir))
    session = SessionOptions(
        session_id="py-state",
        namespace="Worktree: One",
        restore=RestoreOptions("py-state", save="never", check_text="Dashboard"),
    )

    with Browser(session=session) as browser:
        info = browser.native.data("session_info")

    assert info["session"] == "py-state"
    assert info["namespace"] == "Worktree: One"
    assert info["restoreKey"] == "py-state"
    assert info["restoreSave"] == "never"
    assert info["restoreCheckText"] == "Dashboard"
    assert Path(str(info["socketDir"])) == (socket_dir / "namespaces" / "worktree-one" / "run")


def test_dashboard_sidecars_control_boundary_and_teardown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory(prefix="pab-", dir="/tmp") as raw_dir:
        socket_dir = Path(raw_dir)
        monkeypatch.setenv("AGENT_BROWSER_SOCKET_DIR", str(socket_dir))
        session = "py-dashboard"
        browser = Browser(session=SessionOptions(session_id=session, dashboard=DashboardOptions()))

        assert _sidecars(socket_dir, session) == []
        browser.dashboard.status()
        socket_path = socket_dir / f"{session}.sock"
        assert int((socket_dir / f"{session}.stream").read_text()) > 0
        assert (socket_dir / f"{session}.version").read_text() == UPSTREAM_VERSION

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.connect(str(socket_path))
            client.sendall(b'{"id":"control","action":"navigate"}\n')
            denied = json.loads(client.recv(4096).decode())
        assert denied["success"] is False

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.connect(str(socket_path))
            client.sendall(b'{"id":"detach","action":"close"}\n')
            detached = json.loads(client.recv(4096).decode())
        assert detached["data"]["observable_only"] is True

        browser.close()
        assert _sidecars(socket_dir, session) == []


def test_dashboard_stop_removes_stream_sidecars(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory(prefix="pab-", dir="/tmp") as raw_dir:
        socket_dir = Path(raw_dir)
        monkeypatch.setenv("AGENT_BROWSER_SOCKET_DIR", str(socket_dir))
        session = "py-dashboard-stop"
        browser = Browser(session=SessionOptions(session_id=session, dashboard=DashboardOptions()))

        browser.dashboard.status()
        assert _sidecars(socket_dir, session)
        browser.dashboard.stop()
        assert _sidecars(socket_dir, session) == []
        browser.close()


def test_dashboard_close_does_not_wait_for_partial_control_clients() -> None:
    with tempfile.TemporaryDirectory(prefix="pab-", dir="/tmp") as raw_dir:
        socket_dir = Path(raw_dir)
        marker = socket_dir / "closed"
        session = "py-dashboard-partial"
        env = os.environ.copy()
        env["AGENT_BROWSER_SOCKET_DIR"] = str(socket_dir)
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        script = f"""
import socket
from pathlib import Path
from agentbrowser import Browser, DashboardOptions, SessionOptions

socket_dir = Path({str(socket_dir)!r})
browser = Browser(
    session=SessionOptions(session_id={session!r}, dashboard=DashboardOptions())
)
browser.dashboard.status()
client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
client.connect(str(socket_dir / {f"{session}.sock"!r}))
client.sendall(b'{{"id":"partial","action":"close"}}')
browser.close()
Path({str(marker)!r}).write_text("closed")
client.close()
"""
        completed = subprocess.run(
            [sys.executable, "-c", script],
            env=env,
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert completed.returncode == 0, completed.stderr
        assert marker.read_text() == "closed"


def test_dashboard_watchdog_removes_sidecars_after_parent_exit() -> None:
    with tempfile.TemporaryDirectory(prefix="pab-", dir="/tmp") as raw_dir:
        socket_dir = Path(raw_dir)
        session = "py-dashboard-crash"
        env = os.environ.copy()
        env["AGENT_BROWSER_SOCKET_DIR"] = str(socket_dir)
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        script = f"""
import os
from agentbrowser import Browser, DashboardOptions, SessionOptions
browser = Browser(
    session=SessionOptions(session_id={session!r}, dashboard=DashboardOptions())
)
browser.dashboard.status()
os._exit(23)
"""
        completed = subprocess.run([sys.executable, "-c", script], env=env, timeout=5)
        assert completed.returncode == 23
        _wait_until(lambda: _sidecars(socket_dir, session) == [])


def test_python_confirmation_handle_replays_through_pyo3() -> None:
    browser = Browser(
        session=SessionOptions(confirm_actions=("stream_status",)),
    )
    try:
        with pytest.raises(ConfirmationRequired) as required:
            browser.native.data("stream_status")

        confirmed = required.value.pending.confirm()
        assert isinstance(confirmed, dict)
    finally:
        browser.close()
