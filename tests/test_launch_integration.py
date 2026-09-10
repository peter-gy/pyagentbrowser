from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path

import pytest

from agentbrowser import (
    Browser,
    BrowserError,
    LaunchOptions,
    SessionOptions,
)
from tests.support.browser import (
    _browser,
    _session,
)
from tests.support.browser_site import LocalSite
from tests.support.browser_site import local_site as local_site
from tests.support.browser_tls import LocalHttpsSite
from tests.support.browser_tls import local_https_site as local_https_site

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


def test_allowed_domains_support_a_fresh_local_browser(
    chrome_path: Path,
    local_site: LocalSite,
) -> None:
    session = SessionOptions(
        session_id=f"allowlist-{time.monotonic_ns()}",
        timeout=5.0,
        allowed_domains=("127.0.0.1",),
    )

    with _browser(chrome_path, session=session) as browser:
        browser.page.open(local_site.base_url)
        assert browser.page.url().startswith(local_site.base_url)


@pytest.mark.parametrize("new_tab_via_click", [False, True], ids=["tab_new", "click"])
def test_new_tabs_inherit_setup_before_first_navigation_and_share_init_script_handles(
    chrome_path: Path,
    local_site: LocalSite,
    new_tab_via_click: bool,
) -> None:
    (local_site.root / "setup.html").write_text(
        """<a id="next" href="/setup.html">Next</a>
<script>
window.firstDocument = {
  marker: window.initialized ?? null,
  userAgent: navigator.userAgent,
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
};
</script>"""
    )
    url = f"{local_site.base_url}/setup.html"
    with _browser(chrome_path) as browser:
        browser.page.open(url)
        script = browser.native.data("addinitscript", script="window.initialized = 'ready'")
        browser.native.data("useragent", userAgent="pyagentbrowser-integration")
        browser.native.data("timezone", timezoneId="America/New_York")
        if new_tab_via_click:
            browser.native.data("click", selector="#next", newTab=True)
        else:
            browser.tabs.new(url)

        assert browser.page.evaluate("window.firstDocument") == {
            "marker": "ready",
            "userAgent": "pyagentbrowser-integration",
            "timezone": "America/New_York",
        }
        browser.native.data("removeinitscript", identifier=script["identifier"])
        browser.page.open(url)
        assert browser.page.evaluate("window.firstDocument.marker") is None
        if new_tab_via_click:
            browser.native.data("click", selector="#next", newTab=True)
        else:
            browser.tabs.new(url)
        assert browser.page.evaluate("window.firstDocument.marker") is None


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
        browser.page.open(local_site.base_url)
        result = browser.page.evaluate(_WEBGPU_RENDER_PROBE)

    assert result == {"stage": "pixel", "pixel": [255, 0, 0, 255]}


def test_private_ca_trust_and_clear_cross_the_native_browser_boundary(
    local_https_site: LocalHttpsSite,
    request: pytest.FixtureRequest,
) -> None:
    if sys.platform != "linux":
        options = LaunchOptions(
            executable_path=Path("C:/chrome.exe"),
            ca_cert=local_https_site.ca_certificate,
        )
        with pytest.raises(BrowserError, match="supported only on Linux"):
            Browser.launch(options, session=_session("private-ca-platform"))
        return

    chrome_path = request.getfixturevalue("chrome_path")
    options = LaunchOptions(
        executable_path=chrome_path,
        ca_cert=local_https_site.ca_certificate,
    )
    if shutil.which("certutil") is None:
        with pytest.raises(BrowserError, match="certutil"):
            Browser.launch(options, session=_session("private-ca-certutil"))
        return

    with (
        _browser(chrome_path, session=_session("private-ca-baseline")) as browser,
        pytest.raises(BrowserError),
    ):
        browser.page.open(local_https_site.base_url)

    with Browser.launch(options, session=_session("private-ca")) as browser:
        browser.page.open(local_https_site.base_url)
        assert browser.page.title() == "Private CA"

        browser.native.data(
            "launch",
            executablePath=str(chrome_path),
            headless=True,
        )
        browser.page.open(local_https_site.base_url)
        assert browser.page.title() == "Private CA"

        browser.native.data(
            "launch",
            clearCaCert=True,
            executablePath=str(chrome_path),
            headless=True,
        )
        with pytest.raises(BrowserError):
            browser.page.open(local_https_site.base_url)
