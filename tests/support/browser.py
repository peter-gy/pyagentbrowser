from __future__ import annotations

import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

from agentbrowser import (
    Browser,
    LaunchOptions,
    SessionOptions,
)


def _session(prefix: str = "pytest") -> SessionOptions:
    return SessionOptions(
        session_id=f"{prefix}-{time.monotonic_ns()}",
        timeout=5.0,
    )


def _browser(chrome_path: Path, *, session: SessionOptions | None = None) -> Browser:
    return Browser.launch(
        LaunchOptions(executable_path=chrome_path),
        session=session or _session(),
    )


def _data_url(html: str) -> str:
    return "data:text/html;charset=utf-8," + quote(html)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_cdp(port: int, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urlopen(f"http://127.0.0.1:{port}/json/version", timeout=0.5) as response:
                return response.status == 200
        except Exception:
            time.sleep(0.1)
    return False


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def _form_html() -> str:
    return """
    <!doctype html>
    <title>Agent workflow</title>
    <label>Name <input id="name"></label>
    <button id="go">Greet</button>
    <output id="out"></output>
    <script>
      document.querySelector("#go").addEventListener("click", () => {
        document.querySelector("#out").textContent =
          `Hello, ${document.querySelector("#name").value}`;
      });
    </script>
    """
