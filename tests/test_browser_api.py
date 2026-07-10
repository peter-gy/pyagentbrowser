from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from threading import Event
from typing import Any, cast

import pytest
from fakes import ConfirmationNative, ScriptedNative

import agentbrowser
from agentbrowser import (
    AsyncBrowser,
    AsyncQuery,
    AsyncRef,
    AsyncSnapshot,
    Browser,
    BrowserError,
    CDPTarget,
    CloseResult,
    ConfirmationRequired,
    DashboardOptions,
    LaunchOptions,
    NativeParseError,
    Query,
    ReadMode,
    ReadResult,
    Ref,
    RestoreSaveError,
    Screenshot,
    SessionOptions,
    SessionStatus,
    Snapshot,
)
from agentbrowser.session import NativeSession
from agentbrowser.session_async import AsyncNativeSession

pytestmark = pytest.mark.sdk_dx


def _browser(native: Any) -> Browser:
    return Browser(_native_session=NativeSession(native=native))


def _command_without_id(command: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in command.items() if key != "id"}


def _session_status_data() -> dict[str, Any]:
    return {
        "session": "research",
        "namespace": "worker-a",
        "socketDir": "/tmp/agent-browser",
        "backgroundPid": 42,
        "browserLaunched": True,
        "pageCount": 2,
        "engine": "chrome",
        "launchHash": 101,
        "compatibilityStatus": "current",
        "restoreKey": "research",
        "restoreStatus": "loaded",
        "restoreStatusDetail": None,
        "restoreLoadedPath": "/tmp/research.json",
        "restoreValidationPending": False,
        "restoreSave": "always",
        "saveStatus": "saved",
        "restoreSavedPath": "/tmp/research.json",
        "restoreCheckUrl": None,
        "restoreCheckText": "Dashboard",
        "restoreCheckFn": None,
    }


def test_browser_core_is_agent_first_and_returns_typed_values() -> None:
    native = ScriptedNative(
        {
            "launch": {},
            "navigate": {},
            "title": {"title": "Example"},
            "url": {"url": "https://example.com/"},
        }
    )
    browser = _browser(native)

    assert browser.open("example.com", wait_until="domcontentloaded") is browser
    assert browser.title() == "Example"
    assert browser.url() == "https://example.com/"
    assert _command_without_id(native.commands[1]) == {
        "action": "navigate",
        "url": "https://example.com",
        "waitUntil": "domcontentloaded",
    }


@pytest.mark.parametrize("action,field", [("title", "title"), ("url", "url"), ("content", "html")])
def test_browser_core_rejects_missing_typed_fields(action: str, field: str) -> None:
    browser = _browser(ScriptedNative({action: {}}))

    with pytest.raises(NativeParseError, match=field):
        getattr(browser, action)()


def test_live_queries_share_one_type_and_capability_set() -> None:
    native = ScriptedNative(
        {
            "click": {},
            "getbyrole": {"text": "Save"},
        }
    )
    browser = _browser(native)

    css = browser.find.css("#save")
    role = browser.find.role("button", name="Save", exact=True)

    assert isinstance(css, Query)
    assert isinstance(role, Query)
    assert css.click() is css
    assert role.text() == "Save"
    assert native.commands[0]["selector"] == "#save"
    assert _command_without_id(native.commands[1]) == {
        "action": "getbyrole",
        "role": "button",
        "name": "Save",
        "exact": True,
        "subaction": "text",
    }


def test_query_factories_validate_empty_and_negative_inputs() -> None:
    browser = _browser(ScriptedNative(default={}))

    with pytest.raises(ValueError, match="selector"):
        browser.find.css("")
    with pytest.raises(ValueError, match="expression"):
        browser.find.xpath("xpath=")
    with pytest.raises(ValueError, match="exactly one"):
        Query(browser)
    with pytest.raises(ValueError, match="exactly one"):
        Query(browser, selector="#save", action="click")


@pytest.mark.parametrize(
    "factory,error,match",
    [
        (lambda: CDPTarget(), ValueError, "exactly one"),
        (lambda: CDPTarget(url=""), ValueError, "url"),
        (lambda: CDPTarget(port=0), ValueError, "port"),
        (lambda: SessionOptions(timeout=-1), ValueError, "timeout"),
        (lambda: SessionOptions(allowed_domains=("",)), ValueError, "allowed_domains"),
        (
            lambda: SessionOptions(allowed_domains=cast(Any, "example.com")),
            TypeError,
            "allowed_domains",
        ),
        (lambda: SessionOptions(confirm_actions=cast(Any, "click")), TypeError, "confirm_actions"),
        (lambda: LaunchOptions(extensions=cast(Any, "extension")), TypeError, "extensions"),
        (lambda: LaunchOptions(args=cast(Any, "--headless")), TypeError, "args"),
    ],
)
def test_public_configuration_rejects_ambiguous_values(
    factory: Any,
    error: type[Exception],
    match: str,
) -> None:
    with pytest.raises(error, match=match):
        factory()


def test_session_dashboard_requires_named_options() -> None:
    with pytest.raises(TypeError, match="DashboardOptions"):
        SessionOptions(dashboard=cast(Any, True))


def test_emulation_groups_environment_commands_and_hides_native_payloads() -> None:
    native = ScriptedNative({"viewport": {"width": 800, "height": 600}})
    browser = _browser(native)

    assert browser.emulation.viewport(800, 600, device_scale_factor=2) is None
    assert _command_without_id(native.commands[0]) == {
        "action": "viewport",
        "width": 800,
        "height": 600,
        "deviceScaleFactor": 2,
        "mobile": False,
    }


def test_dashboard_namespace_reports_status_and_stops_streaming() -> None:
    native = ScriptedNative(
        {
            "stream_status": {"enabled": True, "port": 4312},
            "stream_disable": {},
        }
    )
    browser = _browser(native)

    assert browser.dashboard.status()["port"] == 4312
    assert browser.dashboard.stop() is None


def test_session_namespace_returns_typed_lifecycle_status() -> None:
    native = ScriptedNative({"session_info": _session_status_data()})
    browser = _browser(native)

    status = browser.session.status()

    assert status == SessionStatus(
        session_id="research",
        namespace="worker-a",
        socket_dir=Path("/tmp/agent-browser"),
        background_pid=42,
        browser_launched=True,
        page_count=2,
        engine="chrome",
        launch_hash=101,
        compatibility_status="current",
        restore_key="research",
        restore_status="loaded",
        restore_status_detail=None,
        restore_loaded_path=Path("/tmp/research.json"),
        restore_validation_pending=False,
        restore_save="always",
        save_status="saved",
        restore_saved_path=Path("/tmp/research.json"),
        restore_check_url=None,
        restore_check_text="Dashboard",
        restore_check_fn=None,
        raw=_session_status_data(),
    )
    assert native.commands[0]["action"] == "session_info"


def test_session_status_requires_native_lifecycle_fields() -> None:
    data = _session_status_data()
    del data["restoreStatus"]
    browser = _browser(ScriptedNative({"session_info": data}))

    with pytest.raises(NativeParseError, match="restoreStatus"):
        browser.session.status()


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
    ],
)
def test_typed_collections_reject_missing_native_arrays(action: str, invoke: Any) -> None:
    browser = _browser(ScriptedNative({action: {}}))

    with pytest.raises(NativeParseError, match="array"):
        invoke(browser)


def test_console_messages_preserve_a_present_empty_collection() -> None:
    browser = _browser(ScriptedNative({"console": {"messages": []}}))

    assert browser.diagnostics.console() == ()


@pytest.mark.parametrize(
    "name",
    [
        "ConsoleMessage",
        "Cookie",
        "CloseResult",
        "NetworkRequest",
        "ProxyConfig",
        "RequestDetail",
        "RestoreSaveError",
        "RouteResponse",
        "SessionId",
        "SessionStatus",
        "TabInfo",
    ],
)
def test_public_contract_types_are_package_exports(name: str) -> None:
    assert name in agentbrowser.__all__
    assert getattr(agentbrowser, name).__module__ == "agentbrowser.models"


def test_screenshot_rejects_a_missing_native_path() -> None:
    browser = _browser(ScriptedNative({"screenshot": {}}))

    with pytest.raises(NativeParseError, match="path"):
        browser.capture.screenshot(wait_ms=0)


@pytest.mark.parametrize(
    "action,reply,invoke,attribute,expected",
    [
        (
            "tab_list",
            {"tabs": [{"id": "tab-1", "url": "https://example.com"}]},
            lambda browser: browser.tabs.list()[0],
            "id",
            "tab-1",
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
            {"requests": [{"id": "request-1", "url": "https://example.com/data"}]},
            lambda browser: browser.network.requests()[0],
            "id",
            "request-1",
        ),
        (
            "request_detail",
            {"id": "request-1", "url": "https://example.com/data", "status": 200},
            lambda browser: browser.network.request_detail("request-1"),
            "status",
            200,
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
                status=201,
                body="created",
                content_type="text/plain",
            ),
            "route",
            {
                "url": "**/api",
                "abort": False,
                "response": {"status": 201, "body": "created", "contentType": "text/plain"},
            },
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
            lambda browser: browser.active_frame.select(name="checkout"),
            "frame",
            {"name": "checkout"},
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


def test_path_namespaces_return_typed_paths(tmp_path: Path) -> None:
    pdf = tmp_path / "page.pdf"
    state = tmp_path / "state.json"
    download = tmp_path / "report.csv"
    native = ScriptedNative(
        {
            "pdf": lambda command: {"path": command["path"]},
            "state_save": lambda command: {"path": command["path"]},
            "waitfordownload": {"path": str(download)},
        }
    )
    browser = _browser(native)

    assert browser.capture.pdf(pdf, landscape=True) == pdf
    assert browser.state.save(state, unsafe_export_all=True) == state
    assert browser.downloads.wait() == download
    assert native.commands[0]["landscape"] is True
    assert native.commands[1]["unsafeExportAll"] is True


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


def test_tabs_open_confirmation_continues_switch_and_navigation() -> None:
    existing = {
        "id": "existing",
        "url": "https://example.com/old",
        "label": "work",
    }
    native = ScriptedNative(
        {
            "tab_list": {"tabs": [existing]},
            "tab_switch": {
                "success": True,
                "data": {
                    "confirmation_required": True,
                    "confirmation_id": "confirm-switch",
                    "action": "tab_switch",
                },
            },
            "confirm": {
                "success": True,
                "data": {
                    "confirmed": True,
                    "action": "tab_switch",
                    "result": {"id": "confirmed-switch", "success": True, "data": {}},
                },
            },
            "navigate": {},
        }
    )
    browser = _browser(native)

    with pytest.raises(ConfirmationRequired) as required:
        browser.tabs.open("example.com/new", label="work", wait_until="domcontentloaded")

    tab = required.value.pending.confirm()

    assert tab.id == "existing"
    assert tab.url == "https://example.com/new"
    assert tab.active is True
    assert [command["action"] for command in native.commands] == [
        "tab_list",
        "tab_switch",
        "confirm",
        "navigate",
    ]
    assert _command_without_id(native.commands[1]) == {
        "action": "tab_switch",
        "tabId": "existing",
    }
    assert _command_without_id(native.commands[-1]) == {
        "action": "navigate",
        "url": "https://example.com/new",
        "waitUntil": "domcontentloaded",
    }


def test_diff_namespace_returns_a_typed_snapshot_diff() -> None:
    browser = _browser(
        ScriptedNative(
            {
                "diff_snapshot": {
                    "diff": "+ ready",
                    "additions": 1,
                    "removals": 0,
                    "unchanged": 2,
                    "changed": True,
                }
            }
        )
    )

    diff = browser.diff.snapshot("baseline")

    assert diff.changed is True
    assert diff.additions == 1


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

    shot = browser.capture.screenshot(path, annotate=True, wait_ms=0)
    copied = shot.save(tmp_path / "copy.png")

    assert shot.bytes() == b"png-bytes"
    assert shot.annotations[0].name == "Save"
    assert copied.bytes() == b"png-bytes"
    assert native.commands[0]["annotate"] is True


def test_read_returns_typed_content_and_serializes_mode() -> None:
    native = ScriptedNative(
        {
            "read": {
                "url": "https://example.com/docs",
                "finalUrl": "https://example.com/docs",
                "status": 200,
                "contentType": "text/markdown",
                "source": "accept-markdown-outline",
                "truncated": False,
                "content": "# Outline\n",
            }
        }
    )
    browser = _browser(native)

    result = browser.read(
        "example.com/docs",
        mode=ReadMode.outline_only(),
        timeout_ms=1_000,
    )

    assert isinstance(result, ReadResult)
    assert result.content == "# Outline\n"
    assert native.commands[0]["url"] == "https://example.com/docs"
    assert native.commands[0]["outline"] is True
    assert native.commands[0]["timeout"] == 1_000


def test_typed_confirmation_resumes_the_original_decoder(tmp_path: Path) -> None:
    path = tmp_path / "shot.png"
    path.write_bytes(b"png")
    browser = _browser(ConfirmationNative(action="screenshot", result={"path": str(path)}))

    with pytest.raises(ConfirmationRequired) as required:
        browser.capture.screenshot(path, wait_ms=0)

    result = required.value.pending.confirm()
    assert isinstance(result, Screenshot)
    assert result.path == path


def test_confirmed_page_value_keeps_its_public_type() -> None:
    browser = _browser(ConfirmationNative(action="title", result={"title": "Confirmed"}))

    with pytest.raises(ConfirmationRequired) as required:
        browser.title()

    assert required.value.pending.confirm() == "Confirmed"


def test_confirmed_query_action_returns_the_same_query() -> None:
    browser = _browser(ConfirmationNative(action="click", result={}))
    query = browser.find.css("#save")

    with pytest.raises(ConfirmationRequired) as required:
        query.click()

    assert required.value.pending.confirm() is query


def test_pending_action_maps_compose_in_call_order() -> None:
    browser = _browser(ConfirmationNative(action="probe", result={"value": 20}))

    with pytest.raises(ConfirmationRequired) as required:
        browser.native.data("probe")

    pending = required.value.pending
    result = pending.map(lambda data: data["value"]).map(lambda value: value * 2).confirm()
    assert result == 40


def test_pending_denial_forwards_the_confirmation_token_and_returns_none() -> None:
    native = ConfirmationNative(action="probe")
    browser = _browser(native)

    with pytest.raises(ConfirmationRequired) as required:
        browser.native.data("probe")

    assert required.value.pending.deny() is None
    assert native.commands[-1]["confirmation_id"] == required.value.confirmation_id


def test_close_is_idempotent_and_browser_cannot_be_reused() -> None:
    native = ScriptedNative(
        {
            "__agent_browser_internal_shutdown": {
                "closed": True,
                "restoreStatus": "loaded",
                "saveStatus": "saved",
                "statePath": "/tmp/research.json",
            }
        }
    )
    browser = _browser(native)

    first = browser.close()
    second = browser.close()

    assert first is second
    assert first == CloseResult(
        closed=True,
        restore_status="loaded",
        save_status="saved",
        state_path=Path("/tmp/research.json"),
        raw={
            "closed": True,
            "restoreStatus": "loaded",
            "saveStatus": "saved",
            "statePath": "/tmp/research.json",
        },
    )
    assert browser.closed is True
    assert len(native.commands) == 1
    with pytest.raises(RuntimeError, match="closed"):
        browser.native.data("probe")


def test_close_surfaces_restore_save_errors_after_terminal_cleanup() -> None:
    native = ScriptedNative(
        {
            "__agent_browser_internal_shutdown": {
                "closed": True,
                "restoreStatus": "loaded",
                "saveStatus": "error",
                "saveError": "permission denied",
            }
        }
    )
    browser = _browser(native)

    with pytest.raises(RestoreSaveError, match="permission denied") as failed:
        browser.close()

    assert failed.value.result.closed is True
    assert browser.closed is True
    with pytest.raises(RestoreSaveError, match="permission denied"):
        browser.close()


def test_close_rejects_missing_native_save_status() -> None:
    browser = _browser(
        ScriptedNative(
            {
                "__agent_browser_internal_shutdown": {
                    "closed": True,
                    "restoreStatus": "loaded",
                }
            }
        )
    )

    with pytest.raises(NativeParseError, match="saveStatus"):
        browser.close()
    assert browser.closed is True
    with pytest.raises(NativeParseError, match="saveStatus"):
        browser.close()


def test_closing_an_unused_browser_does_not_start_its_native_session() -> None:
    session = NativeSession()
    browser = Browser(_native_session=session)

    assert session.started is False
    result = browser.close()
    assert session.started is False
    assert browser.closed is True
    assert result == CloseResult(closed=True)


def test_public_options_use_named_types_and_python_units(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class CapturingSession:
        def __init__(self, **options: Any) -> None:
            captured.update(options)

    monkeypatch.setattr("agentbrowser.browser.NativeSession", CapturingSession)
    session = SessionOptions(
        timeout=2.5,
        allowed_domains=("example.com", "*.example.org"),
        confirm_actions=("click",),
        auto_dialogs=False,
        dashboard=DashboardOptions(port=0),
    )

    Browser(session=session)
    assert captured["default_timeout_ms"] == 2500
    assert captured["allowed_domains"] == "example.com,*.example.org"
    assert captured["confirm_actions"] == ("click",)
    assert captured["no_auto_dialog"] is True
    assert captured["dashboard"] == DashboardOptions(port=0)
    assert LaunchOptions(headless=False).headless is False
    with pytest.raises(TypeError, match="LaunchOptions"):
        cast(Any, Browser.launch)({"headless": True})


def test_async_core_uses_the_same_nouns() -> None:
    async def run() -> None:
        native = ScriptedNative(
            {
                "launch": {},
                "navigate": {},
                "title": {"title": "Async"},
                "session_info": _session_status_data(),
                "__agent_browser_internal_shutdown": {
                    "closed": True,
                    "restoreStatus": "loaded",
                    "saveStatus": "saved",
                },
            }
        )
        browser = AsyncBrowser(
            _native_session=AsyncNativeSession(native=native),
        )

        assert await browser.open("example.com") is browser
        assert await browser.title() == "Async"
        assert (await browser.session.status()).restore_status == "loaded"
        result = await browser.close()
        assert result.save_status == "saved"
        assert await browser.close() is result
        assert browser.closed is True

    asyncio.run(run())


def test_async_close_is_single_flight() -> None:
    async def run() -> None:
        started = Event()
        release = Event()

        def close_reply(_command: dict[str, Any]) -> dict[str, Any]:
            started.set()
            release.wait(timeout=5)
            return {
                "closed": True,
                "restoreStatus": "not_configured",
                "saveStatus": "not_configured",
            }

        native = ScriptedNative(
            {
                "probe": {},
                "__agent_browser_internal_shutdown": close_reply,
            }
        )
        browser = AsyncBrowser(_native_session=AsyncNativeSession(native=native))
        await browser.native.data("probe")

        first_close = asyncio.create_task(browser.close())
        assert await asyncio.to_thread(started.wait, 1)
        second_close = asyncio.create_task(browser.close())
        await asyncio.sleep(0)
        assert second_close.done() is False
        release.set()
        first, second = await asyncio.gather(first_close, second_close)

        assert first is second
        assert [
            command["action"]
            for command in native.commands
            if command["action"] == "__agent_browser_internal_shutdown"
        ] == ["__agent_browser_internal_shutdown"]

    asyncio.run(run())


def test_async_close_replays_the_terminal_decode_error() -> None:
    async def run() -> None:
        native = ScriptedNative(
            {
                "probe": {},
                "__agent_browser_internal_shutdown": {
                    "closed": True,
                    "restoreStatus": "loaded",
                },
            }
        )
        browser = AsyncBrowser(_native_session=AsyncNativeSession(native=native))
        await browser.native.data("probe")

        for _attempt in range(2):
            with pytest.raises(NativeParseError, match="saveStatus"):
                await browser.close()

        assert [
            command["action"]
            for command in native.commands
            if command["action"] == "__agent_browser_internal_shutdown"
        ] == ["__agent_browser_internal_shutdown"]

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
                "tab_switch": {},
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


def _public_methods(target: type[Any]) -> set[str]:
    methods: set[str] = set()
    for name in dir(target):
        if name.startswith("_"):
            continue
        value = inspect.getattr_static(target, name)
        if callable(value) or isinstance(value, classmethod | staticmethod):
            methods.add(name)
    return methods


def test_sync_and_async_public_surfaces_keep_method_and_signature_parity() -> None:
    type_pairs = (
        (Browser, AsyncBrowser),
        (Query, AsyncQuery),
        (Ref, AsyncRef),
        (Snapshot, AsyncSnapshot),
    )
    for sync_type, async_type in type_pairs:
        sync_methods = _public_methods(sync_type)
        async_methods = _public_methods(async_type)
        assert async_methods == sync_methods, sync_type.__name__
        for name in sync_methods:
            sync_parameters = inspect.signature(getattr(sync_type, name)).parameters
            async_parameters = inspect.signature(getattr(async_type, name)).parameters
            if sync_type is Browser and name == "close":
                assert tuple(sync_parameters) == ("self",)
                assert tuple(async_parameters) == ("self", "timeout")
                continue
            assert async_parameters == sync_parameters, f"{sync_type.__name__}.{name}"

    sync_browser = _browser(ScriptedNative(default={}))
    async_browser = AsyncBrowser(
        _native_session=AsyncNativeSession(native=ScriptedNative(default={})),
    )
    sync_namespaces = {
        name: value for name, value in vars(sync_browser).items() if not name.startswith("_")
    }
    async_namespaces = {
        name: value for name, value in vars(async_browser).items() if not name.startswith("_")
    }
    assert async_namespaces.keys() == sync_namespaces.keys()
    for name, sync_namespace in sync_namespaces.items():
        async_namespace = async_namespaces[name]
        sync_methods = _public_methods(type(sync_namespace))
        async_methods = _public_methods(type(async_namespace))
        assert async_methods == sync_methods, name
        for method in sync_methods:
            sync_parameters = inspect.signature(getattr(sync_namespace, method)).parameters
            async_parameters = inspect.signature(getattr(async_namespace, method)).parameters
            assert async_parameters == sync_parameters, f"{name}.{method}"


def test_error_types_share_one_catchable_base() -> None:
    native = ScriptedNative({"title": {"success": False, "error": "failed"}})

    with pytest.raises(BrowserError, match="title failed"):
        _browser(native).title()
