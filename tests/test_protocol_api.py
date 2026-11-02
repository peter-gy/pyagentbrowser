from __future__ import annotations

import asyncio
import math
from pathlib import Path
from typing import Any, cast

import pytest
from fakes import ScriptedNative
from support.sdk import _browser, _command_without_id

from agentbrowser import (
    AgentBrowserError,
    AsyncBrowser,
    NativeParseError,
    RouteResponse,
    StateLoadResult,
)
from agentbrowser.transport.async_ import AsyncNativeSession

pytestmark = pytest.mark.sdk_dx

_TRACKED_REQUEST = {
    "requestId": "request-1",
    "url": "https://example.com/data",
    "method": "GET",
    "headers": {"Accept": "application/json"},
    "timestamp": 1_700_000_000_000,
    "resourceType": "Fetch",
}


def test_native_escape_hatch_preserves_arbitrary_json() -> None:
    native = ScriptedNative({"future_action": {"nested": {"items": [1, True, None]}}})
    browser = _browser(native)

    result = browser.native.data(
        "future_action",
        feature={"enabled": True},
        expect="object",
    )

    assert result == {"nested": {"items": [1, True, None]}}
    assert native.commands[0]["feature"] == {"enabled": True}


def test_native_execute_returns_failed_envelopes_without_hiding_diagnostics() -> None:
    native = ScriptedNative(
        {"probe": {"success": False, "error": "failure", "code": "probe_failed"}}
    )
    browser = _browser(native)

    response = browser.native.execute("probe")

    assert response.success is False
    assert response.raw["code"] == "probe_failed"


@pytest.mark.parametrize(
    "action,invoke",
    [
        ("tab_list", lambda browser: browser.tabs.list()),
        ("cookies_get", lambda browser: browser.cookies.get()),
        ("requests", lambda browser: browser.network.requests()),
        ("console", lambda browser: browser.diagnostics.console()),
        ("errors", lambda browser: browser.diagnostics.errors()),
    ],
)
def test_typed_collections_reject_missing_native_arrays(action: str, invoke: Any) -> None:
    browser = _browser(ScriptedNative({action: {}}))

    with pytest.raises(NativeParseError, match="array"):
        invoke(browser)


@pytest.mark.parametrize(
    "action,reply,invoke,attribute,expected",
    [
        (
            "tab_list",
            {
                "tabs": [
                    {
                        "id": "tab-1",
                        "targetId": "CDP-TARGET-1",
                        "url": "https://example.com",
                    }
                ]
            },
            lambda browser: browser.tabs.list()[0],
            "target_id",
            "CDP-TARGET-1",
        ),
        (
            "cookies_get",
            {"cookies": [{"name": "session", "value": "abc", "domain": "example.com"}]},
            lambda browser: browser.cookies.get()[0],
            "name",
            "session",
        ),
        (
            "requests",
            {"requests": [_TRACKED_REQUEST]},
            lambda browser: browser.network.requests()[0],
            "id",
            "request-1",
        ),
        (
            "request_detail",
            {**_TRACKED_REQUEST, "status": 200, "responseBody": '{"ok": true}'},
            lambda browser: browser.network.request("request-1"),
            "response_body",
            '{"ok": true}',
        ),
        (
            "errors",
            {"errors": [{"text": "boom", "url": "https://example.com/app.js", "line": 3}]},
            lambda browser: browser.diagnostics.errors()[0],
            "line",
            3,
        ),
        (
            "console",
            {"messages": [{"type": "log", "text": "ready"}]},
            lambda browser: browser.diagnostics.console()[0],
            "text",
            "ready",
        ),
    ],
)
def test_typed_namespaces_decode_successful_native_data(
    action: str,
    reply: dict[str, Any],
    invoke: Any,
    attribute: str,
    expected: object,
) -> None:
    browser = _browser(ScriptedNative({action: reply}))

    value = invoke(browser)

    assert getattr(value, attribute) == expected


@pytest.mark.parametrize(
    "invoke,expected_action,expected_params",
    [
        (
            lambda browser: browser.storage.set("theme", "dark", area="session"),
            "storage_set",
            {"type": "session", "key": "theme", "value": "dark"},
        ),
        (
            lambda browser: browser.network.route(
                "**/api",
                RouteResponse(
                    status=201,
                    body="created",
                    content_type="text/plain",
                    allow_origin="https://app.example",
                ),
                resource_types=["fetch", "xhr"],
            ),
            "route",
            {
                "url": "**/api",
                "abort": False,
                "response": {
                    "status": 201,
                    "body": "created",
                    "contentType": "text/plain",
                    "allowOrigin": "https://app.example",
                },
                "resourceTypes": ["fetch", "xhr"],
            },
        ),
        (
            lambda browser: browser.network.har_start(content="all"),
            "har_start",
            {"content": "all"},
        ),
        (
            lambda browser: browser.scripts.add(script="window.ready = true"),
            "addscript",
            {"script": "window.ready = true"},
        ),
        (
            lambda browser: browser.emulation.headers({"X-Test": "1"}),
            "headers",
            {"headers": {"X-Test": "1"}},
        ),
        (
            lambda browser: browser.page.set_content("<h1>Ready</h1>"),
            "setcontent",
            {"html": "<h1>Ready</h1>"},
        ),
        (
            lambda browser: browser.clipboard.write("copied"),
            "clipboard",
            {"subAction": "write", "text": "copied"},
        ),
        (
            lambda browser: browser.dialogs.dismiss(),
            "dialog",
            {"response": "dismiss"},
        ),
        (
            lambda browser: browser.keyboard.press("Enter"),
            "press",
            {"key": "Enter"},
        ),
        (
            lambda browser: browser.mouse.move(12, 24),
            "mousemove",
            {"x": 12, "y": 24},
        ),
    ],
)
def test_namespace_commands_serialize_supported_values(
    invoke: Any,
    expected_action: str,
    expected_params: dict[str, Any],
) -> None:
    native = ScriptedNative(default={})
    browser = _browser(native)

    result = invoke(browser)

    assert result is None
    command = native.commands[-1]
    assert command["action"] == expected_action
    assert {key: command[key] for key in expected_params} == expected_params


def test_har_start_rejects_an_unknown_content_mode() -> None:
    native = ScriptedNative(default={})
    browser = _browser(native)

    with pytest.raises(ValueError, match=r"all.*text.*none"):
        browser.network.har_start(content=cast(Any, "binary"))

    assert native.commands == []


def test_path_namespaces_return_typed_paths(tmp_path: Path) -> None:
    pdf = tmp_path / "page.pdf"
    state = tmp_path / "state.json"
    download = tmp_path / "report.csv"
    native = ScriptedNative(
        {
            "pdf": lambda command: {"path": command["path"]},
            "state_save": lambda command: {"path": command["path"]},
            "state_load": lambda command: {
                "loaded": True,
                "path": command["path"],
                "skippedOrigins": ["https://partner.example"],
            },
            "waitfordownload": {"path": str(download)},
        }
    )
    browser = _browser(native)

    assert browser.page.capture.pdf(pdf, landscape=True) == pdf
    assert browser.state.save(state, unsafe_export_all=True) == state
    assert browser.state.load(state, unsafe_import_all=True) == StateLoadResult(
        path=state, skipped_origins=("https://partner.example",)
    )
    assert browser.downloads.wait() == download
    assert native.commands[0]["landscape"] is True
    assert native.commands[1]["unsafeExportAll"] is True
    assert native.commands[2]["unsafeImportAll"] is True


def test_async_har_start_serializes_the_content_mode() -> None:
    async def run() -> None:
        native = ScriptedNative({"har_start": {}})
        browser = AsyncBrowser(_native_session=AsyncNativeSession(native=native))

        await browser.network.har_start(content="none")

        assert _command_without_id(native.commands[0]) == {
            "action": "har_start",
            "content": "none",
        }

    asyncio.run(run())


@pytest.mark.parametrize("reply", [{"success": False, "error": "failed"}, {}])
def test_error_types_share_one_catchable_base(reply: dict[str, Any]) -> None:
    native = ScriptedNative({"title": reply})

    with pytest.raises(AgentBrowserError, match="title"):
        _browser(native).page.title()


@pytest.mark.parametrize(
    "action,clear",
    [
        ("requests", lambda namespaces: namespaces.network.clear_requests()),
        ("console", lambda namespaces: namespaces.diagnostics.clear_console()),
        ("errors", lambda namespaces: namespaces.diagnostics.clear_errors()),
    ],
)
def test_capture_buffers_clear_through_the_native_clear_flag(action: str, clear: Any) -> None:
    native = ScriptedNative({action: {"cleared": True}})

    assert clear(_browser(native)) is None

    async def run() -> None:
        browser = AsyncBrowser(_native_session=AsyncNativeSession(native=native))
        assert await clear(browser) is None

    asyncio.run(run())
    assert [
        _command_without_id(command) for command in native.commands if command["action"] == action
    ] == [
        {"action": action, "clear": True},
        {"action": action, "clear": True},
    ]


@pytest.mark.parametrize(
    "reply,expected",
    [
        ({"result": None, "unserializable": "Infinity"}, math.inf),
        ({"result": None, "unserializable": "-Infinity"}, -math.inf),
        ({"result": None, "unserializable": "12345678901234567890n"}, 12345678901234567890),
        ({"result": None, "unserializable": "undefined"}, None),
        ({"result": {"ok": True}}, {"ok": True}),
    ],
)
def test_page_evaluate_returns_python_values_for_javascript_results(
    reply: dict[str, Any], expected: object
) -> None:
    browser = _browser(ScriptedNative({"evaluate": reply}))

    assert browser.page.evaluate("value") == expected


def test_page_evaluate_keeps_negative_zero_and_nan() -> None:
    native = ScriptedNative(
        {"evaluate": lambda command: {"result": None, "unserializable": command["script"]}}
    )
    browser = _browser(native)

    assert math.copysign(1.0, browser.page.evaluate("-0")) == -1.0
    assert math.isnan(browser.page.evaluate("NaN"))


def test_route_rejects_a_response_for_an_aborted_route() -> None:
    browser = _browser(ScriptedNative(default={}))

    with pytest.raises(ValueError, match="abort"):
        browser.network.route("**/ads", RouteResponse(status=204), abort=True)
