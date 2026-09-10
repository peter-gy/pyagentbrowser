from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Any

import pytest
from fakes import CLOSE_DATA, ConfirmationNative

from agentbrowser import (
    AsyncBrowser,
    AsyncFrame,
    AsyncPage,
    AsyncSnapshot,
    AsyncStaleRefError,
    Browser,
    ConfirmationRequired,
    ElementGeometry,
    EvidenceManifest,
    Frame,
    Page,
    Screenshot,
    ScrollResult,
    Snapshot,
    SnapshotDiff,
    StaleRefError,
)
from agentbrowser.session import NativeSession
from agentbrowser.session_async import AsyncNativeSession

pytestmark = pytest.mark.sdk_dx
TARGET_ID = "A" * 16
ORIGIN = "https://example.com/app"


def _snapshot_data() -> dict[str, Any]:
    return {
        "snapshot": "button Save [ref=e1]",
        "origin": ORIGIN,
        "targetId": TARGET_ID,
        "refs": {"e1": {"role": "button", "name": "Save"}},
    }


def _geometry_data() -> dict[str, Any]:
    return {
        "result": {
            "x": 10,
            "y": 20,
            "width": 300,
            "height": 200,
            "clientWidth": 300,
            "clientHeight": 200,
            "scrollWidth": 320,
            "scrollHeight": 400,
        },
        "origin": ORIGIN,
        "targetId": TARGET_ID,
    }


def _scroll_data() -> dict[str, Any]:
    return {
        "result": {
            "before": {"x": 0, "y": 10},
            "after": {"x": 0, "y": 110},
        },
        "origin": ORIGIN,
        "targetId": TARGET_ID,
    }


def _tabs_data() -> dict[str, Any]:
    return {
        "tabs": [
            {
                "tabId": "t1",
                "targetId": TARGET_ID,
                "url": ORIGIN,
                "title": "Application",
                "active": True,
            }
        ]
    }


def _frame_tree_data() -> dict[str, Any]:
    return {
        "targetId": TARGET_ID,
        "frameTree": {
            "frame": {"id": "main", "name": "", "url": ORIGIN},
            "childFrames": [
                {
                    "frame": {
                        "id": "preview",
                        "name": "preview",
                        "url": f"{ORIGIN}/preview",
                    }
                }
            ],
        },
    }


def _iframe_snapshot_data(
    *, generation: int, text: str = "iframe Preview [ref=e1]"
) -> dict[str, Any]:
    return {
        "snapshot": text,
        "origin": f"{ORIGIN}/frame",
        "targetId": TARGET_ID,
        "refGeneration": generation,
        "refs": {"e1": {"role": "iframe", "name": "Preview"}},
    }


def _confirmed_sync(
    action: str,
    result: Mapping[str, Any],
    invoke: Callable[[Browser], object],
) -> tuple[object, ConfirmationNative]:
    native = ConfirmationNative(action=action, result=result)
    browser = Browser(_native_session=NativeSession(native=native))
    try:
        with pytest.raises(ConfirmationRequired) as required:
            invoke(browser)
        return required.value.pending.confirm(), native
    finally:
        browser.close()


async def _confirmed_async(
    action: str,
    result: Mapping[str, Any],
    invoke: Callable[[AsyncBrowser], Awaitable[object]],
) -> tuple[object, ConfirmationNative]:
    native = ConfirmationNative(action=action, result=result)
    browser = AsyncBrowser(_native_session=AsyncNativeSession(native=native))
    try:
        with pytest.raises(ConfirmationRequired) as required:
            await invoke(browser)
        return await required.value.pending.confirm(), native
    finally:
        await browser.close()


def test_sync_scoped_operations_restore_public_results_after_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot, _ = _confirmed_sync("snapshot", _snapshot_data(), lambda b: b.page.observe())
    evaluated, _ = _confirmed_sync(
        "evaluate",
        {"result": "ready", "origin": ORIGIN, "targetId": TARGET_ID},
        lambda b: b.page.evaluate("document.body.dataset.state"),
    )
    geometry, _ = _confirmed_sync("evaluate", _geometry_data(), lambda b: b.page.geometry("main"))
    scroll, _ = _confirmed_sync("evaluate", _scroll_data(), lambda b: b.page.scroll.by(y=100))

    monkeypatch.setenv("HOME", str(tmp_path))
    screenshot_path = tmp_path / "captures" / "page.png"
    screenshot, screenshot_native = _confirmed_sync(
        "screenshot",
        {"path": str(screenshot_path), "origin": ORIGIN, "targetId": TARGET_ID},
        lambda b: b.page.capture.screenshot("~/captures/page.png", wait_ms=0),
    )
    page, _ = _confirmed_sync("tab_list", _tabs_data(), lambda b: b.tabs.get(id="t1"))

    assert isinstance(snapshot, Snapshot)
    assert snapshot.browser.scope.target_id == TARGET_ID
    assert evaluated == "ready"
    assert isinstance(geometry, ElementGeometry)
    assert geometry.scope.target_id == TARGET_ID
    assert isinstance(scroll, ScrollResult)
    assert scroll.scope.url == ORIGIN
    assert isinstance(screenshot, Screenshot)
    assert screenshot.scope is not None and screenshot.scope.target_id == TARGET_ID
    assert screenshot_native.commands[0]["path"] == str(screenshot_path)
    assert isinstance(page, Page)
    assert page.target_id == TARGET_ID and page.frame_url == ORIGIN


def test_async_scoped_operations_restore_public_results_after_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run() -> None:
        snapshot, _ = await _confirmed_async(
            "snapshot", _snapshot_data(), lambda b: b.page.observe()
        )
        evaluated, _ = await _confirmed_async(
            "evaluate",
            {"result": "ready", "origin": ORIGIN, "targetId": TARGET_ID},
            lambda b: b.page.evaluate("document.body.dataset.state"),
        )
        geometry, _ = await _confirmed_async(
            "evaluate", _geometry_data(), lambda b: b.page.geometry("main")
        )
        scroll, _ = await _confirmed_async(
            "evaluate", _scroll_data(), lambda b: b.page.scroll.by(y=100)
        )

        monkeypatch.setenv("HOME", str(tmp_path))
        screenshot_path = tmp_path / "captures" / "async.png"
        screenshot, screenshot_native = await _confirmed_async(
            "screenshot",
            {"path": str(screenshot_path), "origin": ORIGIN, "targetId": TARGET_ID},
            lambda b: b.page.capture.screenshot("~/captures/async.png", wait_ms=0),
        )
        page, _ = await _confirmed_async("tab_list", _tabs_data(), lambda b: b.tabs.get(id="t1"))

        assert isinstance(snapshot, AsyncSnapshot)
        assert snapshot.browser.scope.target_id == TARGET_ID
        assert evaluated == "ready"
        assert isinstance(geometry, ElementGeometry)
        assert geometry.scope.target_id == TARGET_ID
        assert isinstance(scroll, ScrollResult)
        assert scroll.scope.url == ORIGIN
        assert isinstance(screenshot, Screenshot)
        assert screenshot.scope is not None and screenshot.scope.target_id == TARGET_ID
        assert screenshot_native.commands[0]["path"] == str(screenshot_path)
        assert isinstance(page, AsyncPage)
        assert page.target_id == TARGET_ID and page.frame_url == ORIGIN

    asyncio.run(run())


class _TargetSequenceNative:
    def __init__(self) -> None:
        self.active_target = "A" * 16
        self.commands: list[dict[str, Any]] = []

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        self.commands.append(command)
        action = str(command["action"])
        if action == "title":
            requested = command.get("_targetId")
            if isinstance(requested, str):
                self.active_target = requested
            data: Mapping[str, Any] = {
                "title": "First" if self.active_target == "A" * 16 else "Second"
            }
        elif action == "tab_switch":
            self.active_target = "B" * 16
            data = {
                "tabId": "t2",
                "targetId": self.active_target,
                "url": "https://second.example",
                "title": "Second",
                "label": None,
            }
        else:
            assert action == "__agent_browser_internal_shutdown"
            data = CLOSE_DATA
        return json.dumps(
            {
                "id": command["id"],
                "success": True,
                "data": data,
                "targetId": self.active_target,
            }
        )


def test_lazy_page_binds_to_first_target_and_survives_tab_switch() -> None:
    native = _TargetSequenceNative()
    browser = Browser(_native_session=NativeSession(native=native))
    try:
        retained = browser.page
        assert retained.target_id is None
        assert retained.title() == "First"
        assert retained.target_id == "A" * 16

        browser.tabs.switch(id="t2")
        current = browser.page
        assert current.target_id == "B" * 16
        assert retained.title() == "First"
        assert native.commands[-1]["_targetId"] == "A" * 16
        assert current.title() == "Second"
        assert native.commands[-1]["_targetId"] == "B" * 16
    finally:
        browser.close()


def test_async_lazy_page_binds_to_first_target_and_survives_tab_switch() -> None:
    async def run() -> None:
        native = _TargetSequenceNative()
        browser = AsyncBrowser(_native_session=AsyncNativeSession(native=native))
        try:
            retained = browser.page
            assert retained.target_id is None
            assert await retained.title() == "First"
            assert retained.target_id == "A" * 16

            await browser.tabs.switch(id="t2")
            current = browser.page
            assert current.target_id == "B" * 16
            assert await retained.title() == "First"
            assert native.commands[-1]["_targetId"] == "A" * 16
            assert await current.title() == "Second"
            assert native.commands[-1]["_targetId"] == "B" * 16
        finally:
            await browser.close()

    asyncio.run(run())


class _QueuedConfirmationNative:
    def __init__(self, replies: list[tuple[str, Mapping[str, Any]]]) -> None:
        self.replies = list(replies)
        self.pending: tuple[str, Mapping[str, Any], str] | None = None
        self.commands: list[dict[str, Any]] = []

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        self.commands.append(command)
        action = str(command["action"])
        target_id: object = None
        if action == "__agent_browser_internal_shutdown":
            data: Mapping[str, Any] = CLOSE_DATA
        elif action == "confirm":
            assert self.pending is not None
            pending_action, result, confirmation_id = self.pending
            assert command.get("confirmation_id") == confirmation_id
            self.pending = None
            target_id = result.get("targetId")
            data = {
                "confirmed": True,
                "action": pending_action,
                "result": {
                    "id": f"confirmed-{confirmation_id}",
                    "success": True,
                    "data": dict(result),
                },
            }
        else:
            expected_action, result = self.replies.pop(0)
            assert action == expected_action
            target_id = result.get("targetId")
            confirmation_id = f"confirm-{len(self.commands)}"
            self.pending = (action, result, confirmation_id)
            data = {
                "confirmation_required": True,
                "confirmation_id": confirmation_id,
                "action": action,
            }
        response = {"id": command["id"], "success": True, "data": data}
        if isinstance(target_id, str):
            response["targetId"] = target_id
        return json.dumps(response)


def test_lazy_page_binds_after_confirmed_first_command() -> None:
    native = _QueuedConfirmationNative([("title", {"title": "Confirmed", "targetId": TARGET_ID})])
    browser = Browser(_native_session=NativeSession(native=native))
    try:
        page = browser.page
        with pytest.raises(ConfirmationRequired) as required:
            page.title()
        assert page.target_id is None

        assert required.value.pending.confirm() == "Confirmed"
        assert page.target_id == TARGET_ID
    finally:
        browser.close()


def test_async_lazy_page_binds_after_confirmed_first_command() -> None:
    async def run() -> None:
        native = _QueuedConfirmationNative(
            [("title", {"title": "Confirmed", "targetId": TARGET_ID})]
        )
        browser = AsyncBrowser(_native_session=AsyncNativeSession(native=native))
        try:
            page = browser.page
            with pytest.raises(ConfirmationRequired) as required:
                await page.title()
            assert page.target_id is None

            assert await required.value.pending.confirm() == "Confirmed"
            assert page.target_id == TARGET_ID
        finally:
            await browser.close()

    asyncio.run(run())


def test_sync_frame_selector_resumes_tree_count_and_resolution_confirmations() -> None:
    native = _QueuedConfirmationNative(
        [
            ("frame", _frame_tree_data()),
            ("evaluate", {"result": 1, "origin": ORIGIN, "targetId": TARGET_ID}),
            ("frame", {"frameId": "preview", "targetId": TARGET_ID}),
        ]
    )
    browser = Browser(_native_session=NativeSession(native=native))
    try:
        with pytest.raises(ConfirmationRequired) as tree_required:
            browser.page.frames.get(selector="#preview")
        with pytest.raises(ConfirmationRequired) as count_required:
            tree_required.value.pending.confirm()
        with pytest.raises(ConfirmationRequired) as frame_required:
            count_required.value.pending.confirm()
        frame = frame_required.value.pending.confirm()

        assert isinstance(frame, Frame)
        assert frame.frame_id == "preview"
        assert frame.target_id == TARGET_ID
    finally:
        browser.close()


def test_async_frame_selector_resumes_tree_count_and_resolution_confirmations() -> None:
    async def run() -> None:
        native = _QueuedConfirmationNative(
            [
                ("frame", _frame_tree_data()),
                ("evaluate", {"result": 1, "origin": ORIGIN, "targetId": TARGET_ID}),
                ("frame", {"frameId": "preview", "targetId": TARGET_ID}),
            ]
        )
        browser = AsyncBrowser(_native_session=AsyncNativeSession(native=native))
        try:
            with pytest.raises(ConfirmationRequired) as tree_required:
                await browser.page.frames.get(selector="#preview")
            with pytest.raises(ConfirmationRequired) as count_required:
                await tree_required.value.pending.confirm()
            with pytest.raises(ConfirmationRequired) as frame_required:
                await count_required.value.pending.confirm()
            frame = await frame_required.value.pending.confirm()

            assert isinstance(frame, AsyncFrame)
            assert frame.frame_id == "preview"
            assert frame.target_id == TARGET_ID
        finally:
            await browser.close()

    asyncio.run(run())


class _StaleContentFrameNative:
    def __init__(self) -> None:
        self.commands: list[dict[str, Any]] = []
        self.confirmation_id = "confirm-frame"

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        self.commands.append(command)
        action = str(command["action"])
        response: dict[str, Any]
        if action == "snapshot":
            response = {
                "id": command["id"],
                "success": True,
                "data": _iframe_snapshot_data(generation=1),
                "refGeneration": 1,
                "targetId": TARGET_ID,
            }
        elif action == "frame":
            assert command["_refGeneration"] == 1
            response = {
                "id": command["id"],
                "success": True,
                "data": {
                    "confirmation_required": True,
                    "confirmation_id": self.confirmation_id,
                    "action": "frame",
                },
                "refGeneration": 1,
            }
        elif action == "confirm":
            response = {
                "id": command["id"],
                "success": True,
                "data": {
                    "confirmed": True,
                    "action": "frame",
                    "result": {
                        "id": "confirmed-frame",
                        "success": False,
                        "code": "stale_ref",
                        "error": "Snapshot ref generation expired",
                    },
                },
                "refGeneration": 2,
            }
        else:
            assert action == "__agent_browser_internal_shutdown"
            response = {"id": command["id"], "success": True, "data": CLOSE_DATA}
        return json.dumps(response)


def test_content_frame_translates_native_generation_expiry() -> None:
    native = _StaleContentFrameNative()
    browser = Browser(_native_session=NativeSession(native=native))
    try:
        ref = browser.page.observe().one(role="iframe", name="Preview")
        with pytest.raises(ConfirmationRequired) as required:
            ref.content_frame()
        with pytest.raises(StaleRefError, match="stale snapshot ref"):
            required.value.pending.confirm()
    finally:
        browser.close()


def test_async_content_frame_translates_native_generation_expiry() -> None:
    async def run() -> None:
        native = _StaleContentFrameNative()
        browser = AsyncBrowser(_native_session=AsyncNativeSession(native=native))
        try:
            ref = (await browser.page.observe()).one(role="iframe", name="Preview")
            with pytest.raises(ConfirmationRequired) as required:
                await ref.content_frame()
            with pytest.raises(AsyncStaleRefError, match="stale snapshot ref"):
                await required.value.pending.confirm()
        finally:
            await browser.close()

    asyncio.run(run())


class _ConfirmingFrameSnapshotNative:
    def __init__(self) -> None:
        self.commands: list[dict[str, Any]] = []
        self.snapshot_count = 0
        self.confirmation_id = "confirm-snapshot"
        self.after = _iframe_snapshot_data(
            generation=2,
            text="iframe Preview [ref=e1]\nheading Updated [ref=e2]",
        )

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        self.commands.append(command)
        action = str(command["action"])
        if action == "snapshot" and self.snapshot_count == 0:
            self.snapshot_count += 1
            response: dict[str, Any] = {
                "id": command["id"],
                "success": True,
                "data": _iframe_snapshot_data(generation=1),
                "refGeneration": 1,
                "targetId": TARGET_ID,
            }
        elif action == "snapshot":
            assert command["_targetId"] == TARGET_ID
            assert command["_frameId"] == "preview"
            response = {
                "id": command["id"],
                "success": True,
                "data": {
                    "confirmation_required": True,
                    "confirmation_id": self.confirmation_id,
                    "action": "snapshot",
                },
                "refGeneration": 1,
            }
        elif action == "confirm":
            response = {
                "id": command["id"],
                "success": True,
                "data": {
                    "confirmed": True,
                    "action": "snapshot",
                    "result": {
                        "id": "confirmed-snapshot",
                        "success": True,
                        "data": self.after,
                        "refGeneration": 2,
                        "targetId": TARGET_ID,
                    },
                },
                "refGeneration": 2,
                "targetId": TARGET_ID,
            }
        else:
            assert action == "__agent_browser_internal_shutdown"
            response = {"id": command["id"], "success": True, "data": CLOSE_DATA}
        return json.dumps(response)


def test_frame_snapshot_diff_and_manifest_keep_captured_scope_generation() -> None:
    native = _ConfirmingFrameSnapshotNative()
    browser = Browser(_native_session=NativeSession(native=native))
    frame = Frame(
        browser,
        target_id=TARGET_ID,
        frame_id="preview",
        frame_url=f"{ORIGIN}/frame",
    )
    try:
        before = frame.observe()
        with pytest.raises(ConfirmationRequired) as required:
            before.diff()
        diff = required.value.pending.confirm()

        record = EvidenceManifest().record("before", before).to_dict()
        assert isinstance(diff, SnapshotDiff) and diff.changed
        assert record["value"]["scope"] == {
            "target_id": TARGET_ID,
            "frame_id": "preview",
            "url": f"{ORIGIN}/frame",
            "generation": 1,
        }
        assert browser._ref_generation == 2
    finally:
        browser.close()


def test_async_frame_snapshot_diff_and_manifest_keep_captured_scope_generation() -> None:
    async def run() -> None:
        native = _ConfirmingFrameSnapshotNative()
        browser = AsyncBrowser(_native_session=AsyncNativeSession(native=native))
        frame = AsyncFrame(
            browser,
            target_id=TARGET_ID,
            frame_id="preview",
            frame_url=f"{ORIGIN}/frame",
        )
        try:
            before = await frame.observe()
            with pytest.raises(ConfirmationRequired) as required:
                await before.diff()
            diff = await required.value.pending.confirm()

            record = EvidenceManifest().record("before", before).to_dict()
            assert isinstance(diff, SnapshotDiff) and diff.changed
            assert record["value"]["scope"] == {
                "target_id": TARGET_ID,
                "frame_id": "preview",
                "url": f"{ORIGIN}/frame",
                "generation": 1,
            }
            assert browser._ref_generation == 2
        finally:
            await browser.close()

    asyncio.run(run())
