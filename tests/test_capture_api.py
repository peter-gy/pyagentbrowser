from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fakes import ScriptedNative
from support.sdk import _browser

from agentbrowser import (
    DocumentScope,
    NativeParseError,
)

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
