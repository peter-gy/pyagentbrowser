from __future__ import annotations

import time
from collections.abc import Iterable
from pathlib import Path
from typing import cast

import pytest

from agentbrowser import (
    ActionResult,
    BrowserError,
    ConfirmationRequired,
    SessionOptions,
    SnapshotDiff,
    Wait,
)
from tests.support.browser import (
    _browser,
    _data_url,
    _form_html,
)
from tests.support.browser_site import LocalSite
from tests.support.browser_site import local_site as local_site

pytestmark = pytest.mark.integration


def _write_frame_site(site: LocalSite) -> None:
    (site.root / "index.html").write_text(
        "<title>Host</title>"
        '<iframe title="Preview" hidden src="about:blank"></iframe>'
        '<iframe id="target" name="preview" title="Preview" src="/frame.html"></iframe>'
    )
    (site.root / "frame.html").write_text(
        "<title>Nested</title><h1>Nested frame</h1>"
        "<script>window.appState = 'preview-ready'</script>"
        '<iframe id="story" name="story" sandbox="allow-scripts" src="/story.html"></iframe>'
    )
    (site.root / "story.html").write_text(
        "<title>Story</title><button onclick=\"this.textContent='Changed'\">Change</button>"
        "<script>window.appState = 'story-ready'</script>"
        '<iframe id="deep" name="deep" '
        'srcdoc="<title>Deep</title><h2>Deep content</h2>'
        "<script>window.appState = &quot;deep-ready&quot;</script>"
        "<button onclick=&quot;this.textContent='Deep changed'&quot;>Deep action</button>"
        '"></iframe>'
        '<div style="height:2000px"></div>'
    )


def test_ref_action_returns_transition_evidence_across_the_native_boundary(
    chrome_path: Path,
) -> None:
    with _browser(chrome_path) as browser:
        browser.page.open(_data_url(_form_html()))
        browser.page.find.css("#name").fill("Ada")
        page = browser.page.observe()

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
        browser.page.open(f"{local_site.base_url}/index.html")
        frame = browser.cdp.frames.get(selector="#target")

        assert frame.url == f"{local_site.base_url}/frame.html"
        assert frame.evaluate("document.title") == "Nested"


def test_page_and_nested_frame_handles_keep_one_explicit_scope(
    chrome_path: Path,
    local_site: LocalSite,
) -> None:
    _write_frame_site(local_site)
    with _browser(chrome_path) as browser:
        browser.page.open(f"{local_site.base_url}/index.html")

        preview = browser.page.frames.get(selector="#target")
        preview.wait_for_text("Nested frame")
        assert {frame.frame_name for frame in preview.frames.tree()} == {"story", "deep"}
        story = preview.frames.get(selector="#story")
        deep = story.frames.get(selector="#deep")
        before = story.observe()
        result = before.one(role="button", name="Change").click(wait=Wait.text("Changed"))
        screenshot = story.capture.screenshot(
            local_site.root / "captures" / "story.png",
            wait_ms=0,
        )
        deep_screenshot = deep.capture.screenshot(
            local_site.root / "captures" / "deep.png",
            wait_ms=0,
        )
        movement = story.scroll.by(y=200)

        assert preview.title() == "Nested"
        assert preview.evaluate("window.appState") == "preview-ready"
        assert story.evaluate("window.appState") == "story-ready"
        assert deep.evaluate("Promise.resolve(window.appState)") == "deep-ready"
        assert story.title() == "Story"
        assert deep.title() == "Deep"
        assert deep.observe().one(role="heading", name="Deep content")
        deep_result = (
            deep.observe()
            .one(role="button", name="Deep action")
            .click(wait=Wait.text("Deep changed"))
        )
        assert deep_result.after.one(role="button", name="Deep changed")
        deep.find.css("button").click()
        deep.find.role("button", name="Deep changed").click()
        assert deep.find.css("button").text() == "Deep changed"
        with pytest.raises(BrowserError, match="Evaluation error"):
            deep.evaluate("throw new Error('deep failure')")
        assert result.after.one(role="button", name="Changed")
        assert movement.moved and movement.after.y > movement.before.y
        assert screenshot.scope is not None
        assert screenshot.scope.target_id
        assert screenshot.scope.frame_id == story.frame_id
        assert screenshot.scope.url == f"{local_site.base_url}/story.html"
        assert movement.scope.target_id == screenshot.scope.target_id
        assert movement.scope.frame_id == story.frame_id
        image = screenshot.pil(mode="RGB")
        assert 0 < image.width <= 300 and 0 < image.height <= 150
        pixels = cast(
            Iterable[tuple[int, int, int]],
            image.crop((0, 0, 140, 70)).get_flattened_data(),
        )
        assert any(sum(pixel) < 300 for pixel in pixels)
        deep_image = deep_screenshot.pil(mode="RGB")
        assert deep_image.width > 0 and deep_image.height > 0
        deep_pixels = cast(
            Iterable[tuple[int, int, int]],
            deep_image.get_flattened_data(),
        )
        assert any(sum(pixel) < 300 for pixel in deep_pixels)
        assert browser.page.title() == "Host"


def test_completed_page_load_wait_returns_after_navigation(
    chrome_path: Path,
    local_site: LocalSite,
) -> None:
    with _browser(chrome_path) as browser:
        browser.page.open(local_site.base_url)
        browser.page.wait_for_load_state("load")


def test_implicit_accessible_roles_resolve_through_live_queries(
    chrome_path: Path,
) -> None:
    with _browser(chrome_path) as browser:
        browser.page.open(_data_url("<h2>Skills</h2>"))

        assert browser.page.find.role("heading", name="skills").text() == "Skills"


def test_confirmation_completes_ref_transition_evidence(chrome_path: Path) -> None:
    html = "<title>Confirmation</title><button id='delete'>Delete</button>"
    session = SessionOptions(
        session_id=f"confirm-{time.monotonic_ns()}",
        timeout=5.0,
        confirm_actions=("click",),
    )
    with _browser(chrome_path, session=session) as browser:
        browser.page.open(_data_url(html))
        ref = browser.page.observe().one(name="Delete")

        with pytest.raises(ConfirmationRequired) as required:
            ref.click()

        result = required.value.pending.confirm()
        assert isinstance(result, ActionResult)
        assert result.action == "click"
        assert result.target is ref
        assert result.after.spec == ref.snapshot.spec
        assert isinstance(result.diff, SnapshotDiff)


def test_bound_page_gates_only_an_actual_target_switch(chrome_path: Path) -> None:
    session = SessionOptions(
        session_id=f"bound-page-policy-{time.monotonic_ns()}",
        confirm_actions=("tab_switch",),
    )
    with _browser(chrome_path, session=session) as browser:
        browser.page.set_content("<title>First</title>")
        first = browser.tabs.get(index=1)

        assert first.title() == "First"
        browser.tabs.new(_data_url("<title>Second</title>"))
        with pytest.raises(ConfirmationRequired) as required:
            first.title()

        assert required.value.data["action"] == "tab_switch"
        assert required.value.pending.confirm() == "First"
