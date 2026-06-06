from __future__ import annotations

import asyncio
import json
import socket
import subprocess
import time
from collections.abc import Iterator
from dataclasses import dataclass
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import quote
from urllib.request import urlopen

import pytest

import pyagentbrowser as ab
from pyagentbrowser import (
    ActionConfirmationRequired,
    AsyncBrowser,
    Browser,
    BrowserError,
    Screenshot,
    Snapshot,
)

pytestmark = pytest.mark.integration


@dataclass(frozen=True, slots=True)
class LocalSite:
    base_url: str
    root: Path


def _data_url(html: str) -> str:
    return "data:text/html;charset=utf-8," + quote(html)


def _async_form_html() -> str:
    return """
    <!doctype html>
    <html>
      <head><title>Async Agent Browser Python</title></head>
      <body>
        <label>Name <input id="name" /></label>
        <button id="go">Greet</button>
        <output id="out"></output>
        <script>
          document.querySelector("#go").addEventListener("click", () => {
            document.querySelector("#out").textContent =
              `Hello, ${document.querySelector("#name").value}`;
          });
        </script>
      </body>
    </html>
    """


def _sync_form_html() -> str:
    return """
    <!doctype html>
    <html>
      <head><title>Agent Browser Python</title></head>
      <body>
        <label>Name <input id="name" /></label>
        <button id="go">Greet</button>
        <output id="out"></output>
        <script>
          document.querySelector("#go").addEventListener("click", () => {
            document.querySelector("#out").textContent =
              `Hello, ${document.querySelector("#name").value}`;
          });
        </script>
      </body>
    </html>
    """


@pytest.fixture
def local_page(tmp_path: Path) -> Iterator[str]:
    html = """
    <!doctype html>
    <html>
      <head><title>Agent Browser Python</title></head>
      <body>
        <h1>Local page</h1>
      </body>
    </html>
    """
    (tmp_path / "index.html").write_text(html)

    handler = partial(SimpleHTTPRequestHandler, directory=tmp_path)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        yield f"http://127.0.0.1:{server.server_port}/index.html"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.fixture
def local_site(tmp_path: Path) -> Iterator[LocalSite]:
    handler = partial(SimpleHTTPRequestHandler, directory=tmp_path)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        yield LocalSite(base_url=f"http://127.0.0.1:{server.server_port}", root=tmp_path)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_cdp(port: int, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urlopen(
                f"http://127.0.0.1:{port}/json/version",
                timeout=0.5,
            ) as response:
                return response.status == 200
        except Exception:
            pass
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


def test_browser_actions_drive_real_page_through_native_rust_engine(chrome_path: Path) -> None:
    with Browser(executable_path=chrome_path, default_timeout_ms=5_000) as browser:
        browser.page.open(_data_url(_sync_form_html()))

        browser.find.css("#name").fill("Ada")
        browser.observe().find(role="button", name="Greet", exact=True).click()
        browser.page.wait_for_text("Hello, Ada")

        assert browser.find.css("#out").text() == "Hello, Ada"


def test_browser_page_title_reads_real_browser_title(chrome_path: Path) -> None:
    with Browser(executable_path=chrome_path, default_timeout_ms=5_000) as browser:
        browser.page.open(_data_url(_sync_form_html()))

        assert browser.page.title() == "Agent Browser Python"


def test_browser_page_evaluate_runs_javascript_in_real_browser(chrome_path: Path) -> None:
    with Browser(executable_path=chrome_path, default_timeout_ms=5_000) as browser:
        browser.page.open(_data_url(_sync_form_html()))

        assert browser.page.evaluate("document.title") == "Agent Browser Python"


def test_browser_snapshot_discovers_real_page_refs(chrome_path: Path) -> None:
    with Browser(executable_path=chrome_path, default_timeout_ms=5_000) as browser:
        browser.page.open(_data_url(_sync_form_html()))

        snapshot = browser.snapshot(interactive=True)

        assert isinstance(snapshot, Snapshot)
        assert "Greet" in snapshot.text
        assert any(ref["name"] == "Greet" for ref in snapshot.refs.values())


def _write_nested_frame_site(local_site: LocalSite, *, title: str = "Nested frame") -> None:
    (local_site.root / "index.html").write_text(
        """
        <!doctype html>
        <html>
          <head><title>Frame host</title></head>
          <body>
            <iframe id="target-frame" src="/frame.html"></iframe>
          </body>
        </html>
        """
    )
    (local_site.root / "frame.html").write_text(
        f"""
        <!doctype html>
        <html>
          <head><title>{title}</title></head>
          <body><h1>{title}</h1></body>
        </html>
        """
    )


def test_frames_get_evaluates_selected_iframe(
    chrome_path: Path,
    local_site: LocalSite,
) -> None:
    _write_nested_frame_site(local_site)
    expected_url = f"{local_site.base_url}/frame.html"
    with Browser(executable_path=chrome_path, default_timeout_ms=5_000) as browser:
        browser.page.open(f"{local_site.base_url}/index.html")

        frame = browser.frames.get(selector="#target-frame")

        assert frame.url == expected_url
        assert frame.evaluate("location.href") == expected_url


def test_cdp_frame_evaluate_uses_selected_iframe(
    chrome_path: Path,
    local_site: LocalSite,
) -> None:
    _write_nested_frame_site(local_site)
    with Browser(executable_path=chrome_path, default_timeout_ms=5_000) as browser:
        browser.page.open(f"{local_site.base_url}/index.html")

        assert browser.cdp.evaluate("document.title", frame="#target-frame") == "Nested frame"


def _write_default_session_page(local_site: LocalSite) -> None:
    (local_site.root / "index.html").write_text(
        """
        <!doctype html>
        <html>
          <head><title>Default session host</title></head>
          <body>
            <button id="go">Go</button>
            <output id="out"></output>
            <script>
              document.querySelector("#go").addEventListener("click", () => {
                document.querySelector("#out").textContent = "default clicked";
              });
            </script>
          </body>
        </html>
        """
    )


def test_default_session_page_namespace_drives_real_browser(
    chrome_path: Path,
    local_site: LocalSite,
) -> None:
    _write_default_session_page(local_site)
    ab.configure(executable_path=chrome_path, default_timeout_ms=5_000)

    try:
        ab.page.open(f"{local_site.base_url}/index.html")

        assert ab.page.title() == "Default session host"
    finally:
        ab.reset()


def test_default_session_find_namespace_drives_real_browser(
    chrome_path: Path,
    local_site: LocalSite,
) -> None:
    _write_default_session_page(local_site)
    ab.configure(executable_path=chrome_path, default_timeout_ms=5_000)

    try:
        ab.page.open(f"{local_site.base_url}/index.html")
        ab.find.css("#go").click()
        ab.page.wait_for_text("default clicked")

        assert ab.find.css("#out").text() == "default clicked"
    finally:
        ab.reset()


def test_default_session_capture_namespace_writes_screenshot(
    chrome_path: Path,
    local_site: LocalSite,
    tmp_path: Path,
) -> None:
    _write_default_session_page(local_site)
    ab.configure(executable_path=chrome_path, default_timeout_ms=5_000)

    try:
        ab.page.open(f"{local_site.base_url}/index.html")
        shot = ab.capture.screenshot(tmp_path / "default-session.png")

        assert shot.path.exists()
    finally:
        ab.reset()


def test_default_session_reset_creates_new_configured_browser(chrome_path: Path) -> None:
    first_browser = ab.configure(executable_path=chrome_path, default_timeout_ms=5_000)

    try:
        ab.reset()
        second_browser = ab.configure(executable_path=chrome_path, default_timeout_ms=5_000)
        assert second_browser is not first_browser
    finally:
        ab.reset()


def _write_default_frame_site(local_site: LocalSite) -> None:
    (local_site.root / "index.html").write_text(
        """
        <!doctype html>
        <html>
          <head><title>Default frame host</title></head>
          <body><iframe id="child" name="child-frame" src="/frame.html"></iframe></body>
        </html>
        """
    )
    (local_site.root / "frame.html").write_text(
        "<!doctype html><title>Default child</title><h1>Default child</h1>"
    )


def test_default_session_frames_list_discovers_real_frame(
    chrome_path: Path,
    local_site: LocalSite,
) -> None:
    _write_default_frame_site(local_site)
    ab.configure(executable_path=chrome_path, default_timeout_ms=5_000)
    try:
        ab.page.open(f"{local_site.base_url}/index.html")

        assert any(item.url.endswith("/frame.html") for item in ab.frames.list())
    finally:
        ab.reset()


def test_default_session_frames_selector_returns_real_frame(
    chrome_path: Path,
    local_site: LocalSite,
) -> None:
    _write_default_frame_site(local_site)
    ab.configure(executable_path=chrome_path, default_timeout_ms=5_000)
    try:
        ab.page.open(f"{local_site.base_url}/index.html")
        frame = ab.frames.get(selector="#child")

        assert frame.url.endswith("/frame.html")
    finally:
        ab.reset()


def test_default_session_frame_handle_evaluates_selected_frame(
    chrome_path: Path,
    local_site: LocalSite,
) -> None:
    _write_default_frame_site(local_site)
    ab.configure(executable_path=chrome_path, default_timeout_ms=5_000)
    try:
        ab.page.open(f"{local_site.base_url}/index.html")
        frame = ab.frames.get(selector="#child")

        assert frame.evaluate("document.title") == "Default child"
    finally:
        ab.reset()


def test_default_session_cdp_namespace_evaluates_selected_frame(
    chrome_path: Path,
    local_site: LocalSite,
) -> None:
    _write_default_frame_site(local_site)
    ab.configure(executable_path=chrome_path, default_timeout_ms=5_000)
    try:
        ab.page.open(f"{local_site.base_url}/index.html")

        assert ab.cdp.evaluate("document.title", frame="#child") == "Default child"
    finally:
        ab.reset()


def _write_named_frame_site(local_site: LocalSite) -> None:
    (local_site.root / "index.html").write_text(
        """
        <!doctype html>
        <html>
          <head><title>Frame host</title></head>
          <body>
            <h1>Frame host</h1>
            <iframe id="target-frame" name="target" src="/frame.html"></iframe>
          </body>
        </html>
        """
    )
    (local_site.root / "frame.html").write_text(
        "<!doctype html><title>Frame child</title><h1>Frame child</h1>"
    )


def test_frames_list_discovers_child_frame(
    chrome_path: Path,
    local_site: LocalSite,
) -> None:
    _write_named_frame_site(local_site)
    with Browser(executable_path=chrome_path, default_timeout_ms=5_000) as browser:
        browser.page.open(f"{local_site.base_url}/index.html")

        frames = browser.frames.list()

        assert any(frame.url.endswith("/frame.html") for frame in frames)


def test_frames_selector_lookup_returns_selected_frame(
    chrome_path: Path,
    local_site: LocalSite,
) -> None:
    _write_named_frame_site(local_site)
    with Browser(executable_path=chrome_path, default_timeout_ms=5_000) as browser:
        browser.page.open(f"{local_site.base_url}/index.html")

        child = browser.frames.get(selector="#target-frame")

        assert child.url.endswith("/frame.html")


def test_selected_frame_evaluates_in_real_browser(
    chrome_path: Path,
    local_site: LocalSite,
) -> None:
    _write_named_frame_site(local_site)
    with Browser(executable_path=chrome_path, default_timeout_ms=5_000) as browser:
        browser.page.open(f"{local_site.base_url}/index.html")

        child = browser.frames.get(selector="#target-frame")

        assert child.evaluate("document.title") == "Frame child"


def test_frames_switch_and_main_restore_snapshot_scope(
    chrome_path: Path,
    local_site: LocalSite,
) -> None:
    _write_named_frame_site(local_site)
    with Browser(executable_path=chrome_path, default_timeout_ms=5_000) as browser:
        browser.page.open(f"{local_site.base_url}/index.html")

        browser.frames.switch(name="target")
        child_snapshot = browser.snapshot(interactive=True).text
        browser.frames.main()
        host_snapshot = browser.snapshot(interactive=True).text

        assert "Frame child" in child_snapshot
        assert "Frame host" in host_snapshot


def _write_two_tab_site(local_site: LocalSite) -> tuple[str, str]:
    (local_site.root / "first.html").write_text("<!doctype html><title>First tab</title>")
    (local_site.root / "second.html").write_text("<!doctype html><title>Second tab</title>")
    return f"{local_site.base_url}/first.html", f"{local_site.base_url}/second.html"


def test_cdp_active_target_reresolves_after_navigation(
    chrome_path: Path,
    local_site: LocalSite,
) -> None:
    first_url, second_url = _write_two_tab_site(local_site)
    with Browser(executable_path=chrome_path, default_timeout_ms=5_000) as browser:
        browser.page.open(first_url)
        assert browser.cdp.evaluate("document.title") == "First tab"

        browser.page.open(second_url)
        assert browser.cdp.evaluate("document.title") == "Second tab"


def test_cdp_target_label_selects_requested_tab(
    chrome_path: Path,
    local_site: LocalSite,
) -> None:
    first_url, second_url = _write_two_tab_site(local_site)
    with Browser(executable_path=chrome_path, default_timeout_ms=5_000) as browser:
        browser.page.open(second_url)
        browser.tabs.new(first_url, label="first")

        assert browser.cdp.target(label="First tab").evaluate("document.title") == "First tab"


def test_cdp_target_url_selects_requested_tab(
    chrome_path: Path,
    local_site: LocalSite,
) -> None:
    first_url, second_url = _write_two_tab_site(local_site)
    with Browser(executable_path=chrome_path, default_timeout_ms=5_000) as browser:
        browser.page.open(second_url)
        browser.tabs.new(first_url, label="first")

        assert browser.cdp.target(url=second_url).evaluate("document.title") == "Second tab"


def test_cdp_root_namespace_follows_tab_switch(
    chrome_path: Path,
    local_site: LocalSite,
) -> None:
    first_url, second_url = _write_two_tab_site(local_site)
    with Browser(executable_path=chrome_path, default_timeout_ms=5_000) as browser:
        browser.page.open(second_url)
        browser.tabs.new(first_url, label="first")

        browser.tabs.switch("first")

        assert browser.page.title() == "First tab"
        assert browser.cdp.evaluate("document.title") == "First tab"


def test_screenshot_writes_file(chrome_path: Path, tmp_path: Path) -> None:
    with Browser(executable_path=chrome_path) as browser:
        browser.page.open(_data_url("<title>Shot</title><h1>Screenshot</h1>"))
        shot = browser.capture.screenshot(tmp_path / "page.png")

    assert isinstance(shot, Screenshot)
    assert shot.path == tmp_path / "page.png"
    assert shot.path.exists()
    assert shot.path.stat().st_size > 0


def test_screenshot_wait_ms_allows_delayed_paint(chrome_path: Path, tmp_path: Path) -> None:
    from PIL import Image

    html = """
    <!doctype html>
    <html>
      <head><title>Delayed screenshot paint</title></head>
      <body style="margin:0;background:white">
        <div id="box" style="width:200px;height:200px;background:white"></div>
        <script>
          setTimeout(() => {
            document.querySelector("#box").style.background = "rgb(220, 0, 0)";
          }, 75);
        </script>
      </body>
    </html>
    """

    with Browser(executable_path=chrome_path) as browser:
        browser.page.open(_data_url(html))
        browser.set_viewport(200, 200)
        shot = browser.capture.screenshot(tmp_path / "delayed-paint.png", wait_ms=200)

    image = Image.open(shot.path).convert("RGB")
    assert image.getpixel((100, 100)) == (220, 0, 0)


def _semantic_helpers_html() -> str:
    return """
    <!doctype html>
    <html>
      <head><title>Semantic helpers</title></head>
      <body>
        <label>Name <input id="name-input" /></label>
        <button id="go">Greet</button>
        <output id="out"></output>
        <script>
          document.querySelector("#go").addEventListener("click", () => {
            document.querySelector("#out").textContent =
              `Hello, ${document.querySelector("#name-input").value}`;
          });
        </script>
      </body>
    </html>
    """


def test_label_locator_fill_drives_real_browser_output(chrome_path: Path) -> None:
    with Browser(executable_path=chrome_path, default_timeout_ms=5_000) as browser:
        browser.page.open(_data_url(_semantic_helpers_html()))
        browser.page.ready(min_text_length=len("Name Greet"))

        browser.find.label("Name").fill("Ada")
        browser.find.css("#go").click()
        browser.page.wait_for_text("Hello, Ada")

        assert browser.find.css("#out").text() == "Hello, Ada"


def test_role_locator_click_drives_real_browser_output(chrome_path: Path) -> None:
    with Browser(executable_path=chrome_path, default_timeout_ms=5_000) as browser:
        browser.page.open(_data_url(_semantic_helpers_html()))
        browser.page.ready(min_text_length=len("Name Greet"))

        browser.find.css("#name-input").fill("Ada")
        browser.find.role("button", name="Greet", exact=True).click()
        browser.page.wait_for_text("Hello, Ada")

        assert browser.find.css("#out").text() == "Hello, Ada"


def test_upload_sets_real_file_input(chrome_path: Path, tmp_path: Path) -> None:
    upload_path = tmp_path / "note.txt"
    upload_path.write_text("agent-browser upload")
    html = """
    <!doctype html>
    <html>
      <head><title>Upload helper</title></head>
      <body>
        <input id="file-input" type="file" />
        <output id="file-out"></output>
        <script>
          document.querySelector("#file-input").addEventListener("change", () => {
            document.querySelector("#file-out").textContent =
              document.querySelector("#file-input").files[0]?.name || "";
          });
        </script>
      </body>
    </html>
    """

    with Browser(executable_path=chrome_path, default_timeout_ms=5_000) as browser:
        browser.page.open(_data_url(html))

        browser.command("upload", selector="#file-input", files=[str(upload_path)])
        browser.page.wait_for_text("note.txt")

        assert browser.find.css("#file-out").text() == "note.txt"


def test_diff_snapshot_reports_real_page_change(chrome_path: Path) -> None:
    html = """
    <!doctype html>
    <html>
      <head><title>Diff helper</title></head>
      <body>
        <button id="go">Greet</button>
        <output id="out"></output>
        <script>
          document.querySelector("#go").addEventListener("click", () => {
            document.querySelector("#out").textContent = "Hello, Ada";
          });
        </script>
      </body>
    </html>
    """

    with Browser(executable_path=chrome_path, default_timeout_ms=5_000) as browser:
        browser.page.open(_data_url(html))
        baseline = browser.snapshot(interactive=True)
        browser.find.role("button", name="Greet", exact=True).click()
        browser.page.wait_for_text("Hello, Ada")

        diff = browser.diff_snapshot(baseline)

        assert browser.find.css("#out").text() == "Hello, Ada"
        assert diff.changed is True
        assert "Hello, Ada" in diff.text


def test_action_evidence_uses_real_snapshot_refs(chrome_path: Path) -> None:
    html = """
    <!doctype html>
    <html>
      <head><title>Evidence</title></head>
      <body>
        <button id="target">Submit</button>
        <output id="out"></output>
        <script>
          function wire() {
            document.querySelector("#target").addEventListener("click", () => {
              document.querySelector("#out").textContent = "Clicked";
            });
          }
          wire();
        </script>
      </body>
    </html>
    """

    with Browser(executable_path=chrome_path, default_timeout_ms=5_000) as browser:
        browser.page.open(_data_url(html))
        page = browser.observe()

        ref = page.find(role="button", name="Submit", exact=True)
        evidence = ref.click_and_observe(wait_for_text="Clicked")

        assert evidence.target == ref.selector
        assert evidence.diff.changed is True
        assert browser.find.css("#out").text() == "Clicked"


def test_confirmation_replay_uses_upstream_real_browser(chrome_path: Path) -> None:
    html = """
    <!doctype html>
    <html>
      <head><title>Confirm</title></head>
      <body>
        <button id="delete">Delete</button>
        <output id="out"></output>
        <script>
          document.querySelector("#delete").addEventListener("click", () => {
            document.querySelector("#out").textContent = "Deleted";
          });
        </script>
      </body>
    </html>
    """

    with Browser(
        executable_path=chrome_path,
        confirm_actions=["click"],
        default_timeout_ms=5_000,
    ) as browser:
        browser.page.open(_data_url(html))

        with pytest.raises(ActionConfirmationRequired) as exc_info:
            browser.find.css("#delete").click()

        confirmation = exc_info.value
        assert confirmation.confirmation_id
        browser.confirm(confirmation)
        browser.page.wait_for_text("Deleted")

        assert browser.find.css("#out").text() == "Deleted"


@pytest.mark.upstream_boundary
@pytest.mark.xfail(
    reason=(
        "upstream responsebody currently races Network.getResponseBody. "
        "pyagentbrowser treats responsebody as an upstream-owned native behavior"
    ),
    strict=True,
)
def test_response_body_is_upstream_owned(
    chrome_path: Path,
    local_site: LocalSite,
) -> None:
    (local_site.root / "index.html").write_text(
        "<!doctype html><title>Response body</title><h1>Response body</h1>"
    )
    (local_site.root / "api").mkdir()
    (local_site.root / "api" / "body").write_text("body from server")

    with Browser(executable_path=chrome_path, default_timeout_ms=5_000) as browser:
        browser.page.open(f"{local_site.base_url}/index.html")
        browser.page.evaluate("setTimeout(() => fetch('/api/body'), 50); 'scheduled'")
        body = browser.command("responsebody", url="/api/body")

    assert body["body"] == "body from server"


def test_network_route_drives_real_browser(
    chrome_path: Path,
    local_site: LocalSite,
) -> None:
    (local_site.root / "index.html").write_text(
        """
        <!doctype html>
        <html>
          <head><title>Network route</title></head>
          <body>
            <button id="fetch">Fetch</button>
            <output id="out"></output>
            <script>
              document.querySelector("#fetch").addEventListener("click", async () => {
                const response = await fetch("/api/message");
                document.querySelector("#out").textContent = await response.text();
              });
            </script>
          </body>
        </html>
        """
    )

    with Browser(executable_path=chrome_path, default_timeout_ms=5_000) as browser:
        browser.page.open(f"{local_site.base_url}/index.html")
        browser.network.route("*api/message", body="from route", content_type="text/plain")
        browser.find.css("#fetch").click()
        browser.page.wait_for_text("from route")

        assert browser.find.css("#out").text() == "from route"


def test_download_helper_writes_real_file(
    chrome_path: Path,
    local_site: LocalSite,
    tmp_path: Path,
) -> None:
    (local_site.root / "index.html").write_text(
        """
        <!doctype html>
        <html>
          <head><title>Download helper</title></head>
          <body><a id="download" href="/download.txt" download>Download</a></body>
        </html>
        """
    )
    (local_site.root / "download.txt").write_text("downloaded by agent-browser")
    download_path = tmp_path / "downloaded.txt"

    with Browser(executable_path=chrome_path, default_timeout_ms=5_000) as browser:
        browser.launch(download_path=tmp_path)
        browser.page.open(f"{local_site.base_url}/index.html")
        downloaded = browser.downloads.download("#download", download_path)

        assert downloaded.exists()
        assert downloaded.read_text() == "downloaded by agent-browser"


def test_storage_state_round_trip_real_browser(
    chrome_path: Path,
    local_site: LocalSite,
    tmp_path: Path,
) -> None:
    (local_site.root / "index.html").write_text(
        "<!doctype html><title>State round trip</title><h1>State round trip</h1>"
    )
    state_path = tmp_path / "state.json"

    with Browser(executable_path=chrome_path, default_timeout_ms=5_000) as browser:
        browser.page.open(f"{local_site.base_url}/index.html")
        browser.storage.set("theme", "dark")
        saved = browser.state.save(state_path)
        browser.storage.clear()
        browser.state.load(saved)

        assert browser.storage.get("theme") == "dark"


def test_cookie_state_round_trip_real_browser(
    chrome_path: Path,
    local_site: LocalSite,
    tmp_path: Path,
) -> None:
    (local_site.root / "index.html").write_text(
        "<!doctype html><title>Cookie round trip</title><h1>Cookie round trip</h1>"
    )
    state_path = tmp_path / "state.json"

    with Browser(executable_path=chrome_path, default_timeout_ms=5_000) as browser:
        browser.page.open(f"{local_site.base_url}/index.html")
        browser.cookies.set("pyagentbrowser", "yes", url=local_site.base_url)
        saved = browser.state.save(state_path)
        browser.cookies.clear()
        browser.state.load(saved)

        assert any(
            cookie.name == "pyagentbrowser" and cookie.value == "yes"
            for cookie in browser.cookies.get([local_site.base_url])
        )


def test_browser_can_attach_to_existing_chrome_cdp(chrome_path: Path, tmp_path: Path) -> None:
    port = _free_port()
    profile = tmp_path / "cdp-profile"
    process = subprocess.Popen(
        [
            str(chrome_path),
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile}",
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        if not _wait_for_cdp(port):
            pytest.skip("Chrome CDP endpoint did not become ready")

        with Browser(cdp_port=port, default_timeout_ms=5_000) as browser:
            browser.connect()
            assert browser.tabs.list()
            browser.page.open(_data_url("<title>Attached</title><h1>CDP attach</h1>"))

            assert browser.page.title() == "Attached"
    finally:
        _stop_process(process)


def test_default_configure_attaches_to_existing_chrome_cdp_before_navigation(
    chrome_path: Path,
    tmp_path: Path,
) -> None:
    port = _free_port()
    profile = tmp_path / "default-cdp-profile"
    process = subprocess.Popen(
        [
            str(chrome_path),
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile}",
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        if not _wait_for_cdp(port):
            pytest.skip("Chrome CDP endpoint did not become ready")

        browser = ab.configure(cdp_port=port, default_timeout_ms=5_000)

        assert browser.is_launched is True
        assert browser.tabs.list()
    finally:
        ab.reset()
        _stop_process(process)


def test_tabs_new_creates_labelled_tab_in_real_browser(
    chrome_path: Path,
    local_page: str,
) -> None:
    with Browser(executable_path=chrome_path, default_timeout_ms=5_000) as browser:
        browser.page.open(local_page)

        assert browser.tabs.list()
        browser.tabs.new(local_page, label="docs")

        assert any(tab.label == "docs" for tab in browser.tabs.list())


def test_tabs_switch_updates_active_real_browser_page(
    chrome_path: Path,
    local_page: str,
) -> None:
    with Browser(executable_path=chrome_path, default_timeout_ms=5_000) as browser:
        browser.page.open(local_page)
        browser.tabs.new(local_page, label="docs")

        browser.tabs.switch("docs")

        assert browser.page.title() == "Agent Browser Python"


def test_tabs_close_removes_labelled_tab_in_real_browser(
    chrome_path: Path,
    local_page: str,
) -> None:
    with Browser(executable_path=chrome_path, default_timeout_ms=5_000) as browser:
        browser.page.open(local_page)
        browser.tabs.new(local_page, label="docs")

        browser.tabs.close("docs")

        assert all(tab.label != "docs" for tab in browser.tabs.list())


def _write_mixed_storage_state(local_site: LocalSite, path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "cookies": [],
                "origins": [
                    {
                        "origin": local_site.base_url,
                        "localStorage": [{"name": "theme", "value": "dark"}],
                        "sessionStorage": [],
                    },
                    {
                        "origin": "https://evil.example",
                        "localStorage": [{"name": "token", "value": "secret"}],
                        "sessionStorage": [],
                    },
                ],
            }
        )
    )


def test_state_load_filters_storage_state_by_allowlist(
    chrome_path: Path,
    local_site: LocalSite,
    tmp_path: Path,
) -> None:
    (local_site.root / "index.html").write_text("<title>State</title><h1>State</h1>")
    state_path = tmp_path / "mixed-state.json"
    _write_mixed_storage_state(local_site, state_path)

    with Browser(
        executable_path=chrome_path,
        allowed_domains="127.0.0.1",
        default_timeout_ms=5_000,
    ) as browser:
        browser.page.open(f"{local_site.base_url}/index.html")
        browser.state.load(state_path)
        exported_path = browser.state.save(
            tmp_path / "loaded-state.json",
            unsafe_export_all=True,
        )
        assert browser.storage.get("theme") == "dark"

    exported = json.loads(exported_path.read_text())
    assert {origin["origin"] for origin in exported["origins"]} == {local_site.base_url}


def test_state_save_filters_storage_state_by_allowlist(
    chrome_path: Path,
    local_site: LocalSite,
    tmp_path: Path,
) -> None:
    (local_site.root / "index.html").write_text("<title>State</title><h1>State</h1>")
    state_path = tmp_path / "mixed-state.json"
    saved_path = tmp_path / "filtered-state.json"
    _write_mixed_storage_state(local_site, state_path)

    with Browser(
        executable_path=chrome_path,
        allowed_domains="127.0.0.1",
        default_timeout_ms=5_000,
    ) as browser:
        browser.page.open(f"{local_site.base_url}/index.html")
        browser.state.load(state_path, unsafe_import_all=True)
        browser.state.save(saved_path)

    saved = json.loads(saved_path.read_text())
    origins = {origin["origin"]: origin for origin in saved["origins"]}
    assert set(origins) == {local_site.base_url}
    storage = {item["name"]: item["value"] for item in origins[local_site.base_url]["localStorage"]}
    assert storage == {"theme": "dark"}


def test_browser_async_drives_real_page(chrome_path: Path) -> None:
    async def run() -> None:
        async with AsyncBrowser(executable_path=chrome_path, default_timeout_ms=5_000) as browser:
            await browser.page.open(_data_url(_async_form_html()))

            await browser.find.css("#name").fill("Ada")
            await (await browser.observe()).find(role="button", name="Greet", exact=True).click()
            await browser.page.wait_for_text("Hello, Ada")
            assert await browser.find.css("#out").text() == "Hello, Ada"

    asyncio.run(run())


def test_browser_async_wait_timeout_does_not_block_event_loop(chrome_path: Path) -> None:
    async def run() -> None:
        async with AsyncBrowser(executable_path=chrome_path, default_timeout_ms=5_000) as browser:
            await browser.page.open(_data_url(_async_form_html()))
            wait_task = asyncio.create_task(
                browser.page.wait_for_function(
                    "window.__pyagentbrowserNeverReady === true",
                    timeout_ms=500,
                )
            )

            async def ticker() -> int:
                ticks = 0
                for _ in range(5):
                    await asyncio.sleep(0.01)
                    ticks += 1
                return ticks

            tick_task = asyncio.create_task(ticker())
            done, _pending = await asyncio.wait(
                {tick_task, wait_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            assert tick_task in done
            assert wait_task not in done

            with pytest.raises(BrowserError):
                await wait_task

            assert tick_task.result() == 5
            assert await browser.page.title() == "Async Agent Browser Python"

    asyncio.run(run())


def test_async_capture_writes_screenshot_file(
    chrome_path: Path,
    local_site: LocalSite,
    tmp_path: Path,
) -> None:
    async def run() -> None:
        (local_site.root / "index.html").write_text(
            """
            <!doctype html>
            <html>
              <head><title>Async capture</title></head>
              <body><h1>Async capture</h1></body>
            </html>
            """
        )

        async with AsyncBrowser(executable_path=chrome_path, default_timeout_ms=5_000) as browser:
            await browser.page.open(f"{local_site.base_url}/index.html")
            shot = await browser.capture.screenshot(tmp_path / "async-capture.png")

            assert shot.path == tmp_path / "async-capture.png"
            assert shot.path.exists()
            assert shot.path.stat().st_size > 0

    asyncio.run(run())


def test_async_frames_get_evaluates_selected_frame(
    chrome_path: Path,
    local_site: LocalSite,
) -> None:
    async def run() -> None:
        _write_nested_frame_site(local_site, title="Async child")

        async with AsyncBrowser(executable_path=chrome_path, default_timeout_ms=5_000) as browser:
            await browser.page.open(f"{local_site.base_url}/index.html")
            frame = await browser.frames.get(selector="#target-frame")

            assert await frame.evaluate("document.title") == "Async child"

    asyncio.run(run())


def test_async_cdp_evaluate_uses_frame_selector(
    chrome_path: Path,
    local_site: LocalSite,
) -> None:
    async def run() -> None:
        _write_nested_frame_site(local_site, title="Async child")

        async with AsyncBrowser(executable_path=chrome_path, default_timeout_ms=5_000) as browser:
            await browser.page.open(f"{local_site.base_url}/index.html")

            assert await browser.cdp.evaluate("document.title", frame="#target-frame") == (
                "Async child"
            )

    asyncio.run(run())
