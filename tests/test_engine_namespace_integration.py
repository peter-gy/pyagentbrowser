from __future__ import annotations

import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

from agentbrowser import Browser, LaunchOptions, SessionOptions

pytestmark = pytest.mark.integration


def test_session_binding_persists_target_in_its_namespace(
    chrome_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    socket_dir = tmp_path / "sockets"
    monkeypatch.setenv("AGENT_BROWSER_SOCKET_DIR", str(socket_dir))
    (tmp_path / "page.html").write_text("<!doctype html><title>Namespace</title>")
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(tmp_path))
    )
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    url = f"http://127.0.0.1:{server.server_port}/page.html"
    try:
        with Browser.launch(
            LaunchOptions(executable_path=chrome_path),
            session=SessionOptions(session_id="research", namespace="Worker A"),
        ) as browser:
            browser.page.open(f"{url}?token=fixture#section")
            browser.native.data("url", pinTab=True)
            binding = json.loads(
                (socket_dir / "namespaces" / "worker-a" / "run" / "research.target").read_text()
            )

            assert binding["targetId"] == browser.page.target_id
            assert binding["url"] == url
            assert binding["pinned"] is True
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
