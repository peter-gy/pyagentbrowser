from __future__ import annotations

import asyncio
import json

import pytest
from fakes import AgentNative, StaleRefNative, TransitionSnapshotNative

from agentbrowser import (
    ActionEvidence,
    AgentSnapshot,
    AsyncAgentSnapshot,
    AsyncBrowser,
    AsyncStaleAgentRefError,
    Browser,
    BrowserError,
    StaleAgentRefError,
)
from agentbrowser.models import SnapshotDiff
from agentbrowser.session import NativeSession
from agentbrowser.session_async import AsyncNativeSession

pytestmark = pytest.mark.sdk_dx


class BoundRefNative:
    def __init__(self) -> None:
        self.email: str | None = None
        self.submitted = False

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        action = command["action"]
        if action == "snapshot":
            data = {
                "snapshot": '@e1 [button] "Submit"\n@e2 [input] "Email"',
                "origin": "https://example.com",
                "refs": {
                    "e1": {"role": "button", "name": "Submit"},
                    "e2": {"role": "textbox", "name": "Email"},
                },
            }
        elif action == "fill" and command.get("selector") == "@e2":
            self.email = str(command.get("value"))
            data = {}
        elif action == "click" and command.get("selector") == "@e1":
            if self.email != "ada@example.com":
                raise AssertionError("submit clicked before email was filled")
            self.submitted = True
            data = {}
        elif action == "title":
            data = {"title": "Submitted" if self.submitted else "Form"}
        else:
            raise AssertionError(f"unexpected bound ref command: {command}")
        return json.dumps({"id": command["id"], "success": True, "data": data})


def test_browser_observe_exposes_snapshot_refs() -> None:
    browser = Browser(native_session=NativeSession(native=BoundRefNative()))
    page = browser.observe()

    assert isinstance(page, AgentSnapshot)
    assert page.text.startswith("@e1")
    assert page.ref("e1").selector == "@e1"
    assert page.find(role="button", name="Submit", exact=True).name == "Submit"


def test_agent_refs_drive_actions_and_page_state() -> None:
    native = BoundRefNative()
    browser = Browser(native_session=NativeSession(native=native))
    page = browser.observe()
    email = page.find(name="Email")
    submit = page.ref("@e1")

    assert email.fill("ada@example.com") is email
    assert submit.click() is submit
    assert browser.page.title() == "Submitted"


def test_browser_snapshot_filters_malformed_native_refs() -> None:
    class MalformedRefNative:
        def execute_json(self, command_json: str) -> str:
            command = json.loads(command_json)
            return json.dumps(
                {
                    "id": command["id"],
                    "success": True,
                    "data": {
                        "snapshot": '@e1 [button] "Submit"',
                        "origin": "https://example.com",
                        "refs": {
                            "e1": {"role": "button", "name": "Submit"},
                            "broken": "not a ref object",
                        },
                    },
                }
            )

    browser = Browser(native_session=NativeSession(native=MalformedRefNative()))
    snapshot = browser.snapshot()

    assert snapshot.text == '@e1 [button] "Submit"'
    assert snapshot.origin == "https://example.com"
    assert snapshot.ref("@e1").selector == "@e1"
    assert "broken" not in snapshot.refs


class MatchRefsNative:
    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        if command["action"] != "snapshot":
            raise AssertionError(f"unexpected match-ref command: {command}")
        return json.dumps(
            {
                "id": command["id"],
                "success": True,
                "data": {
                    "snapshot": (
                        '@e1 [button] "Submit"\n'
                        '@e2 [button] "Submit form"\n'
                        '@e3 [link] "Submit docs"'
                    ),
                    "origin": "https://example.com",
                    "refs": {
                        "e1": {"role": "button", "name": "Submit"},
                        "e2": {"role": "button", "name": "Submit form"},
                        "e3": {"role": "link", "name": "Submit docs"},
                    },
                },
            }
        )


def _match_refs_page() -> AgentSnapshot:
    browser = Browser(native_session=NativeSession(native=MatchRefsNative()))
    return browser.observe()


def test_agent_snapshot_find_all_matches_role_and_partial_name() -> None:
    page = _match_refs_page()

    refs = page.find_all(role="button", name="Submit")

    assert {ref.selector for ref in refs} == {"@e1", "@e2"}


def test_agent_snapshot_find_matches_exact_name() -> None:
    page = _match_refs_page()

    assert page.find(role="button", name="Submit", exact=True).selector == "@e1"


def test_agent_snapshot_find_matches_contained_text() -> None:
    page = _match_refs_page()

    assert page.find(role="button", contains="form").selector == "@e2"


def test_agent_snapshot_find_can_return_first_non_strict_match() -> None:
    page = _match_refs_page()

    assert page.find(role="button", name="Submit", strict=False).selector == "@e1"


def test_agent_snapshot_find_raises_for_ambiguous_partial_match() -> None:
    page = _match_refs_page()

    with pytest.raises(LookupError, match="multiple refs"):
        page.find(role="button", name="Submit")


def test_agent_snapshot_find_raises_for_missing_ref() -> None:
    page = _match_refs_page()

    with pytest.raises(LookupError, match="no ref"):
        page.find(role="button", name="Missing")


def test_agent_ref_stale_ref_errors_are_not_replayed_implicitly() -> None:
    native = StaleRefNative()
    browser = Browser(native_session=NativeSession(native=native))

    ref = browser.observe().find(role="button", name="Submit", exact=True)

    with pytest.raises(StaleAgentRefError) as exc_info:
        ref.click()

    assert exc_info.value.ref is ref


def test_agent_ref_refresh_returns_live_ref_after_stale_error() -> None:
    native = StaleRefNative()
    browser = Browser(native_session=NativeSession(native=native))

    ref = browser.observe().find(role="button", name="Submit", exact=True)
    with pytest.raises(StaleAgentRefError):
        ref.click()

    refreshed = ref.refresh()

    assert refreshed.selector == "@e2"
    assert refreshed.click() is refreshed


def test_stale_agent_ref_error_can_refresh_explicitly() -> None:
    native = StaleRefNative()
    browser = Browser(native_session=NativeSession(native=native))

    with pytest.raises(StaleAgentRefError) as exc_info:
        browser.observe().find(role="button", name="Submit", exact=True).click()

    refreshed = exc_info.value.refresh()
    assert refreshed.selector == "@e2"
    assert refreshed.click() is refreshed


def test_stale_agent_ref_message_only_error_stays_browser_error() -> None:
    message_only = StaleRefNative(error="Unknown ref: e1", code=None)
    message_browser = Browser(native_session=NativeSession(native=message_only))
    message_ref = message_browser.observe().find(role="button", name="Submit", exact=True)

    with pytest.raises(BrowserError) as false_positive:
        message_ref.click()

    assert not isinstance(false_positive.value, StaleAgentRefError)
    assert false_positive.value.code is None


def test_stale_agent_ref_mapping_uses_structured_error_code() -> None:
    coded = StaleRefNative(error="Reference disappeared", code="unknown_ref")
    coded_browser = Browser(native_session=NativeSession(native=coded))
    coded_ref = coded_browser.observe().find(role="button", name="Submit", exact=True)

    with pytest.raises(StaleAgentRefError) as false_negative:
        coded_ref.click()

    assert false_negative.value.ref.selector == "@e1"


def test_agent_ref_action_evidence_returns_snapshot_shape() -> None:
    native = AgentNative()
    browser = Browser(native_session=NativeSession(native=native))

    evidence = browser.observe().find(role="button", name="Submit", exact=True).click_and_observe()

    assert isinstance(evidence, ActionEvidence)
    assert isinstance(evidence.before, AgentSnapshot)
    assert isinstance(evidence.after, AgentSnapshot)
    assert isinstance(evidence.diff, SnapshotDiff)


def test_agent_ref_action_evidence_records_action_target() -> None:
    native = AgentNative()
    browser = Browser(native_session=NativeSession(native=native))

    evidence = browser.observe().find(role="button", name="Submit", exact=True).click_and_observe()

    assert evidence.action == "click"
    assert evidence.target == "@e1"


def test_agent_ref_action_evidence_captures_before_snapshot() -> None:
    native = AgentNative()
    browser = Browser(native_session=NativeSession(native=native))

    evidence = browser.observe().find(role="button", name="Submit", exact=True).click_and_observe()

    assert evidence.before.find(role="button", name="Submit", exact=True).selector == "@e1"


def test_agent_ref_action_evidence_captures_native_diff() -> None:
    native = AgentNative()
    browser = Browser(native_session=NativeSession(native=native))

    evidence = browser.observe().find(role="button", name="Submit", exact=True).click_and_observe()

    assert evidence.diff.changed is True


def test_action_evidence_after_snapshot_is_fresh_and_usable() -> None:
    native = TransitionSnapshotNative()
    browser = Browser(native_session=NativeSession(native=native))

    evidence = browser.observe().find(role="button", name="Submit", exact=True).click_and_observe()
    refreshed = evidence.after.find(role="button", name="Continue", exact=True)

    assert evidence.before.origin == "https://example.com/form"
    assert evidence.after.origin == "https://example.com/done"
    assert refreshed.click() is refreshed


class WaitAwareNative:
    def __init__(self) -> None:
        self.snapshot_count = 0
        self.filled_value: str | None = None
        self.seen_text_wait = False
        self.seen_url_wait = False
        self.seen_load_wait = False

    @property
    def ready_for_after_snapshot(self) -> bool:
        return (
            self.filled_value == "Ada"
            and self.seen_text_wait
            and self.seen_url_wait
            and self.seen_load_wait
        )

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        action = command["action"]
        if action == "snapshot":
            self.snapshot_count += 1
            if self.snapshot_count == 1:
                data = {
                    "snapshot": '@e1 [button] "Submit"\n@e2 [input] "Email"',
                    "origin": "https://example.com/form",
                    "refs": {
                        "e1": {"role": "button", "name": "Submit"},
                        "e2": {"role": "textbox", "name": "Email"},
                    },
                }
            else:
                origin = (
                    "https://example.com/done"
                    if self.ready_for_after_snapshot and command.get("compact") is False
                    else "https://example.com/too-early"
                )
                data = {
                    "snapshot": '@e3 [button] "Continue"\n@e4 [text] "Saved"',
                    "origin": origin,
                    "refs": {
                        "e3": {"role": "button", "name": "Continue"},
                        "e4": {"role": "text", "name": "Saved"},
                    },
                }
        elif action == "fill":
            self.filled_value = str(command.get("value"))
            data = {}
        elif action == "wait":
            self.seen_text_wait = self.seen_text_wait or command.get("text") == "Saved"
            self.seen_url_wait = self.seen_url_wait or command.get("url") == "**/done"
            self.seen_load_wait = self.seen_load_wait or command.get("loadState") == "networkidle"
            data = {}
        elif action == "diff_snapshot":
            data = {
                "diff": '+ @e3 [button] "Continue"',
                "additions": 1,
                "removals": 1,
                "unchanged": 0,
                "changed": self.ready_for_after_snapshot and command.get("compact") is False,
            }
        else:
            data = {}
        return json.dumps({"id": command["id"], "success": True, "data": data})


def _fill_and_observe(native: WaitAwareNative) -> ActionEvidence:
    browser = Browser(native_session=NativeSession(native=native))
    return (
        browser.observe()
        .find(name="Email")
        .fill_and_observe(
            "Ada",
            wait_for_text="Saved",
            wait_for_url="**/done",
            wait_for_load_state="networkidle",
            compact=False,
        )
    )


def test_fill_and_observe_waits_before_after_snapshot() -> None:
    native = WaitAwareNative()

    evidence = _fill_and_observe(native)

    assert evidence.after.origin == "https://example.com/done"


def test_fill_and_observe_compact_false_returns_diff() -> None:
    native = WaitAwareNative()

    evidence = _fill_and_observe(native)

    assert evidence.diff.changed is True


def test_fill_and_observe_records_action_target() -> None:
    native = WaitAwareNative()

    evidence = _fill_and_observe(native)

    assert evidence.target == "@e2"


def test_fill_and_observe_returns_fresh_after_ref() -> None:
    native = WaitAwareNative()

    evidence = _fill_and_observe(native)

    assert evidence.after.find(role="button", name="Continue", exact=True).selector == "@e3"


def test_browser_async_observe_exposes_snapshot_refs() -> None:
    async def run() -> None:
        native = AgentNative()
        browser = AsyncBrowser(native_session=AsyncNativeSession(native=native))

        page = await browser.observe()
        assert page.ref("e1").selector == "@e1"
        assert page.find(role="button", name="Submit", exact=True).name == "Submit"
        await browser.aclose()

    asyncio.run(run())


def test_async_agent_ref_action_returns_same_handle() -> None:
    async def run() -> None:
        native = AgentNative()
        browser = AsyncBrowser(native_session=AsyncNativeSession(native=native))

        page = await browser.observe()
        ref = page.find(role="button", name="Submit", exact=True)
        clicked = await ref.click()
        assert clicked is ref
        await browser.aclose()

    asyncio.run(run())


def test_async_stale_agent_ref_error_can_refresh_explicitly() -> None:
    async def run() -> None:
        native = StaleRefNative()
        browser = AsyncBrowser(native_session=AsyncNativeSession(native=native))
        page = await browser.observe()
        ref = page.find(role="button", name="Submit", exact=True)

        with pytest.raises(AsyncStaleAgentRefError) as exc_info:
            await ref.click()

        refreshed = await exc_info.value.refresh()
        assert refreshed.selector == "@e2"
        clicked = await refreshed.click()
        assert clicked is refreshed
        await browser.aclose()

    asyncio.run(run())


def test_async_action_evidence_returns_snapshot_shape() -> None:
    async def run() -> None:
        native = TransitionSnapshotNative()
        browser = AsyncBrowser(native_session=AsyncNativeSession(native=native))

        page = await browser.observe()
        evidence = await page.find(role="button", name="Submit", exact=True).click_and_observe()

        assert isinstance(evidence.before, AsyncAgentSnapshot)
        assert isinstance(evidence.after, AsyncAgentSnapshot)
        assert isinstance(evidence.diff, SnapshotDiff)
        await browser.aclose()

    asyncio.run(run())


def test_async_action_evidence_records_action_target() -> None:
    async def run() -> None:
        native = TransitionSnapshotNative()
        browser = AsyncBrowser(native_session=AsyncNativeSession(native=native))

        page = await browser.observe()
        evidence = await page.find(role="button", name="Submit", exact=True).click_and_observe()

        assert evidence.target == "@e1"
        await browser.aclose()

    asyncio.run(run())


def test_async_action_evidence_after_snapshot_is_usable() -> None:
    async def run() -> None:
        native = TransitionSnapshotNative()
        browser = AsyncBrowser(native_session=AsyncNativeSession(native=native))

        page = await browser.observe()
        evidence = await page.find(role="button", name="Submit", exact=True).click_and_observe()
        after = evidence.after
        assert isinstance(after, AsyncAgentSnapshot)
        refreshed = after.find(role="button", name="Continue", exact=True)
        clicked = await refreshed.click()

        assert evidence.after.origin == "https://example.com/done"
        assert clicked is refreshed
        await browser.aclose()

    asyncio.run(run())
