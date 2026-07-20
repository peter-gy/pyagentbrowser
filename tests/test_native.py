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

import agentbrowser.skills as skills
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


def _dashboard_control_client(socket_dir: Path, session: str) -> socket.socket:
    if os.name == "nt":
        port = int((socket_dir / f"{session}.port").read_text())
        return socket.create_connection(("127.0.0.1", port))
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.connect(str(socket_dir / f"{session}.sock"))
    return client


def test_native_extension_reports_exact_upstream_provenance() -> None:
    assert __agent_browser_version__ == UPSTREAM_VERSION


def test_native_skill_data_matches_upstream_submodule_snapshot() -> None:
    root = Path(__file__).resolve().parents[1]
    upstream = root / "third_party" / "agent-browser" / "skill-data"
    assert upstream.is_dir()

    upstream_files = {
        path.relative_to(upstream): path.read_text(encoding="utf-8")
        for path in upstream.rglob("*")
        if path.is_file()
    }
    public_files: dict[Path, str] = {}
    for skill in skills.list(include_hidden=True, full=True):
        public_files[Path(skill.name) / "SKILL.md"] = skills.read(skill.name)
        for file in skill.files:
            public_files[Path(skill.name) / file.path] = skills.read(skill.name, file.path)

    assert public_files == upstream_files


@pytest.mark.parametrize(
    ("options", "command", "match"),
    [
        ({"restore_key": "saved"}, {}, "--restore"),
        ({}, {"storageState": "/tmp/state.json"}, "storageState"),
        ({}, {"cdpPort": 9222}, "--cdp"),
        ({}, {"profile": "/tmp/profile"}, "--profile"),
        ({}, {"args": ["--user-data-dir=/tmp/profile"]}, "--user-data-dir"),
        ({}, {"provider": "safari"}, "Safari provider"),
    ],
)
def test_native_allowlist_rejects_uncontained_launch_modes(
    options: dict[str, object],
    command: dict[str, object],
    match: str,
) -> None:
    native = NativeBrowser(json.dumps({"allowed_domains": "example.com", **options}))
    response = json.loads(
        native.execute_json(json.dumps({"id": "launch", "action": "launch", **command}))
    )

    assert response["success"] is False
    assert match in response["error"]


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
        status = browser.session.status()

    assert status.session_id == "py-state"
    assert status.namespace == "Worktree: One"
    assert status.restore_key == "py-state"
    assert status.restore_save == "never"
    assert status.restore_check_text == "Dashboard"
    assert status.socket_dir == (socket_dir / "namespaces" / "worktree-one" / "run")


def test_dashboard_sidecars_control_boundary_and_teardown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory(prefix="pab-") as raw_dir:
        socket_dir = Path(raw_dir)
        monkeypatch.setenv("AGENT_BROWSER_SOCKET_DIR", str(socket_dir))
        session = "py-dashboard"
        browser = Browser(session=SessionOptions(session_id=session, dashboard=DashboardOptions()))

        assert _sidecars(socket_dir, session) == []
        browser.dashboard.status()
        control_sidecar = socket_dir / f"{session}.{'port' if os.name == 'nt' else 'sock'}"
        assert control_sidecar.exists()
        assert int((socket_dir / f"{session}.stream").read_text()) > 0
        assert (socket_dir / f"{session}.version").read_text() == UPSTREAM_VERSION

        with _dashboard_control_client(socket_dir, session) as client:
            client.sendall(b'{"id":"control","action":"navigate"}\n')
            with client.makefile("rb") as responses:
                denied = json.loads(responses.readline())
        assert denied["success"] is False

        with _dashboard_control_client(socket_dir, session) as client:
            client.sendall(b'{"id":"detach","action":"close"}\n')
            with client.makefile("rb") as responses:
                detached = json.loads(responses.readline())
        assert detached["data"]["observable_only"] is True

        browser.close()
        assert _sidecars(socket_dir, session) == []


def test_dashboard_control_close_cleans_namespaced_sidecars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory(prefix="pab-") as raw_dir:
        root = Path(raw_dir)
        socket_dir = root / "namespaces" / "w" / "run"
        monkeypatch.setenv("AGENT_BROWSER_SOCKET_DIR", str(root))
        session = "n"
        browser = Browser(
            session=SessionOptions(
                session_id=session,
                namespace="W",
                dashboard=DashboardOptions(),
            )
        )

        browser.dashboard.status()
        assert _sidecars(socket_dir, session)

        with _dashboard_control_client(socket_dir, session) as client:
            client.sendall(b'{"id":"detach","action":"close"}\n')
            with client.makefile("rb") as responses:
                detached = json.loads(responses.readline())

        assert detached["data"]["observable_only"] is True
        assert _sidecars(socket_dir, session) == []
        browser.close()


def test_dashboard_stop_removes_stream_sidecars(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory(prefix="pab-") as raw_dir:
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
    with tempfile.TemporaryDirectory(prefix="pab-") as raw_dir:
        socket_dir = Path(raw_dir)
        marker = socket_dir / "closed"
        session = "py-dashboard-partial"
        env = os.environ.copy()
        env["AGENT_BROWSER_SOCKET_DIR"] = str(socket_dir)
        script = f"""
import socket
import os
from pathlib import Path
from agentbrowser import Browser, DashboardOptions, SessionOptions

socket_dir = Path({str(socket_dir)!r})
browser = Browser(
    session=SessionOptions(session_id={session!r}, dashboard=DashboardOptions())
)
browser.dashboard.status()
if os.name == "nt":
    port = int((socket_dir / {f"{session}.port"!r}).read_text())
    client = socket.create_connection(("127.0.0.1", port))
else:
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
    with tempfile.TemporaryDirectory(prefix="pab-") as raw_dir:
        socket_dir = Path(raw_dir)
        session = "py-dashboard-crash"
        env = os.environ.copy()
        env["AGENT_BROWSER_SOCKET_DIR"] = str(socket_dir)
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
