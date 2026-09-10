from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest


@dataclass(frozen=True, slots=True)
class LocalSite:
    base_url: str
    root: Path


@pytest.fixture
def local_site(tmp_path: Path) -> Iterator[LocalSite]:
    handler = partial(SimpleHTTPRequestHandler, directory=tmp_path)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield LocalSite(f"http://127.0.0.1:{server.server_port}", tmp_path)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
