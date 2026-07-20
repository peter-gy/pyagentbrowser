from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fakes import ScriptedNative

from agentbrowser import ActionResult, AsyncBrowser, Browser, ConfirmationRequired, Wait
from agentbrowser.session import NativeSession
from agentbrowser.session_async import AsyncNativeSession

pytestmark = pytest.mark.sdk_dx


def _browser(native: Any) -> Browser:
    return Browser(_native_session=NativeSession(native=native))


def _async_browser(native: Any) -> AsyncBrowser:
    return AsyncBrowser(_native_session=AsyncNativeSession(native=native))


def _confirmation(action: str, confirmation_id: str) -> dict[str, Any]:
    return {
        "success": True,
        "data": {
            "confirmation_required": True,
            "confirmation_id": confirmation_id,
            "action": action,
        },
    }


def _confirmed(action: str, data: Any) -> dict[str, Any]:
    return {
        "success": True,
        "data": {
            "confirmed": True,
            "action": action,
            "result": {
                "id": f"confirmed-{action}",
                "success": True,
                "data": data,
            },
        },
    }


def _launch_then_navigate_native() -> ScriptedNative:
    def confirm(command: dict[str, Any]) -> dict[str, Any]:
        confirmation_id = command["confirmation_id"]
        if confirmation_id == "confirm-launch":
            return _confirmed("launch", {})
        if confirmation_id == "confirm-navigate":
            return _confirmed("navigate", {})
        raise AssertionError(f"unexpected confirmation id: {confirmation_id}")

    return ScriptedNative(
        {
            "launch": _confirmation("launch", "confirm-launch"),
            "navigate": _confirmation("navigate", "confirm-navigate"),
            "confirm": confirm,
            "__agent_browser_internal_shutdown": {},
        }
    )


def _chained_tab_switch_native() -> ScriptedNative:
    attempts = 0
    existing = {
        "id": "existing",
        "url": "https://example.com/old",
        "label": "work",
    }

    def confirm(command: dict[str, Any]) -> dict[str, Any]:
        nonlocal attempts
        assert command["confirmation_id"] == "confirm-switch"
        attempts += 1
        if attempts == 1:
            return {
                "success": True,
                "data": {
                    "confirmed": True,
                    "action": "tab_switch",
                    "result": {
                        "id": "confirmed-tab-switch",
                        "success": True,
                        "data": {
                            "confirmation_required": True,
                            "confirmation_id": "confirm-switch",
                            "action": "plugin:provider:launch.mutate",
                        },
                    },
                },
            }
        return _confirmed("plugin:provider:launch.mutate", {})

    return ScriptedNative(
        {
            "tab_list": {"tabs": [existing]},
            "tab_switch": _confirmation("tab_switch", "confirm-switch"),
            "confirm": confirm,
            "navigate": {},
            "__agent_browser_internal_shutdown": {},
        }
    )


def _snapshot(*, submitted: bool) -> dict[str, Any]:
    return {
        "snapshot": '@e1 [button] "Submit"',
        "origin": "https://example.com/complete" if submitted else "https://example.com/form",
        "refs": {"e1": {"role": "button", "name": "Submit"}},
    }


def _confirmed_wait_native() -> ScriptedNative:
    state = {"submitted": False, "waits": 0}

    def snapshot(_command: dict[str, Any]) -> dict[str, Any]:
        return _snapshot(submitted=bool(state["submitted"]))

    def click(_command: dict[str, Any]) -> dict[str, Any]:
        state["submitted"] = True
        return {}

    def wait(_command: dict[str, Any]) -> dict[str, Any]:
        state["waits"] += 1
        if state["waits"] == 1:
            return _confirmation("wait", "confirm-wait")
        return {}

    return ScriptedNative(
        {
            "snapshot": snapshot,
            "click": click,
            "wait": wait,
            "confirm": _confirmed("wait", {}),
            "__agent_browser_internal_shutdown": {},
        }
    )


def test_sync_repeated_launch_and_navigation_confirmation_returns_browser() -> None:
    native = _launch_then_navigate_native()
    browser = _browser(native)

    with pytest.raises(ConfirmationRequired) as launch_required:
        browser.open("example.com")
    with pytest.raises(ConfirmationRequired) as navigate_required:
        launch_required.value.pending.confirm()

    assert navigate_required.value.pending.confirm() is browser
    assert [command["action"] for command in native.commands[:4]] == [
        "launch",
        "confirm",
        "navigate",
        "confirm",
    ]
    browser.close()


def test_async_repeated_launch_and_navigation_confirmation_returns_browser() -> None:
    async def run() -> None:
        native = _launch_then_navigate_native()
        browser = _async_browser(native)

        with pytest.raises(ConfirmationRequired) as launch_required:
            await browser.open("example.com")
        with pytest.raises(ConfirmationRequired) as navigate_required:
            await launch_required.value.pending.confirm()

        assert await navigate_required.value.pending.confirm() is browser
        assert [command["action"] for command in native.commands[:4]] == [
            "launch",
            "confirm",
            "navigate",
            "confirm",
        ]
        await browser.close()

    asyncio.run(run())


def test_sync_chained_confirmation_preserves_decoder_and_completion() -> None:
    native = _chained_tab_switch_native()
    browser = _browser(native)

    with pytest.raises(ConfirmationRequired) as first:
        browser.tabs.open("example.com/new", label="work")
    with pytest.raises(ConfirmationRequired) as second:
        first.value.pending.confirm()

    tab = second.value.pending.confirm()
    assert tab.id == "existing"
    assert tab.url == "https://example.com/new"
    assert tab.active is True
    assert [command["action"] for command in native.commands[:5]] == [
        "tab_list",
        "tab_switch",
        "confirm",
        "confirm",
        "navigate",
    ]
    browser.close()


def test_async_chained_confirmation_preserves_decoder_and_completion() -> None:
    async def run() -> None:
        native = _chained_tab_switch_native()
        browser = _async_browser(native)

        with pytest.raises(ConfirmationRequired) as first:
            await browser.tabs.open("example.com/new", label="work")
        with pytest.raises(ConfirmationRequired) as second:
            await first.value.pending.confirm()

        tab = await second.value.pending.confirm()
        assert tab.id == "existing"
        assert tab.url == "https://example.com/new"
        assert tab.active is True
        assert [command["action"] for command in native.commands[:5]] == [
            "tab_list",
            "tab_switch",
            "confirm",
            "confirm",
            "navigate",
        ]
        await browser.close()

    asyncio.run(run())


def test_sync_wait_all_resumes_remaining_waits_before_snapshot() -> None:
    native = _confirmed_wait_native()
    browser = _browser(native)
    ref = browser.observe().one(name="Submit")

    with pytest.raises(ConfirmationRequired) as required:
        ref.click(wait=Wait.all(Wait.text("Saved"), Wait.url("*/complete")))

    result = required.value.pending.confirm()
    waits = [command for command in native.commands if command["action"] == "wait"]
    assert isinstance(result, ActionResult)
    assert [command["action"] for command in native.commands[-3:]] == [
        "confirm",
        "wait",
        "snapshot",
    ]
    assert waits[0]["text"] == "Saved"
    assert waits[1]["url"] == "*/complete"
    browser.close()


def test_async_wait_all_resumes_remaining_waits_before_snapshot() -> None:
    async def run() -> None:
        native = _confirmed_wait_native()
        browser = _async_browser(native)
        ref = (await browser.observe()).one(name="Submit")

        with pytest.raises(ConfirmationRequired) as required:
            await ref.click(wait=Wait.all(Wait.text("Saved"), Wait.url("*/complete")))

        result = await required.value.pending.confirm()
        waits = [command for command in native.commands if command["action"] == "wait"]
        assert isinstance(result, ActionResult)
        assert [command["action"] for command in native.commands[-3:]] == [
            "confirm",
            "wait",
            "snapshot",
        ]
        assert waits[0]["text"] == "Saved"
        assert waits[1]["url"] == "*/complete"
        await browser.close()

    asyncio.run(run())


def test_sync_native_any_confirmation_preserves_arbitrary_json() -> None:
    browser = _browser(
        ScriptedNative(
            {
                "future_action": _confirmation("future_action", "confirm-any"),
                "confirm": _confirmed("future_action", ["ready", 1, None]),
            }
        )
    )

    with pytest.raises(ConfirmationRequired) as required:
        browser.native.data("future_action", expect="any")

    assert required.value.pending.confirm() == ["ready", 1, None]


def test_async_native_any_confirmation_preserves_arbitrary_json() -> None:
    async def run() -> None:
        browser = _async_browser(
            ScriptedNative(
                {
                    "future_action": _confirmation("future_action", "confirm-any"),
                    "confirm": _confirmed("future_action", ["ready", 1, None]),
                    "__agent_browser_internal_shutdown": {},
                }
            )
        )

        with pytest.raises(ConfirmationRequired) as required:
            await browser.native.data("future_action", expect="any")

        assert await required.value.pending.confirm() == ["ready", 1, None]
        await browser.close()

    asyncio.run(run())


def test_sync_tab_labels_are_forwarded_to_native_without_listing() -> None:
    native = ScriptedNative(
        {
            "tab_switch": {},
            "tab_close": {},
            "__agent_browser_internal_shutdown": {},
        }
    )
    browser = _browser(native)

    browser.tabs.switch(label="work")
    browser.tabs.close(label="work")

    assert [command["action"] for command in native.commands] == ["tab_switch", "tab_close"]
    assert [command["tabId"] for command in native.commands] == ["work", "work"]
    browser.close()


def test_async_tab_labels_are_forwarded_to_native_without_listing() -> None:
    async def run() -> None:
        native = ScriptedNative(
            {
                "tab_switch": {},
                "tab_close": {},
                "__agent_browser_internal_shutdown": {},
            }
        )
        browser = _async_browser(native)

        await browser.tabs.switch(label="work")
        await browser.tabs.close(label="work")

        assert [command["action"] for command in native.commands] == [
            "tab_switch",
            "tab_close",
        ]
        assert [command["tabId"] for command in native.commands] == ["work", "work"]
        await browser.close()

    asyncio.run(run())


def test_sync_implicit_launch_updates_lifecycle_before_navigation() -> None:
    native = ScriptedNative(
        {
            "title": {
                "title": "Implicit",
                "lifecycle": {"effectiveLaunch": {"browserLaunched": True}},
            },
            "navigate": {},
            "__agent_browser_internal_shutdown": {},
        }
    )
    browser = _browser(native)

    assert browser.title() == "Implicit"
    assert browser.is_launched is True
    assert browser.open("example.com") is browser
    assert [command["action"] for command in native.commands] == ["title", "navigate"]
    browser.close()


def test_async_implicit_launch_updates_lifecycle_before_navigation() -> None:
    async def run() -> None:
        native = ScriptedNative(
            {
                "title": {
                    "title": "Implicit",
                    "lifecycle": {"effectiveLaunch": {"browserLaunched": True}},
                },
                "navigate": {},
                "__agent_browser_internal_shutdown": {},
            }
        )
        browser = _async_browser(native)

        assert await browser.title() == "Implicit"
        assert browser.is_launched is True
        assert await browser.open("example.com") is browser
        assert [command["action"] for command in native.commands] == ["title", "navigate"]
        await browser.close()

    asyncio.run(run())
