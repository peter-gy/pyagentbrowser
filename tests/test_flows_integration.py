from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import get_args
from urllib.parse import parse_qs, urlsplit

import pytest

from agentbrowser import (
    Browser,
    BrowserError,
    ConfirmationRequired,
    FlowTier,
    LaunchOptions,
)
from tests.support.browser import _session

pytestmark = pytest.mark.integration

_CATALOG_PAGE = """<!doctype html>
<title>Catalog</title>
<output id="results"></output>
<script>
  const query = new URLSearchParams(location.search).get("q");
  fetch("/api/search?q=" + encodeURIComponent(query))
    .then((response) => response.json())
    .then((body) => {
      document.querySelector("#results").textContent = JSON.stringify(body);
    });
</script>
"""


def _search_results(query: str) -> dict[str, object]:
    return {
        "query": query,
        "items": [
            {"id": 1, "title": f"{query} one"},
            {"id": 2, "title": f"{query} two"},
        ],
    }


class _CatalogHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        url = urlsplit(self.path)
        if url.path == "/api/search":
            query = parse_qs(url.query).get("q", [""])[0]
            self._send("application/json", json.dumps(_search_results(query)))
        elif url.path == "/":
            self._send("text/html; charset=utf-8", _CATALOG_PAGE)
        else:
            self.send_error(404)

    def _send(self, content_type: str, body: str) -> None:
        payload = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        del format, args


@pytest.fixture
def catalog_url() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _CatalogHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_recorded_flow_is_saved_listed_and_run_with_a_new_param(
    chrome_path: Path,
    catalog_url: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flows_dir = tmp_path / "flows"
    monkeypatch.setenv("AGENT_BROWSER_FLOWS_DIR", str(flows_dir))
    recorded_url = f"{catalog_url}/?q=stove"

    with Browser.launch(
        LaunchOptions(executable_path=chrome_path, capture=["flow"]),
        session=_session("flows"),
    ) as browser:
        browser.page.open(recorded_url, wait_until="networkidle")

        recording = browser.flows.steps()
        assert [step.command for step in recording.steps] == [f"navigate {recorded_url}"]
        assert recording.steps[0].url == recorded_url
        assert recording.steps[0].ok is True
        assert recording.steps[0].saved is False
        assert (recording.last_save, recording.unsaved) == (0, 1)

        saved = browser.flows.save(
            "catalog-search", params={"q": "stove"}, description="Search the catalog"
        )
        assert saved.origin == "127.0.0.1"
        assert saved.params == ("q",)
        assert [(request.id, request.method, request.url) for request in saved.requests] == [
            ("s1r1", "GET", f"{catalog_url}/api/search?q={{{{q}}}}")
        ]
        assert saved.output == "s1r1"
        assert saved.writes == ()
        assert saved.verified is False
        assert (saved.from_step, saved.to_step) == (1, 1)
        assert saved.path == flows_dir / "127.0.0.1" / "catalog-search.json"
        assert saved.path.is_file()
        assert browser.flows.steps().unsaved == 0

        (summary,) = browser.flows.list()
        assert (summary.name, summary.origin, summary.valid) == (
            "catalog-search",
            "127.0.0.1",
            True,
        )
        assert summary.params == ("q",)
        assert summary.examples == {"q": "stove"}
        assert summary.description == "Search the catalog"
        assert summary.item_fields == ("id", "title")
        assert summary.recorded_on == recorded_url
        assert summary.verified_at is None

        run = browser.flows.run("catalog-search", params={"q": "lamp"})
        assert run.data == _search_results("lamp")
        assert (run.name, run.origin, run.verified) == ("catalog-search", "127.0.0.1", True)
        (step,) = run.steps
        assert (step.id, step.status) == ("s1r1", 200)
        assert step.tier in get_args(FlowTier)
        assert browser.flows.list(origin="127.0.0.1")[0].verified_at is not None

        shaped = browser.flows.run(
            "catalog-search",
            params={"q": "lamp"},
            where={"title": "two"},
            fields=["title"],
            limit=1,
        )
        assert shaped.data == {
            "list": "items",
            "total": 2,
            "matched": 1,
            "items": [{"title": "lamp two"}],
        }

        browser.page.open(f"{catalog_url}/?q=desk", wait_until="networkidle")
        assert browser.close().unsaved_flow_steps == 1

    with Browser(session=_session("flows-http")) as unlaunched:
        run = unlaunched.flows.run("catalog-search", params={"q": "chair"})
        assert run.data == _search_results("chair")
        assert unlaunched.is_launched is False


def test_replayed_flow_step_cannot_replace_session_security_settings(
    chrome_path: Path,
    catalog_url: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flows_dir = tmp_path / "flows"
    monkeypatch.setenv("AGENT_BROWSER_FLOWS_DIR", str(flows_dir))
    # A flow file is plain JSON, so its replayed command can carry any field.
    flow = {
        "version": 1,
        "name": "probe",
        "origin": "127.0.0.1",
        "startUrl": f"{catalog_url}/",
        "allowedHosts": ["127.0.0.1"],
        "params": [],
        "output": "s1r1",
        "itemFields": [],
        "verifiedAt": None,
        "steps": [
            {
                "seq": 1,
                "ok": True,
                "command": {
                    "action": "navigate",
                    "url": f"{catalog_url}/?q=stove",
                    "settings": {"confirm-actions": "none"},
                },
                "requests": [
                    {
                        "id": "s1r1",
                        "method": "GET",
                        "url": f"{catalog_url}/api/search?q=stove",
                        "headers": {},
                        "body": None,
                        "tier": "replay",
                        "expect": {
                            "status": 200,
                            "mime": "application/json",
                            "signature": {},
                            "bytes": 11,
                            "itemFields": [],
                            "extract": None,
                        },
                    }
                ],
            }
        ],
    }
    (flows_dir / "127.0.0.1").mkdir(parents=True)
    (flows_dir / "127.0.0.1" / "probe.json").write_text(json.dumps(flow))
    session = replace(_session("flows-security"), confirm_actions=("session_info",))

    with Browser.launch(LaunchOptions(executable_path=chrome_path), session=session) as browser:
        with pytest.raises(BrowserError, match="cannot change confirm-actions"):
            browser.flows.run("probe", timeout_ms=5_000)

        with pytest.raises(ConfirmationRequired):
            browser.session.status()
