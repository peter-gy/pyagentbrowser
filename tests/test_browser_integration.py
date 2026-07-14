from __future__ import annotations

import asyncio
import socket
import subprocess
import sys
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

from agentbrowser import (
    ActionResult,
    AsyncBrowser,
    Browser,
    BrowserError,
    CDPTarget,
    ConfirmationRequired,
    LaunchOptions,
    RestoreOptions,
    SessionOptions,
    SessionStatus,
    SnapshotDiff,
)

pytestmark = pytest.mark.integration

_WEBGPU_RENDER_PROBE = r"""(async () => {
  const withTimeout = (promise, label) => Promise.race([
    Promise.resolve(promise),
    new Promise((_, reject) => setTimeout(
      () => reject(new Error(label + " timed out")),
      10000,
    )),
  ]);
  try {
    if (!window.isSecureContext) return {stage: "context"};
    if (!navigator.gpu) return {stage: "api"};
    let adapter = null;
    for (let attempt = 0; attempt < 5 && !adapter; attempt++) {
      if (attempt > 0) await new Promise(resolve => setTimeout(resolve, 1000));
      adapter = await withTimeout(navigator.gpu.requestAdapter(), "requestAdapter");
    }
    if (!adapter) return {stage: "adapter"};
    const device = await withTimeout(adapter.requestDevice(), "requestDevice");
    const texture = device.createTexture({
      size: [1, 1],
      format: "rgba8unorm",
      usage: GPUTextureUsage.RENDER_ATTACHMENT | GPUTextureUsage.COPY_SRC,
    });
    const buffer = device.createBuffer({
      size: 256,
      usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ,
    });
    const encoder = device.createCommandEncoder();
    const pass = encoder.beginRenderPass({colorAttachments: [{
      view: texture.createView(),
      clearValue: {r: 1, g: 0, b: 0, a: 1},
      loadOp: "clear",
      storeOp: "store",
    }]});
    pass.end();
    encoder.copyTextureToBuffer(
      {texture},
      {buffer, bytesPerRow: 256},
      [1, 1],
    );
    device.queue.submit([encoder.finish()]);
    await withTimeout(buffer.mapAsync(GPUMapMode.READ), "mapAsync");
    const pixel = Array.from(new Uint8Array(buffer.getMappedRange()).slice(0, 4));
    buffer.unmap();
    buffer.destroy();
    texture.destroy();
    device.destroy();
    return {stage: "pixel", pixel};
  } catch (error) {
    return {stage: "error", error: String(error && error.message || error)};
  }
})()"""


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


def _write_frame_site(site: LocalSite) -> None:
    (site.root / "index.html").write_text(
        '<title>Host</title><iframe id="target" src="/frame.html"></iframe>'
    )
    (site.root / "frame.html").write_text("<title>Nested</title><h1>Nested frame</h1>")


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


def _wait_for_restore_save(browser: Browser, timeout: float = 6.0) -> SessionStatus:
    deadline = time.monotonic() + timeout
    latest: SessionStatus | None = None
    while time.monotonic() < deadline:
        latest = browser.session.status()
        if latest.save_status == "saved":
            return latest
        time.sleep(0.1)
    pytest.fail(f"restore state was not autosaved: {latest}")


def test_ref_action_returns_transition_evidence_across_the_native_boundary(
    chrome_path: Path,
) -> None:
    with _browser(chrome_path) as browser:
        browser.open(_data_url(_form_html()))
        browser.find.css("#name").fill("Ada")
        page = browser.observe()

        result = page.one(role="button", name="Greet").click()

        assert isinstance(result, ActionResult)
        assert result.action == "click"
        assert result.before is page
        assert result.target.name == "Greet"
        assert result.after.spec == page.spec
        assert isinstance(result.diff, SnapshotDiff)


def test_cdp_frame_resolution_uses_the_active_native_target(
    chrome_path: Path,
    local_site: LocalSite,
) -> None:
    _write_frame_site(local_site)
    with _browser(chrome_path) as browser:
        browser.open(f"{local_site.base_url}/index.html")
        frame = browser.cdp.frames.get(selector="#target")

        assert frame.url == f"{local_site.base_url}/frame.html"
        assert frame.evaluate("document.title") == "Nested"


def test_webgpu_launch_preset_renders_offscreen_pixels_across_native_boundary(
    chrome_path: Path,
    local_site: LocalSite,
) -> None:
    args: tuple[str, ...] = ()
    if sys.platform == "win32":
        # WARP gives GPU-less runners the D3D11 device Chrome needs before
        # Dawn can discover the SwiftShader WebGPU adapter.
        args = (
            "--use-angle=d3d11-warp",
            "--use-webgpu-adapter=swiftshader",
        )
    session = SessionOptions(
        session_id=f"webgpu-{time.monotonic_ns()}",
        timeout=90.0,
    )
    with Browser.launch(
        LaunchOptions(executable_path=chrome_path, webgpu=True, args=args),
        session=session,
    ) as browser:
        browser.open(local_site.base_url)
        result = browser.evaluate(_WEBGPU_RENDER_PROBE)

    assert result == {"stage": "pixel", "pixel": [255, 0, 0, 255]}


def test_confirmation_completes_ref_transition_evidence(chrome_path: Path) -> None:
    html = "<title>Confirmation</title><button id='delete'>Delete</button>"
    session = SessionOptions(
        session_id=f"confirm-{time.monotonic_ns()}",
        timeout=5.0,
        confirm_actions=("click",),
    )
    with _browser(chrome_path, session=session) as browser:
        browser.open(_data_url(html))
        ref = browser.observe().one(name="Delete")

        with pytest.raises(ConfirmationRequired) as required:
            ref.click()

        result = required.value.pending.confirm()
        assert isinstance(result, ActionResult)
        assert result.action == "click"
        assert result.target is ref
        assert result.after.spec == ref.snapshot.spec
        assert isinstance(result.diff, SnapshotDiff)


def test_periodic_restore_autosave_survives_abrupt_browser_exit(
    chrome_path: Path,
    local_site: LocalSite,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = f"autosave-{time.monotonic_ns()}"
    session = SessionOptions(
        session_id=key,
        namespace=f"pytest-{key}",
        timeout=5.0,
        restore=RestoreOptions(key, save="always", autosave_interval_ms=100),
    )
    monkeypatch.setenv("AGENT_BROWSER_AUTOSAVE_INTERVAL_MS", "0")
    browser = _browser(chrome_path, session=session)
    saved_path: Path | None = None

    try:
        browser.open(local_site.base_url)
        browser.storage.set("periodic", "saved")
        time.sleep(2.2)
        status = _wait_for_restore_save(browser)
        saved_path = status.restore_saved_path
        assert saved_path is not None
        assert saved_path.is_file()

        browser.cdp.send("Browser.close")
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if not browser.session.status().browser_launched:
                break
            time.sleep(0.1)
        assert browser.session.status().browser_launched is False
    finally:
        browser.close()

    restored = _browser(chrome_path, session=session)
    try:
        restored.open(local_site.base_url)
        assert restored.session.status().restore_status == "loaded"
        assert restored.storage.get("periodic") == "saved"
    finally:
        restored.close()
        if saved_path is not None:
            saved_path.unlink(missing_ok=True)


def test_browser_attaches_to_an_existing_cdp_target(
    chrome_path: Path,
    tmp_path: Path,
) -> None:
    port = _free_port()
    process = subprocess.Popen(
        [
            str(chrome_path),
            f"--remote-debugging-port={port}",
            f"--user-data-dir={tmp_path / 'cdp-profile'}",
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
        with Browser.attach(CDPTarget(port=port), session=_session("attach")) as browser:
            browser.open(_data_url("<title>Attached</title>"))
            assert browser.title() == "Attached"
    finally:
        _stop_process(process)


def test_async_native_wait_does_not_block_the_event_loop(chrome_path: Path) -> None:
    async def run() -> None:
        browser = await AsyncBrowser.launch(
            LaunchOptions(executable_path=chrome_path),
            session=_session("async"),
        )
        async with browser:
            await browser.open(_data_url(_form_html()))
            wait_task = asyncio.create_task(
                browser.native.data(
                    "wait",
                    function="window.__neverReady === true",
                    timeout=500,
                )
            )

            async def ticker() -> int:
                for _ in range(5):
                    await asyncio.sleep(0.01)
                return 5

            tick_task = asyncio.create_task(ticker())
            done, _ = await asyncio.wait(
                {wait_task, tick_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            assert tick_task in done
            assert wait_task not in done
            with pytest.raises(BrowserError):
                await wait_task
            assert tick_task.result() == 5

    asyncio.run(run())
