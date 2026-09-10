from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentbrowser import (
    BrowserError,
    HarContentMode,
)
from agentbrowser.cdp import CDPStaleObjectError
from tests.support.browser import (
    _browser,
    _data_url,
)
from tests.support.browser_site import LocalSite
from tests.support.browser_site import local_site as local_site

pytestmark = pytest.mark.integration


def test_recording_retains_the_active_page_and_survives_invalid_restart(
    chrome_path: Path,
    tmp_path: Path,
) -> None:
    ffprobe = shutil.which("ffprobe")
    assert ffprobe and shutil.which("ffmpeg"), "Recording contracts require FFmpeg and ffprobe"
    path = tmp_path / "active-page.webm"
    with _browser(chrome_path) as browser:
        browser.page.open(_data_url('<input id="draft">'))
        browser.page.evaluate("document.getElementById('draft').value = 'unsaved'")
        active = next(tab for tab in browser.tabs.list() if tab.active)
        frame = browser.cdp.frames.get()
        started = browser.native.data("recording_start", path=str(path), fps=12)

        assert started["fps"] == 12
        assert next(tab for tab in browser.tabs.list() if tab.active).target_id == active.target_id
        assert frame.evaluate("document.getElementById('draft').value") == "unsaved"
        with pytest.raises(BrowserError, match="Invalid fps"):
            browser.native.data("recording_restart", path=str(tmp_path / "invalid.webm"), fps=0)
        assert frame.evaluate("document.getElementById('draft').value") == "unsaved"
        browser.page.evaluate(
            """new Promise(resolve => {
  let frames = 0;
  function paint() {
    document.getElementById('draft').value = String(++frames);
    if (frames === 12) resolve();
    else requestAnimationFrame(paint);
  }
  requestAnimationFrame(paint);
})"""
        )
        stopped = browser.native.data("recording_stop")

    assert stopped["path"] == str(path)
    assert stopped["fps"] == 12
    probe = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-count_frames",
            "-show_entries",
            "stream=codec_name,r_frame_rate,nb_read_frames",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    stream = json.loads(probe.stdout)["streams"][0]
    assert stream["codec_name"] == "vp8"
    assert stream["r_frame_rate"] == "12/1"
    assert int(stream["nb_read_frames"]) > 0


def test_recording_restart_navigation_invalidates_held_cdp_frames(
    chrome_path: Path,
    tmp_path: Path,
) -> None:
    with _browser(chrome_path) as browser:
        browser.page.open(_data_url("<title>First take</title>"))
        browser.native.data("recording_start", path=str(tmp_path / "first.webm"))
        frame = browser.cdp.frames.get()
        restarted = browser.native.data(
            "recording_restart",
            path=str(tmp_path / "second.webm"),
            url=_data_url("<title>Second take</title>"),
        )

        assert restarted["fps"] == 30
        assert browser.page.title() == "Second take"
        with pytest.raises(CDPStaleObjectError, match="stale"):
            frame.evaluate("document.title")
        browser.page.evaluate(
            """new Promise(resolve => {
  let frames = 0;
  function paint() {
    document.body.textContent = String(++frames);
    if (frames === 12) resolve();
    else requestAnimationFrame(paint);
  }
  requestAnimationFrame(paint);
})"""
        )
        stopped = browser.native.data("recording_stop")
        assert stopped["path"] == str(tmp_path / "second.webm")


@pytest.mark.parametrize(("content_mode", "embeds_text"), [("text", True), ("none", False)])
def test_har_content_mode_controls_response_body_capture(
    chrome_path: Path,
    local_site: LocalSite,
    tmp_path: Path,
    content_mode: HarContentMode,
    embeds_text: bool,
) -> None:
    payload = {"message": f"captured-{content_mode}"}
    payload_name = f"payload-{content_mode}.json"
    page_name = f"har-{content_mode}.html"
    (local_site.root / payload_name).write_text(json.dumps(payload))
    (local_site.root / page_name).write_text(
        "<script>"
        f"fetch('/{payload_name}').then(response => response.json()).then(payload => {{"
        "document.body.textContent = payload.message;"
        "document.body.dataset.loaded = 'true';"
        "});"
        "</script>"
    )

    with _browser(chrome_path) as browser:
        browser.network.har_start(content=content_mode)
        browser.page.open(f"{local_site.base_url}/{page_name}")
        browser.page.wait_for_function("document.body.dataset.loaded === 'true'")
        har_path = browser.network.har_stop(tmp_path / f"{content_mode}.har")

    har = json.loads(har_path.read_text())
    entry = next(
        item for item in har["log"]["entries"] if item["request"]["url"].endswith(payload_name)
    )
    content = entry["response"]["content"]
    assert ("text" in content) is embeds_text
    if embeds_text:
        assert json.loads(content["text"]) == payload
