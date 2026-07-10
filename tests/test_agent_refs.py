from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from agentbrowser import (
    ActionResult,
    ActionTransitionError,
    AsyncBrowser,
    AsyncSnapshot,
    Browser,
    BrowserError,
    ConfirmationRequired,
    NativeParseError,
    Snapshot,
    SnapshotSpec,
    StaleRefError,
    Wait,
)
from agentbrowser.session import NativeSession
from agentbrowser.session_async import AsyncNativeSession

pytestmark = pytest.mark.sdk_dx


def _snapshot(*, submitted: bool = False) -> dict[str, Any]:
    return {
        "snapshot": '@e1 [button] "Submit"\n@e2 [textbox] "Email"',
        "origin": "https://example.com/complete" if submitted else "https://example.com/form",
        "refs": {
            "e1": {"role": "button", "name": "Submit"},
            "e2": {"role": "textbox", "name": "Email"},
        },
    }


class TransitionNative:
    def __init__(self) -> None:
        self.commands: list[dict[str, Any]] = []
        self.submitted = False

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        self.commands.append(command)
        action = command["action"]
        if action == "snapshot":
            data = _snapshot(submitted=self.submitted)
        elif action == "click":
            self.submitted = True
            data = {}
        elif action == "wait":
            data = {}
        elif action in {"gettext", "isvisible"}:
            data = {"text": "Submit"} if action == "gettext" else {"visible": True}
        elif action == "__agent_browser_internal_shutdown":
            data = {
                "closed": True,
                "restoreStatus": "not_configured",
                "saveStatus": "not_configured",
            }
        else:
            raise AssertionError(f"unexpected transition command: {command}")
        return json.dumps({"id": command["id"], "success": True, "data": data})


class StaleNative(TransitionNative):
    def __init__(self, *, structured: bool) -> None:
        super().__init__()
        self.structured = structured
        self.attempts = 0

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        if command["action"] == "snapshot" and self.attempts > 0:
            self.commands.append(command)
            data = {
                "snapshot": '@e3 [button] "Submit"\n@e4 [textbox] "Email"',
                "origin": "https://example.com/form",
                "refs": {
                    "e3": {"role": "button", "name": "Submit"},
                    "e4": {"role": "textbox", "name": "Email"},
                },
            }
            return json.dumps({"id": command["id"], "success": True, "data": data})
        if command["action"] == "click":
            self.commands.append(command)
            self.attempts += 1
            if self.attempts == 1:
                response: dict[str, Any] = {
                    "id": command["id"],
                    "success": False,
                    "error": "selector was stale"
                    if self.structured
                    else "stale ref mentioned in prose",
                }
                if self.structured:
                    response["code"] = "stale_ref"
                return json.dumps(response)
        return super().execute_json(command_json)


class ConfirmedTransitionNative(TransitionNative):
    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        if command["action"] == "click":
            self.commands.append(command)
            data = {
                "confirmation_required": True,
                "confirmation_id": "confirm-click",
                "action": "click",
            }
            return json.dumps({"id": command["id"], "success": True, "data": data})
        if command["action"] == "confirm":
            self.commands.append(command)
            self.submitted = True
            data = {
                "confirmed": True,
                "action": "click",
                "result": {
                    "id": "confirmed-click",
                    "success": True,
                    "data": {},
                },
            }
            return json.dumps({"id": command["id"], "success": True, "data": data})
        return super().execute_json(command_json)


class ConfirmedRefReadNative(TransitionNative):
    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        if command["action"] == "gettext":
            self.commands.append(command)
            data = {
                "confirmation_required": True,
                "confirmation_id": "confirm-read",
                "action": "gettext",
            }
            return json.dumps({"id": command["id"], "success": True, "data": data})
        if command["action"] == "confirm":
            self.commands.append(command)
            data = {
                "confirmed": True,
                "action": "gettext",
                "result": {
                    "id": "confirmed-read",
                    "success": True,
                    "data": {"text": "Submit"},
                },
            }
            return json.dumps({"id": command["id"], "success": True, "data": data})
        return super().execute_json(command_json)


class WaitFailureNative(TransitionNative):
    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        if command["action"] == "wait":
            self.commands.append(command)
            return json.dumps(
                {
                    "id": command["id"],
                    "success": False,
                    "error": "timed out",
                }
            )
        return super().execute_json(command_json)


def _browser(native: Any) -> Browser:
    return Browser(_native_session=NativeSession(native=native))


def test_snapshot_binds_refs_and_expresses_cardinality() -> None:
    page = _browser(TransitionNative()).observe()

    assert isinstance(page, Snapshot)
    assert page.ref("@e1").selector == "@e1"
    assert page.one(role="textbox").name == "Email"
    assert tuple(ref.id for ref in page.all(contains="m")) == ("e1", "e2")

    with pytest.raises(LookupError, match="multiple"):
        page.one(contains="m")
    with pytest.raises(LookupError, match="no matching"):
        page.one(name="Missing")


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("snapshot", None, "snapshot.*string"),
        ("origin", None, "origin.*string"),
        ("refs", [], "refs.*object"),
        ("refs", {"e1": {"role": "button"}}, "role.*name"),
    ],
)
def test_snapshot_decoder_rejects_protocol_drift(
    field: str,
    value: object,
    message: str,
) -> None:
    data = _snapshot()
    data[field] = value

    class MalformedNative:
        def execute_json(self, command_json: str) -> str:
            command = json.loads(command_json)
            return json.dumps({"id": command["id"], "success": True, "data": data})

    with pytest.raises(NativeParseError, match=message):
        _browser(MalformedNative()).observe()


def test_ref_action_returns_reproducible_transition_evidence() -> None:
    native = TransitionNative()
    spec = SnapshotSpec(compact=True, urls=True)
    before = _browser(native).observe(spec)

    result = before.one(role="button", name="Submit").click(
        wait=Wait.all(Wait.text("Saved"), Wait.url("*/complete"))
    )

    assert isinstance(result, ActionResult)
    assert result.target.id == "e1"
    assert result.before is before
    assert result.after.spec is spec
    assert result.after.origin.endswith("/complete")
    assert result.diff.changed is True


def test_ref_reads_require_typed_native_fields() -> None:
    ref = _browser(TransitionNative()).observe().ref("e1")

    assert ref.text() == "Submit"
    assert ref.is_visible() is True


def test_confirmed_ref_read_keeps_its_public_type() -> None:
    ref = _browser(ConfirmedRefReadNative()).observe().ref("e1")

    with pytest.raises(ConfirmationRequired) as required:
        ref.text()

    assert required.value.pending.confirm() == "Submit"


def test_stale_ref_translation_uses_structured_error_codes() -> None:
    native = StaleNative(structured=True)
    browser = _browser(native)
    ref = browser.observe().one(name="Submit")

    with pytest.raises(StaleRefError) as stale:
        ref.click()

    refreshed = stale.value.refresh()
    assert refreshed.id == "e3"
    assert refreshed.snapshot is not ref.snapshot
    assert native.attempts == 1

    message_browser = _browser(StaleNative(structured=False))
    with pytest.raises(BrowserError) as error:
        message_browser.observe().one(name="Submit").click()
    assert not isinstance(error.value, StaleRefError)


def test_confirmed_ref_action_finishes_the_same_high_level_contract() -> None:
    browser = _browser(ConfirmedTransitionNative())
    ref = browser.observe().one(name="Submit")

    with pytest.raises(ConfirmationRequired) as required:
        ref.click(wait=Wait.url("*/complete"))

    result = required.value.pending.confirm()
    assert isinstance(result, ActionResult)
    assert result.target is ref
    assert result.after.origin.endswith("/complete")


def test_post_action_wait_failure_reports_that_the_action_completed() -> None:
    native = WaitFailureNative()
    ref = _browser(native).observe().one(name="Submit")

    with pytest.raises(ActionTransitionError) as failed:
        ref.click(wait=Wait.text("Saved"))

    assert native.submitted is True
    assert failed.value.action == "click"
    assert failed.value.stage == "wait"
    assert failed.value.before is ref.snapshot
    assert failed.value.after is None


def test_async_snapshot_and_action_match_the_sync_contract() -> None:
    async def run() -> None:
        native = TransitionNative()
        browser = AsyncBrowser(
            _native_session=AsyncNativeSession(native=native),
        )
        page = await browser.observe(SnapshotSpec(compact=True))
        result = await page.one(name="Submit").click(wait=Wait.text("Saved"))

        assert isinstance(page, AsyncSnapshot)
        assert result.before is page
        assert result.after.spec == page.spec
        assert result.diff.additions == 1
        await browser.close()

    asyncio.run(run())
