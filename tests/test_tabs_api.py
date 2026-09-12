from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fakes import ScriptedNative
from support.sdk import _browser, _command_without_id

from agentbrowser import (
    AsyncBrowser,
    ConfirmationRequired,
    NativeParseError,
    TabCloseResult,
    TabSwitchResult,
)
from agentbrowser.transport.async_ import AsyncNativeSession

pytestmark = pytest.mark.sdk_dx


def test_tabs_get_returns_page_bound_to_exact_target() -> None:
    native = ScriptedNative(
        {
            "tab_list": {
                "tabs": [
                    {
                        "tabId": "t1",
                        "targetId": "0123456789ABCDEF",
                        "url": "https://example.com",
                        "title": "Example",
                        "active": True,
                    }
                ]
            },
            "title": {"title": "Example"},
        }
    )
    browser = _browser(native)

    page = browser.tabs.get(id="t1")

    assert page.title() == "Example"
    assert native.commands[1]["_targetId"] == "0123456789ABCDEF"
    assert native.commands[1]["_frameId"] == ""


def test_tabs_get_index_uses_the_stable_tab_id_suffix() -> None:
    native = ScriptedNative(
        {
            "tab_list": {
                "tabs": [
                    {"tabId": "t2", "targetId": "B" * 16, "url": "https://two.example"},
                    {"tabId": "t1", "targetId": "A" * 16, "url": "https://one.example"},
                ]
            }
        }
    )
    browser = _browser(native)

    page = browser.tabs.get(index=1)

    assert page.target_id == "A" * 16


def test_tab_lifecycle_results_surface_discarded_tab_revival() -> None:
    native = ScriptedNative(
        {
            "tab_switch": {
                "tabId": "t2",
                "targetId": "CDP-TARGET-2",
                "url": "https://example.com/reloaded",
                "title": "Reloaded",
                "label": "work",
                "revived": True,
            },
            "tab_close": {
                "tabId": "t2",
                "targetId": "CDP-TARGET-2",
                "label": "work",
                "closed": True,
                "activeTabRevived": True,
            },
        }
    )
    browser = _browser(native)

    switched = browser.tabs.switch(id="t2")
    closed = browser.tabs.close(id="t2")

    assert switched.id == "t2"
    assert switched.target_id == "CDP-TARGET-2"
    assert isinstance(switched, TabSwitchResult)
    assert switched.revived is True
    assert switched.dialog_blocked is False
    assert isinstance(closed, TabCloseResult)
    assert closed.id == "t2"
    assert closed.target_id == "CDP-TARGET-2"
    assert closed.closed is True
    assert closed.active_tab_revived is True


def test_tab_switch_result_surfaces_a_blocking_dialog() -> None:
    browser = _browser(
        ScriptedNative(
            {
                "tab_switch": {
                    "tabId": "t2",
                    "url": "https://example.com/form",
                    "title": "Form",
                    "label": None,
                    "dialogBlocked": True,
                }
            }
        )
    )

    switched = browser.tabs.switch(id="t2")

    assert switched.dialog_blocked is True
    assert switched.revived is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("tabId", 7),
        ("url", False),
        ("title", {"unexpected": True}),
        ("label", ["work"]),
        ("targetId", 1),
        ("revived", 1),
        ("dialogBlocked", "yes"),
    ],
)
def test_tab_switch_rejects_malformed_native_metadata(field: str, value: Any) -> None:
    data: dict[str, Any] = {
        "tabId": "t2",
        "url": "https://example.com/form",
        "title": "Form",
        "label": None,
    }
    data[field] = value
    browser = _browser(ScriptedNative({"tab_switch": data}))

    with pytest.raises(NativeParseError):
        browser.tabs.switch(id="t2")


def test_tabs_open_creates_a_labelled_tab_when_no_reusable_tab_exists() -> None:
    native = ScriptedNative(
        {
            "tab_list": {"tabs": []},
            "tab_new": {
                "id": "created",
                "url": "https://example.com/created",
                "label": "work",
                "active": True,
            },
        }
    )
    browser = _browser(native)

    tab = browser.tabs.open("example.com/created", label="work")

    assert tab.id == "created"
    assert tab.label == "work"
    assert [command["action"] for command in native.commands] == ["tab_list", "tab_new"]
    assert _command_without_id(native.commands[-1]) == {
        "action": "tab_new",
        "url": "https://example.com/created",
        "label": "work",
    }


def test_async_tab_lifecycle_results_match_the_sync_contract() -> None:
    async def run() -> None:
        native = ScriptedNative(
            {
                "tab_switch": {
                    "tabId": "t2",
                    "targetId": "CDP-TARGET-2",
                    "url": "https://example.com/reloaded",
                    "title": "Reloaded",
                    "label": None,
                    "revived": True,
                },
                "tab_close": {
                    "tabId": "t2",
                    "targetId": "CDP-TARGET-2",
                    "label": None,
                    "closed": True,
                    "activeTabRevived": True,
                },
            }
        )
        browser = AsyncBrowser(_native_session=AsyncNativeSession(native=native))

        switched = await browser.tabs.switch(id="t2")
        closed = await browser.tabs.close(id="t2")

        assert switched.revived is True
        assert switched.target_id == "CDP-TARGET-2"
        assert closed.active_tab_revived is True
        assert closed.target_id == "CDP-TARGET-2"

    asyncio.run(run())


def test_async_tabs_open_creates_a_labelled_tab_when_no_reusable_tab_exists() -> None:
    async def run() -> None:
        native = ScriptedNative(
            {
                "tab_list": {"tabs": []},
                "tab_new": {
                    "id": "created",
                    "url": "https://example.com/created",
                    "label": "work",
                    "active": True,
                },
            },
            default={},
        )
        browser = AsyncBrowser(_native_session=AsyncNativeSession(native=native))

        tab = await browser.tabs.open("example.com/created", label="work")

        assert tab.id == "created"
        assert tab.label == "work"
        assert [command["action"] for command in native.commands] == ["tab_list", "tab_new"]
        assert _command_without_id(native.commands[-1]) == {
            "action": "tab_new",
            "url": "https://example.com/created",
            "label": "work",
        }
        await browser.close()

    asyncio.run(run())


def test_async_tabs_open_confirmation_continues_switch_and_navigation() -> None:
    async def run() -> None:
        existing = {
            "id": "existing",
            "url": "https://example.com/old",
            "label": "work",
        }
        native = ScriptedNative(
            {
                "tab_list": {
                    "success": True,
                    "data": {
                        "confirmation_required": True,
                        "confirmation_id": "confirm-list",
                        "action": "tab_list",
                    },
                },
                "confirm": {
                    "success": True,
                    "targetId": "existing",
                    "data": {
                        "confirmed": True,
                        "action": "tab_list",
                        "result": {
                            "id": "confirmed-list",
                            "success": True,
                            "data": {"tabs": [existing]},
                        },
                    },
                },
                "tab_switch": {
                    "tabId": "existing",
                    "url": "https://example.com/old",
                    "title": "Existing",
                    "label": "work",
                },
                "navigate": {},
            },
            default={},
        )
        browser = AsyncBrowser(_native_session=AsyncNativeSession(native=native))

        with pytest.raises(ConfirmationRequired) as required:
            await browser.tabs.open(
                "example.com/new",
                label="work",
                wait_until="domcontentloaded",
            )

        tab = await required.value.pending.confirm()

        assert tab.id == "existing"
        assert tab.url == "https://example.com/new"
        assert tab.active is True
        assert [command["action"] for command in native.commands] == [
            "tab_list",
            "confirm",
            "tab_switch",
            "navigate",
        ]
        assert _command_without_id(native.commands[2]) == {
            "action": "tab_switch",
            "tabId": "existing",
        }
        assert _command_without_id(native.commands[-1]) == {
            "action": "navigate",
            "url": "https://example.com/new",
            "waitUntil": "domcontentloaded",
        }
        await browser.close()

    asyncio.run(run())
