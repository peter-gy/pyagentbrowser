from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from fakes import ScriptedNative
from support.sdk import _browser

from agentbrowser import (
    AsyncBrowser,
    DocumentScope,
    NativeParseError,
    ScreenshotObservation,
)
from agentbrowser.transport.async_ import AsyncNativeSession

pytestmark = pytest.mark.sdk_dx


def test_screenshot_creates_artifact_directory_and_exposes_image_content(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "capture.png"

    def capture(_command: dict[str, Any]) -> dict[str, Any]:
        assert path.parent.is_dir()
        path.write_bytes(b"png-bytes")
        return {
            "path": str(path),
            "origin": "https://example.com",
            "targetId": "A" * 16,
        }

    native = ScriptedNative({"screenshot": capture})
    browser = _browser(native)

    screenshot = browser.page.capture.screenshot(path, wait_ms=0)

    assert path.parent.is_dir()
    assert screenshot.scope == DocumentScope("A" * 16, url="https://example.com")
    assert screenshot.content().data == b"png-bytes"
    assert screenshot.content().media_type == "image/png"


def test_screenshot_rejects_a_missing_native_path() -> None:
    browser = _browser(ScriptedNative({"screenshot": {}}))

    with pytest.raises(NativeParseError, match="path"):
        browser.page.capture.screenshot(wait_ms=0)


def test_screenshot_value_exposes_annotations_bytes_and_copy(tmp_path: Path) -> None:
    path = tmp_path / "shot.png"
    path.write_bytes(b"png-bytes")
    native = ScriptedNative(
        {
            "screenshot": {
                "path": str(path),
                "annotations": [
                    {
                        "ref": "e1",
                        "number": 1,
                        "role": "button",
                        "name": "Save",
                        "box": {"x": 1, "y": 2, "width": 30, "height": 12},
                    }
                ],
            }
        }
    )
    browser = _browser(native)

    shot = browser.page.capture.screenshot(path, annotate=True, wait_ms=0)
    copied = shot.save(tmp_path / "copy.png")

    assert shot.bytes() == b"png-bytes"
    assert shot.annotations[0].name == "Save"
    assert copied.bytes() == b"png-bytes"
    assert native.commands[0]["annotate"] is True


def test_conditional_screenshot_returns_written_and_unchanged_observations(
    tmp_path: Path,
) -> None:
    path = tmp_path / "conditional.png"
    calls = 0

    def capture(command: dict[str, Any]) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        assert command["ifChanged"] is True
        assert command["threshold"] == 0.1
        if calls == 1:
            path.write_bytes(b"png-bytes")
            return {
                "changed": True,
                "revision": 1,
                "pixelChangeRatio": 1.0,
                "threshold": 0.1,
                "path": str(path),
                "targetId": "A" * 16,
            }
        return {
            "changed": False,
            "revision": 2,
            "pixelChangeRatio": 0.0,
            "threshold": 0.1,
            "targetId": "A" * 16,
        }

    browser = _browser(ScriptedNative({"screenshot": capture}))

    first = browser.page.capture.screenshot_if_changed(path, threshold=0.1, wait_ms=0)
    second = browser.page.capture.screenshot_if_changed(path, threshold=0.1, wait_ms=0)

    assert isinstance(first, ScreenshotObservation)
    assert first.changed is True
    assert first.path == path
    assert first.screenshot is not None and first.screenshot.content().data == b"png-bytes"
    assert first.scope == DocumentScope("A" * 16)
    assert second.changed is False
    assert second.path is None
    assert second.screenshot is None
    assert second.revision == 2
    assert second.scope == first.scope


def test_conditional_screenshot_validates_threshold_and_matches_async_contract(
    tmp_path: Path,
) -> None:
    browser = _browser(ScriptedNative(default={}))
    with pytest.raises(ValueError, match="between 0 and 1"):
        browser.page.capture.screenshot_if_changed(threshold=1.1, wait_ms=0)

    async def run() -> ScreenshotObservation:
        native = ScriptedNative(
            {
                "screenshot": {
                    "changed": False,
                    "revision": 3,
                    "pixelChangeRatio": 0.01,
                    "threshold": 0.2,
                },
                "__agent_browser_internal_shutdown": {},
            }
        )
        async with AsyncBrowser(_native_session=AsyncNativeSession(native=native)) as async_browser:
            result = await async_browser.page.capture.screenshot_if_changed(
                tmp_path / "async.png", threshold=0.2, wait_ms=0
            )
        assert native.commands[0]["ifChanged"] is True
        return result

    observation = asyncio.run(run())
    assert observation.changed is False
    assert observation.revision == 3
