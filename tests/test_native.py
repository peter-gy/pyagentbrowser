from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import cast

import pytest

from pyagentbrowser import (
    ActionConfirmationRequired,
    Browser,
    BrowserError,
    BrowserSessionOptions,
    DashboardOptions,
    ReadMode,
    ReadResult,
    RestoreOptions,
)
from pyagentbrowser._native import NativeBrowser, __agent_browser_version__

pytestmark = pytest.mark.native_smoke

DEVICE_LIST_ONLY_ON_MACOS = pytest.mark.skipif(
    sys.platform != "darwin",
    reason="device_list is only available on macOS with Xcode",
)
CONFIRMABLE_ACTION = "stream_status"


def _wait_until(predicate: Callable[[], bool], timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("condition was not met before timeout")


def _read_exact(stream: socket.socket, n: int) -> bytes:
    chunks: list[bytes] = []
    remaining = n
    while remaining:
        chunk = stream.recv(remaining)
        if not chunk:
            raise AssertionError("websocket closed while reading frame")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _websocket_connect(port: int) -> socket.socket:
    client = socket.create_connection(("127.0.0.1", port), timeout=2)
    key = base64.b64encode(os.urandom(16)).decode()
    request = (
        "GET / HTTP/1.1\r\n"
        f"Host: 127.0.0.1:{port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "\r\n"
    )
    client.sendall(request.encode())
    response = b""
    while b"\r\n\r\n" not in response:
        response += client.recv(4096)
    expected_accept = base64.b64encode(
        hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
    ).decode()
    assert b" 101 " in response
    assert f"Sec-WebSocket-Accept: {expected_accept}".encode().lower() in response.lower()
    return client


def _websocket_recv_json(stream: socket.socket, timeout: float = 2.0) -> dict[str, object]:
    stream.settimeout(timeout)
    header = _read_exact(stream, 2)
    opcode = header[0] & 0x0F
    length = header[1] & 0x7F
    masked = bool(header[1] & 0x80)
    if length == 126:
        length = int.from_bytes(_read_exact(stream, 2), "big")
    elif length == 127:
        length = int.from_bytes(_read_exact(stream, 8), "big")
    mask = _read_exact(stream, 4) if masked else b""
    payload = _read_exact(stream, length)
    if masked:
        payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    if opcode == 8:
        raise AssertionError("websocket closed before expected message")
    return cast(dict[str, object], json.loads(payload.decode()))


def _send_dashboard_control(socket_path: Path, payload: bytes) -> dict[str, object]:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.connect(str(socket_path))
        client.sendall(payload)
        return cast(dict[str, object], json.loads(client.recv(4096).decode()))


def _dashboard_sidecars(socket_dir: Path, session: str) -> list[Path]:
    return list(socket_dir.glob(f"{session}.*"))


def test_native_binding_exposes_agent_browser_version() -> None:
    assert __agent_browser_version__
    assert "." in __agent_browser_version__


@DEVICE_LIST_ONLY_ON_MACOS
def test_native_device_list_returns_device_records() -> None:
    with Browser() as browser:
        data = browser.native.data("device_list")

    assert "devices" in data
    devices = data["devices"]
    assert isinstance(devices, list)
    assert devices
    for device in devices:
        assert isinstance(device, dict)
        assert isinstance(cast(dict[str, object], device).get("name"), str)


def test_native_bridge_rejects_invalid_options_json() -> None:
    with pytest.raises(ValueError, match="invalid native options JSON"):
        NativeBrowser("{not-json")


def test_native_bridge_rejects_invalid_command_json() -> None:
    native = NativeBrowser()
    with pytest.raises(ValueError, match="invalid command JSON"):
        native.execute_json("{not-json")


def test_native_bridge_rejects_non_object_command_json() -> None:
    native = NativeBrowser()

    with pytest.raises(ValueError, match="command JSON must be an object"):
        native.execute_json("[]")


def test_native_bridge_preserves_command_ids_at_pyo3_boundary() -> None:
    response = json.loads(
        NativeBrowser().execute_json('{"id": "custom", "action": "stream_status"}')
    )

    assert response["id"] == "custom"
    assert response["success"] is True
    assert "enabled" in response["data"]


def test_native_read_fetches_markdown_through_page_namespace() -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/markdown")
            self.end_headers()
            self.wfile.write(b"# Native read\n")

        def log_message(self, format: str, *args: object) -> None:
            del format, args
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/docs"
            with Browser(
                session_options=BrowserSessionOptions(allowed_domains="127.0.0.1")
            ) as browser:
                result = browser.page.read(url, mode=ReadMode.markdown(require=True))
        finally:
            server.shutdown()
            thread.join(timeout=2)

    assert isinstance(result, ReadResult)
    assert result.status == 200
    assert result.content == "# Native read\n"
    assert result.content_type == "text/markdown"


def test_native_restore_constructor_configures_session_info() -> None:
    with Browser.from_session(
        "py-restore",
        restore=RestoreOptions(key="py-restore", save="never", check_text="Dashboard"),
    ) as browser:
        info = browser.restore.info()

    assert info["session"] == "py-restore"
    assert info["restoreKey"] == "py-restore"
    assert info["restoreSave"] == "never"
    assert info["restoreCheckText"] == "Dashboard"
    assert info["restoreStatus"] == "pending"


def test_native_namespace_scopes_session_info(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    socket_dir = tmp_path / "sockets"
    monkeypatch.setenv("AGENT_BROWSER_SOCKET_DIR", str(socket_dir))
    monkeypatch.delenv("AGENT_BROWSER_NAMESPACE", raising=False)

    with Browser.from_session(
        "py-namespace",
        session_options=BrowserSessionOptions(namespace="Worktree: One"),
    ) as browser:
        info = browser.runtime.info()

    socket_path = Path(str(info["socketDir"]))
    assert info["namespace"] == "Worktree: One"
    assert socket_path == socket_dir / "namespaces" / "worktree-one" / "run"
    assert "AGENT_BROWSER_NAMESPACE" not in os.environ


def test_native_dashboard_writes_discovery_sidecars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory(prefix="pab-", dir="/tmp") as socket_dir_raw:
        socket_dir = Path(socket_dir_raw)
        monkeypatch.setenv("AGENT_BROWSER_SOCKET_DIR", str(socket_dir))
        browser = Browser.from_session("py-dashboard")

        try:
            browser.dashboard.start()
            stream_path = socket_dir / "py-dashboard.stream"
            pid_path = socket_dir / "py-dashboard.pid"
            socket_path = socket_dir / "py-dashboard.sock"

            assert int(stream_path.read_text()) > 0
            assert int(pid_path.read_text()) > 0
            assert socket_path.exists()
            assert (socket_dir / "py-dashboard.version").read_text() == __agent_browser_version__
            assert json.loads((socket_dir / "py-dashboard.metadata").read_text())["control"] == (
                "observable-only"
            )
        finally:
            browser.close()


def test_native_dashboard_start_is_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory(prefix="pab-", dir="/tmp") as socket_dir_raw:
        socket_dir = Path(socket_dir_raw)
        monkeypatch.setenv("AGENT_BROWSER_SOCKET_DIR", str(socket_dir))
        browser = Browser.from_session("py-dashboard")

        try:
            assert _dashboard_sidecars(socket_dir, "py-dashboard") == []
            browser.dashboard.start()
            assert (socket_dir / "py-dashboard.stream").exists()
        finally:
            browser.close()


def test_native_dashboard_stream_status_reports_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory(prefix="pab-", dir="/tmp") as socket_dir_raw:
        socket_dir = Path(socket_dir_raw)
        monkeypatch.setenv("AGENT_BROWSER_SOCKET_DIR", str(socket_dir))
        browser = Browser.from_session("py-dashboard")

        try:
            browser.dashboard.start()
            assert browser.native.data("stream_status")["enabled"] is True
        finally:
            browser.close()


def test_native_dashboard_control_close_is_observable_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory(prefix="pab-", dir="/tmp") as socket_dir_raw:
        socket_dir = Path(socket_dir_raw)
        monkeypatch.setenv("AGENT_BROWSER_SOCKET_DIR", str(socket_dir))
        browser = Browser.from_session("py-dashboard")

        try:
            browser.dashboard.start()
            stream_path = socket_dir / "py-dashboard.stream"
            socket_path = socket_dir / "py-dashboard.sock"

            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.connect(str(socket_path))
                client.sendall(b'{"id":"dash-test","action":"close"}\n')
                response = json.loads(client.recv(4096).decode())

            assert response["success"] is True
            assert response["data"]["observable_only"] is True
            assert response["data"]["detached"] is True
            _wait_until(lambda: not stream_path.exists())
            assert browser.native.data("stream_status")["enabled"] is True
        finally:
            browser.close()


def test_native_dashboard_close_removes_sidecars(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory(prefix="pab-", dir="/tmp") as socket_dir_raw:
        socket_dir = Path(socket_dir_raw)
        monkeypatch.setenv("AGENT_BROWSER_SOCKET_DIR", str(socket_dir))
        browser = Browser.from_session("py-dashboard")
        browser.dashboard.start()

        browser.close()

        assert _dashboard_sidecars(socket_dir, "py-dashboard") == []


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(b"{not-json\n", id="invalid-json"),
        pytest.param(b'{"id":"dash-nav","action":"navigate"}\n', id="navigate"),
        pytest.param(b'{"id":"dash-kill","action":"kill"}\n', id="kill"),
        pytest.param(b'{"id":"dash-shot","action":"screenshot"}\n', id="screenshot"),
    ],
)
def test_native_dashboard_rejects_hostile_control(
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
) -> None:
    with tempfile.TemporaryDirectory(prefix="pab-", dir="/tmp") as socket_dir_raw:
        socket_dir = Path(socket_dir_raw)
        monkeypatch.setenv("AGENT_BROWSER_SOCKET_DIR", str(socket_dir))

        with Browser.from_session("py-dashboard-hostile") as browser:
            browser.dashboard.start()
            socket_path = socket_dir / "py-dashboard-hostile.sock"
            response = _send_dashboard_control(socket_path, payload)

            assert response["success"] is False
            assert "observable-only" in cast(str, response["error"])
            data = cast(dict[str, object], response["data"])
            assert data["observable_only"] is True
            assert socket_path.exists()


def test_native_dashboard_hostile_control_keeps_browser_alive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory(prefix="pab-", dir="/tmp") as socket_dir_raw:
        socket_dir = Path(socket_dir_raw)
        monkeypatch.setenv("AGENT_BROWSER_SOCKET_DIR", str(socket_dir))

        with Browser.from_session("py-dashboard-hostile") as browser:
            browser.dashboard.start()
            socket_path = socket_dir / "py-dashboard-hostile.sock"
            _send_dashboard_control(socket_path, b'{"id":"dash-nav","action":"navigate"}\n')

            assert browser.native.data("stream_status")["enabled"] is True


def test_native_dashboard_close_does_not_hang_on_partial_control_client() -> None:
    with tempfile.TemporaryDirectory(prefix="pab-", dir="/tmp") as socket_dir_raw:
        socket_dir = Path(socket_dir_raw)
        marker = socket_dir / "closed"
        session = "py-dashboard-partial"
        env = os.environ.copy()
        env["AGENT_BROWSER_SOCKET_DIR"] = str(socket_dir)
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        script = f"""
import socket
from pathlib import Path

from pyagentbrowser import Browser

socket_dir = Path({str(socket_dir)!r})
session = {session!r}
browser = Browser.from_session(session)
browser.dashboard.start()
client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
client.connect(str(socket_dir / f"{{session}}.sock"))
client.sendall(b'{{"id":"partial","action":"close"}}')
browser.close()
Path({str(marker)!r}).write_text("closed")
client.close()
"""
        proc = subprocess.Popen(
            [sys.executable, "-c", script],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate(timeout=3)
            raise AssertionError(
                "dashboard close hung with partial control client\n"
                f"stdout={stdout}\nstderr={stderr}"
            ) from None

        assert proc.returncode == 0, stderr
        assert marker.read_text() == "closed"


def test_native_dashboard_writes_configured_cli_version_sidecar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory(prefix="pab-", dir="/tmp") as socket_dir_raw:
        socket_dir = Path(socket_dir_raw)
        monkeypatch.setenv("AGENT_BROWSER_SOCKET_DIR", str(socket_dir))
        with Browser.from_session("py-dashboard-version") as browser:
            browser.dashboard.start(DashboardOptions(cli_version="999.888.777"))
            assert (socket_dir / "py-dashboard-version.version").read_text() == "999.888.777"


def test_native_dashboard_watchdog_removes_sidecars_after_parent_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory(prefix="pab-", dir="/tmp") as socket_dir_raw:
        socket_dir = Path(socket_dir_raw)
        marker = socket_dir / "ready.json"
        session = "py-dashboard-crash"
        env = os.environ.copy()
        env["AGENT_BROWSER_SOCKET_DIR"] = str(socket_dir)
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        script = f"""
import json
import os
from pathlib import Path

from pyagentbrowser import Browser

socket_dir = Path({str(socket_dir)!r})
session = {session!r}
browser = Browser.from_session(session)
browser.dashboard.start()
pid = (socket_dir / f"{{session}}.pid").read_text()
Path({str(marker)!r}).write_text(json.dumps({{"pid": pid}}))
os._exit(23)
"""
        proc = subprocess.Popen([sys.executable, "-c", script], env=env)
        try:
            assert proc.wait(timeout=5) == 23
            assert marker.exists()
            _wait_until(lambda: _dashboard_sidecars(socket_dir, session) == [], timeout=5)
        finally:
            if proc.poll() is None:
                proc.kill()


def test_native_dashboard_stream_result_reports_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory(prefix="pab-", dir="/tmp") as socket_dir_raw:
        socket_dir = Path(socket_dir_raw)
        monkeypatch.setenv("AGENT_BROWSER_SOCKET_DIR", str(socket_dir))

        with Browser.from_session("py-dashboard-result") as browser:
            browser.dashboard.start()
            port = int((socket_dir / "py-dashboard-result.stream").read_text())
            with closing(_websocket_connect(port)) as websocket:
                browser.native.data("stream_status")
                result = None
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    message = _websocket_recv_json(websocket, timeout=1)
                    if message.get("type") == "result" and message.get("action") == "stream_status":
                        result = message
                        break

            assert result is not None
            assert result["success"] is True


def test_native_errors_raise_typed_browser_error() -> None:
    with Browser() as browser, pytest.raises(BrowserError) as exc_info:
        browser.native.data("not_an_agent_browser_action")

    assert exc_info.value.action == "not_an_agent_browser_action"
    assert exc_info.value.response["success"] is False
    assert isinstance(exc_info.value.response["error"], str)
    assert exc_info.value.response["error"]


def test_native_tab_new_rejects_disallowed_url() -> None:
    with (
        Browser(session_options=BrowserSessionOptions(allowed_domains="example.com")) as browser,
        pytest.raises(BrowserError) as exc_info,
    ):
        browser.native.data("tab_new", url="https://evil.example")

    assert exc_info.value.action == "tab_new"
    assert "allowed domains" in str(exc_info.value)


def test_native_cookie_set_rejects_disallowed_domain() -> None:
    with (
        Browser(session_options=BrowserSessionOptions(allowed_domains="example.com")) as browser,
        pytest.raises(BrowserError) as exc_info,
    ):
        browser.cookies.set("session", "abc", domain="evil.example")

    assert exc_info.value.action == "cookies_set"
    assert "Cookie domain" in str(exc_info.value)


def test_native_confirmation_requires_matching_confirmation_id() -> None:
    with Browser(
        session_options=BrowserSessionOptions(confirm_actions=[CONFIRMABLE_ACTION])
    ) as browser:
        with pytest.raises(ActionConfirmationRequired) as exc_info:
            browser.native.data(CONFIRMABLE_ACTION)

        confirmation = exc_info.value
        assert confirmation.confirmation_id

        with pytest.raises(BrowserError) as wrong_id:
            browser.native.data("confirm", confirmation_id=f"{confirmation.confirmation_id}-wrong")
        assert "confirmation_id does not match" in str(wrong_id.value)


def test_native_confirmation_replays_with_matching_confirmation_id() -> None:
    with Browser(
        session_options=BrowserSessionOptions(confirm_actions=[CONFIRMABLE_ACTION])
    ) as browser:
        with pytest.raises(ActionConfirmationRequired) as exc_info:
            browser.native.data(CONFIRMABLE_ACTION)

        data = browser.confirm(exc_info.value)

    assert "enabled" in data


def test_native_confirmation_replay_rechecks_policy_deny(
    tmp_path: Path,
) -> None:
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps({"confirm": [CONFIRMABLE_ACTION]}))

    with Browser(session_options=BrowserSessionOptions(action_policy=policy)) as browser:
        with pytest.raises(ActionConfirmationRequired) as exc_info:
            browser.native.data(CONFIRMABLE_ACTION)

        policy.write_text(json.dumps({"deny": [CONFIRMABLE_ACTION]}))

        with pytest.raises(BrowserError) as denied:
            browser.confirm(exc_info.value)

    assert "denied by policy during confirmation" in str(denied.value)


def test_native_confirmation_replay_fails_closed_when_policy_is_invalid(
    tmp_path: Path,
) -> None:
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps({"confirm": [CONFIRMABLE_ACTION]}))

    with Browser(session_options=BrowserSessionOptions(action_policy=policy)) as browser:
        with pytest.raises(ActionConfirmationRequired) as exc_info:
            browser.native.data(CONFIRMABLE_ACTION)

        policy.write_text("{not-json")

        with pytest.raises(BrowserError) as denied:
            browser.confirm(exc_info.value)

    assert "denied by policy during confirmation" in str(denied.value)
    assert "Invalid policy JSON" in str(denied.value)


def test_native_confirmation_can_replay_after_policy_repair(
    tmp_path: Path,
) -> None:
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps({"confirm": [CONFIRMABLE_ACTION]}))

    with Browser(session_options=BrowserSessionOptions(action_policy=policy)) as browser:
        with pytest.raises(ActionConfirmationRequired) as exc_info:
            browser.native.data(CONFIRMABLE_ACTION)

        policy.write_text("{not-json")
        with pytest.raises(BrowserError):
            browser.confirm(exc_info.value)

        policy.write_text(json.dumps({"allow": [CONFIRMABLE_ACTION, "confirm", "close"]}))
        assert "enabled" in browser.confirm(exc_info.value)


def test_native_confirmation_replay_fails_closed_when_policy_is_deleted(
    tmp_path: Path,
) -> None:
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps({"confirm": [CONFIRMABLE_ACTION]}))

    with Browser(session_options=BrowserSessionOptions(action_policy=policy)) as browser:
        with pytest.raises(ActionConfirmationRequired) as exc_info:
            browser.native.data(CONFIRMABLE_ACTION)

        policy.unlink()

        with pytest.raises(BrowserError) as denied:
            browser.confirm(exc_info.value)

    assert "denied by policy during confirmation" in str(denied.value)
    assert "Failed to read policy file" in str(denied.value)


def test_native_confirmation_policy_cannot_bypass_python_url_allowlist() -> None:
    with (
        Browser(
            session_options=BrowserSessionOptions(
                allowed_domains="example.com",
                confirm_actions=["tab_new"],
            )
        ) as browser,
        pytest.raises(BrowserError) as denied,
    ):
        browser.native.data("tab_new", url="https://evil.example")

    assert denied.value.action == "tab_new"
    assert denied.value.code == "allowed_domains"
    assert "allowed domains" in str(denied.value)


def test_native_confirmation_policy_cannot_bypass_python_cookie_allowlist() -> None:
    with (
        Browser(
            session_options=BrowserSessionOptions(
                allowed_domains="example.com",
                confirm_actions=["cookies_set"],
            )
        ) as browser,
        pytest.raises(BrowserError) as denied,
    ):
        browser.cookies.set("session", "abc", domain="evil.example")

    assert denied.value.action == "cookies_set"
    assert denied.value.code == "allowed_domains"
    assert "Cookie domain 'evil.example'" in str(denied.value)


def test_native_confirmation_replay_fails_closed_for_unvalidated_allowlist_targets(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({"cookies": [], "origins": []}))

    with Browser(
        session_options=BrowserSessionOptions(
            allowed_domains="example.com",
            confirm_actions=["state_load"],
        )
    ) as browser:
        with pytest.raises(ActionConfirmationRequired) as exc_info:
            browser.state.load(state_path)

        with pytest.raises(BrowserError) as denied:
            browser.confirm(exc_info.value)

    assert denied.value.action == "confirm"
    assert "target cannot be validated against allowed domains" in str(denied.value)
