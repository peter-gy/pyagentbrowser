from __future__ import annotations

import pytest

from agentbrowser.cdp import (
    CDPContextNotFoundError,
    CDPFrameNotFoundError,
    CDPPageSession,
    CDPStaleObjectError,
)
from tests.support.cdp_transport import (
    FakeCDPTransport,
    _context_event,
)

pytestmark = pytest.mark.sdk_dx


def test_frame_context_selects_default_context() -> None:
    page = _extension_context_page()
    frame = page.frame()

    default_context = frame.context()

    assert default_context.unique_id == "main-unique"
    assert frame.evaluate("window.answer") == "context:main-unique"


def test_frame_context_selects_extension_context() -> None:
    page = _extension_context_page()
    frame = page.frame()
    extension_context = frame.context(extension_id="abcdefghijklmnop")

    assert extension_context.unique_id == "extension-unique"
    assert extension_context.evaluate("window.__MY_EXTENSION_STATE__") == (
        "context:extension-unique"
    )


def test_frame_context_reports_missing_extension_context() -> None:
    page = _extension_context_page()
    frame = page.frame()

    with pytest.raises(CDPContextNotFoundError):
        frame.context(extension_id="missing")


def test_frame_selector_resolves_iframe() -> None:
    transport = FakeCDPTransport()
    page = CDPPageSession(transport, session_id="s1", target_id="target")
    page.enable()

    frame = page.frame(selector="#target-frame")

    assert frame.id == "child"
    assert frame.name == "target"
    assert frame.url == "https://example.com/frame"


def test_frame_selector_reports_missing_iframe() -> None:
    page = CDPPageSession(FakeCDPTransport(), session_id="s1", target_id="target")
    page.enable()

    with pytest.raises(CDPFrameNotFoundError, match="no iframe matched"):
        page.frame(selector="#missing-frame")


def test_frame_selector_reports_non_frame_match() -> None:
    page = CDPPageSession(FakeCDPTransport(), session_id="s1", target_id="target")
    page.enable()

    with pytest.raises(CDPFrameNotFoundError, match="did not resolve to a frame node"):
        page.frame(selector="#not-a-frame")


def test_frame_returns_main_frame_by_default() -> None:
    page = CDPPageSession(FakeCDPTransport(), session_id="s1", target_id="target")
    page.enable()

    assert page.frame().id == "main"


def test_frames_list_returns_current_frame_tree() -> None:
    page = CDPPageSession(FakeCDPTransport(), session_id="s1", target_id="target")
    page.enable()

    frames = page.frames()
    frames_by_id = {frame.id: frame for frame in frames}

    assert frames_by_id["main"].url == "https://example.com"
    assert frames_by_id["child"].name == "target"
    assert frames_by_id["child"].url == "https://example.com/frame"


def test_stale_frame_errors_after_invalidation() -> None:
    page = CDPPageSession(FakeCDPTransport(), session_id="s1", target_id="target")
    page.enable()
    frame = page.frame()

    page.invalidate()

    with pytest.raises(CDPStaleObjectError, match="frame is stale"):
        frame.evaluate("location.href")


def _extension_context_page() -> CDPPageSession:
    transport = FakeCDPTransport()
    transport.events = [
        _context_event(1, "main-unique", "main", is_default=True),
        _context_event(
            2,
            "extension-unique",
            "main",
            origin="chrome-extension://abcdefghijklmnop",
            name="chrome-extension://abcdefghijklmnop/content.js",
            context_type="isolated",
            is_default=False,
        ),
    ]
    page = CDPPageSession(transport, session_id="s1", target_id="target")
    page.enable()
    return page
