from __future__ import annotations

import html
import json
import time
from collections.abc import Iterator
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import quote

import pytest

from agentbrowser import Browser, BrowserError, LaunchOptions, SessionOptions, StaleRefError

pytestmark = pytest.mark.integration


@pytest.fixture
def frame_site(tmp_path: Path) -> Iterator[str]:
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=tmp_path)
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_frame_capture_clips_every_ancestor_viewport(
    chrome_path: Path, tmp_path: Path, frame_site: str
) -> None:
    def document(content: str, color: str) -> str:
        return (
            f"<style>html,body{{margin:0;background:{color}}}"
            f"iframe{{border:0;position:absolute}}</style>{content}"
        )

    def frame(url: str, style: str) -> str:
        return f'<iframe style="{style}" src="{url}"></iframe>'

    other_site = frame_site.replace("127.0.0.1", "localhost")
    inner = document("<script>window.ready = true</script>", "red")
    middle = document(
        frame(f"{other_site}/inner.html", "left:10px;top:20px;width:500px;height:400px"), "blue"
    )
    outer = document(
        frame(f"{frame_site}/middle.html", "left:20px;top:30px;width:400px;height:300px"), "green"
    )
    page = document(
        '<div id="clip" style="position:absolute;left:40px;top:100px;'
        'width:240px;height:180px;overflow:hidden">'
        + frame(f"{other_site}/outer.html", "left:0;top:0;width:240px;height:180px")
        + "</div>",
        "white",
    )
    for name, content in {"inner": inner, "middle": middle, "outer": outer, "index": page}.items():
        (tmp_path / f"{name}.html").write_text(content)
    with Browser.launch(
        LaunchOptions(executable_path=chrome_path, headless=True),
        session=SessionOptions(session_id=f"frame-clipping-{time.monotonic_ns()}"),
    ) as browser:
        browser.page.open(f"{frame_site}/index.html")
        outer_frame = browser.page.frames.get(selector="iframe")
        middle_frame = outer_frame.frames.get(selector="iframe")
        inner_frame = middle_frame.frames.get(selector="iframe")
        inner_frame.wait_for_function("window.ready === true")
        # Cross-process projection requires more than one iframe CDP session.
        trees = browser.native.data("frame", list=True)["oopifFrameTrees"]
        assert isinstance(trees, list) and len(trees) >= 2
        screenshot = inner_frame.capture.screenshot(tmp_path / "clipped.png", wait_ms=0)
        image = screenshot.pil(mode="RGB")
        assert image.size == (210, 130)
        assert image.getpixel((0, 0)) == (255, 0, 0)
        assert image.getpixel((209, 129)) == (255, 0, 0)
        browser.page.evaluate("document.body.style.height = '2000px'; scrollTo(0, 200)")
        scrolled = inner_frame.capture.screenshot(tmp_path / "scrolled.png", wait_ms=0).pil(
            mode="RGB"
        )
        assert scrolled.size == (210, 80)
        assert scrolled.getpixel((0, 0)) == (255, 0, 0)
        assert scrolled.getpixel((209, 79)) == (255, 0, 0)
        browser.page.evaluate(
            "scrollTo(0, 0); Object.assign(document.querySelector('#clip').style, "
            "{width: '180px', height: '120px'})"
        )
        clipped = inner_frame.capture.screenshot(tmp_path / "overflow.png", wait_ms=0).pil(
            mode="RGB"
        )
        assert clipped.size == (150, 70)
        assert clipped.getpixel((149, 69)) == (255, 0, 0)
        browser.page.evaluate("document.querySelector('#clip').style.transform = 'rotate(10deg)'")
        with pytest.raises(BrowserError, match="axis-aligned transforms"):
            inner_frame.capture.screenshot(tmp_path / "rotated.png", wait_ms=0)


def test_external_frame_navigation_expires_snapshot_refs(chrome_path: Path) -> None:
    original = '<button onclick="window.clicked=true">Run</button><h1>Original document</h1>'
    replacement = '<button onclick="window.clicked=true">Run</button><h1>Replacement document</h1>'
    page = f'<iframe srcdoc="{html.escape(original, quote=True)}"></iframe>'
    with Browser.launch(
        LaunchOptions(executable_path=chrome_path, headless=True),
        session=SessionOptions(session_id=f"frame-navigation-{time.monotonic_ns()}"),
    ) as browser:
        browser.page.open("data:text/html," + quote(page))
        frame = browser.page.frames.get(selector="iframe")
        reference = frame.observe().one(role="button", name="Run")
        browser.page.evaluate(
            f"document.querySelector('iframe').srcdoc = {json.dumps(replacement)}"
        )
        frame.wait_for_text("Replacement document")
        with pytest.raises(StaleRefError):
            reference.click()
        assert frame.evaluate("Boolean(window.clicked)") is False


def test_typed_refs_keep_captured_node_identity(chrome_path: Path) -> None:
    markup = '<button onclick="window.clicked=true">Run</button>'
    with Browser.launch(
        LaunchOptions(executable_path=chrome_path, headless=True),
        session=SessionOptions(session_id=f"ref-identity-{time.monotonic_ns()}"),
    ) as browser:
        browser.page.open("data:text/html," + quote(markup))
        reference = browser.page.observe().one(role="button", name="Run")
        browser.page.evaluate(f"document.querySelector('button').outerHTML = {json.dumps(markup)}")
        with pytest.raises(StaleRefError):
            reference.text()
        with pytest.raises(StaleRefError):
            reference.click()
        assert browser.page.evaluate("Boolean(window.clicked)") is False
        browser.native.data("click", selector=reference.selector)
        assert browser.page.evaluate("Boolean(window.clicked)") is True


def test_stale_native_ref_replay_preserves_the_active_tab(chrome_path: Path) -> None:
    with Browser.launch(
        LaunchOptions(executable_path=chrome_path, headless=True),
        session=SessionOptions(session_id=f"ref-replay-{time.monotonic_ns()}"),
    ) as browser:
        browser.page.open("data:text/html," + quote("<title>First</title><button>Run</button>"))
        first = browser.page
        snapshot = first.observe()
        reference = snapshot.one(role="button", name="Run")
        browser.tabs.new("data:text/html," + quote("<title>Second</title>"))
        with pytest.raises(BrowserError) as caught:
            browser.native.data(
                "click",
                selector=reference.selector,
                _refGeneration=snapshot.generation,
                _targetId=first.target_id,
                _frameId="",
            )
        assert caught.value.code == "stale_ref"
        assert browser.native.data("evaluate", script="document.title")["result"] == "Second"
