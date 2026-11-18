import json
import os
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import parse_qs, urlsplit

from agentbrowser import Browser, LaunchOptions

PAGE = """<!doctype html>
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


class Catalog(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        url = urlsplit(self.path)
        if url.path == "/api/search":
            query = parse_qs(url.query).get("q", [""])[0]
            items = [{"id": 1, "title": f"{query} one"}, {"id": 2, "title": f"{query} two"}]
            self.reply("application/json", json.dumps({"query": query, "items": items}))
        else:
            self.reply("text/html; charset=utf-8", PAGE)

    def reply(self, content_type: str, body: str) -> None:
        payload = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        pass


server = ThreadingHTTPServer(("127.0.0.1", 0), Catalog)
Thread(target=server.serve_forever, daemon=True).start()
site = f"http://127.0.0.1:{server.server_port}"
os.environ["AGENT_BROWSER_FLOWS_DIR"] = tempfile.mkdtemp(prefix="flows-")

with Browser.launch(LaunchOptions(capture=["flow"])) as browser:
    browser.page.open(f"{site}/?q=stove", wait_until="networkidle")
    for step in browser.flows.steps().steps:
        print(step.seq, step.command, step.requests)

    saved = browser.flows.save("catalog-search", params={"q": "stove"})
    print(saved.params, saved.output, [request.url for request in saved.requests])

with Browser() as browser:
    run = browser.flows.run("catalog-search", params={"q": "lamp"}, fields=["title"])
    print(run.steps[0].tier, run.data)
    print(browser.is_launched)

server.shutdown()
