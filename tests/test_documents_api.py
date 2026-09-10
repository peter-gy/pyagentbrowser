from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fakes import ScriptedNative
from support.sdk import _browser

from agentbrowser import (
    AsyncBrowser,
    AsyncFrame,
    Browser,
    DocumentScope,
    ElementGeometry,
    Frame,
    FrameLookupError,
    Page,
    ScrollResult,
)
from agentbrowser.transport.async_ import AsyncNativeSession

pytestmark = pytest.mark.sdk_dx


def _frame_tree() -> dict[str, Any]:
    return {
        "frame": {"id": "main", "name": "", "url": "https://example.com"},
        "childFrames": [
            {
                "frame": {
                    "id": "preview",
                    "name": "preview",
                    "url": "https://example.com/preview",
                },
                "childFrames": [
                    {
                        "frame": {
                            "id": "story",
                            "name": "story",
                            "url": "https://example.com/story",
                        }
                    }
                ],
            }
        ],
    }


@pytest.mark.parametrize("browser_type,frame_type", [(Browser, Frame), (AsyncBrowser, AsyncFrame)])
def test_frame_handles_require_explicit_identity(browser_type: Any, frame_type: Any) -> None:
    browser = browser_type()
    with pytest.raises(TypeError, match="frame_id"):
        frame_type(browser.extension(lambda executor: executor))
    for frame_id in (None, "", " ", 0):
        with pytest.raises(ValueError, match="non-empty string"):
            frame_type(browser.extension(lambda executor: executor), frame_id=frame_id)


def test_page_and_frame_handles_apply_explicit_native_scope() -> None:
    def frame_reply(command: dict[str, Any]) -> dict[str, Any]:
        if command.get("list"):
            return {"frameTree": _frame_tree()}
        return {"frame": "preview", "frameId": "preview"}

    def evaluate_reply(command: dict[str, Any]) -> dict[str, Any]:
        if "querySelector" in command["script"]:
            return {"result": 1}
        return {"result": "Preview", "origin": "https://example.com/preview"}

    native = ScriptedNative(
        {
            "frame": frame_reply,
            "snapshot": {
                "snapshot": "button Save [ref=e1]",
                "origin": "https://example.com/preview",
                "refs": {"e1": {"role": "button", "name": "Save"}},
            },
            "evaluate": evaluate_reply,
        }
    )
    browser = _browser(native)

    assert isinstance(browser.page, Page)
    frame = browser.page.frames.get(selector="#preview")
    snapshot = frame.observe()
    title = frame.evaluate("document.title")

    assert isinstance(frame, Frame)
    assert frame.frame_id == "preview"
    assert snapshot.document == frame
    assert snapshot.one(role="button", name="Save").content_frame
    assert title == "Preview"
    assert native.commands[0]["_frameId"] == ""
    assert native.commands[1]["_frameId"] == ""
    assert native.commands[2]["_frameId"] == ""
    assert native.commands[3]["_frameId"] == "preview"
    assert native.commands[4]["_frameId"] == "preview"


def test_frame_tree_is_scoped_to_direct_children() -> None:
    native = ScriptedNative({"frame": {"frameTree": _frame_tree()}})
    browser = _browser(native)

    preview = browser.page.frames.get(name="preview")
    story = preview.frames.get(name="story")

    assert preview.parent_frame_id == "main"
    assert story.parent_frame_id == "preview"


def test_frame_lookup_error_exposes_reason_and_bounded_candidates() -> None:
    native = ScriptedNative({"frame": {"frameTree": _frame_tree()}})
    browser = _browser(native)

    with pytest.raises(FrameLookupError) as missing:
        browser.page.frames.get(name="missing")

    assert missing.value.reason == "not_found"
    assert missing.value.candidates == (
        "preview name='preview' url='https://example.com/preview'",
        "story name='story' url='https://example.com/story'",
    )


def test_frame_selector_rejects_multiple_iframe_elements() -> None:
    native = ScriptedNative(
        {
            "frame": {"frameTree": _frame_tree()},
            "evaluate": {"result": 2},
        }
    )
    browser = _browser(native)

    with pytest.raises(FrameLookupError) as ambiguous:
        browser.page.frames.get(selector="iframe[title='Preview']")

    assert ambiguous.value.reason == "ambiguous"


def test_frame_command_maps_detached_context_failure() -> None:
    native = ScriptedNative(
        {
            "evaluate": {
                "success": False,
                "code": "frame_detached",
                "error": "frame execution context detached",
            }
        }
    )
    browser = _browser(native)
    frame = Frame(browser.extension(lambda executor: executor), frame_id="detached")

    with pytest.raises(FrameLookupError) as detached:
        frame.evaluate("document.title")

    assert detached.value.reason == "detached"


def test_scroll_returns_measured_scope_and_offsets() -> None:
    native = ScriptedNative(
        {
            "evaluate": {
                "result": {"before": {"x": 0, "y": 100}, "after": {"x": 0, "y": 700}},
                "origin": "https://example.com",
                "targetId": "A" * 16,
            }
        }
    )
    browser = _browser(native)

    result = browser.page.scroll.by(y=600, selector="#results")

    assert isinstance(result, ScrollResult)
    assert result.container == "#results"
    assert result.before.y == 100
    assert result.after.y == 700
    assert result.moved
    assert result.scope.target_id == "A" * 16


def test_geometry_reports_bounds_and_overflow() -> None:
    native = ScriptedNative(
        {
            "evaluate": {
                "result": {
                    "x": 10,
                    "y": 20,
                    "width": 390,
                    "height": 844,
                    "clientWidth": 390,
                    "clientHeight": 844,
                    "scrollWidth": 420,
                    "scrollHeight": 1200,
                },
                "origin": "https://example.com",
                "targetId": "A" * 16,
            }
        }
    )
    browser = _browser(native)

    geometry = browser.page.geometry("main")

    assert isinstance(geometry, ElementGeometry)
    assert geometry.overflows_x and geometry.overflows_y
    assert geometry.scope == DocumentScope("A" * 16, url="https://example.com")


def test_async_frame_handles_apply_the_same_explicit_scope() -> None:
    def frame_reply(command: dict[str, Any]) -> dict[str, Any]:
        if command.get("list"):
            return {"frameTree": _frame_tree()}
        return {"frame": "preview", "frameId": "preview"}

    def evaluate_reply(command: dict[str, Any]) -> dict[str, Any]:
        if "querySelector" in command["script"]:
            return {"result": 1}
        return {"result": "Preview", "origin": "https://example.com/preview"}

    native = ScriptedNative(
        {
            "frame": frame_reply,
            "evaluate": evaluate_reply,
        },
        default={},
    )

    async def run() -> None:
        browser = AsyncBrowser(_native_session=AsyncNativeSession(native=native))
        frame = await browser.page.frames.get(selector="#preview")

        assert isinstance(frame, AsyncFrame)
        assert await frame.evaluate("document.title") == "Preview"
        assert native.commands[-1]["_frameId"] == "preview"
        await browser.close()

    asyncio.run(run())
