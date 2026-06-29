from __future__ import annotations

import asyncio
import hashlib
import importlib
import inspect
import json
import sys
import types
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import pytest
from fakes import (
    LIFECYCLE_CLOSE_ACTIONS,
    AgentNative,
    BlockingNative,
    CloseErrorNative,
    ConfirmationNative,
    ConfirmedCookieNative,
    ConfirmingActionNative,
    EchoNative,
    ErrorNative,
    FailingConfirmationNative,
    RawValueNative,
    ScreenshotNative,
    StatefulConfirmationNative,
)

import agentbrowser as ab
from agentbrowser import (
    ActionConfirmationRequired,
    AgentBrowserError,
    AsyncBrowser,
    AsyncPendingAction,
    BoundingBox,
    Browser,
    BrowserError,
    BrowserInstallError,
    BrowserResponse,
    BrowserSessionOptions,
    CDPAttach,
    CDPClosedError,
    ConfirmationTarget,
    ConsoleMessage,
    Cookie,
    InstallResult,
    LaunchOptions,
    NativeParseError,
    NetworkRequest,
    PendingAction,
    ProxyConfig,
    ReadMode,
    ReadResult,
    RequestDetail,
    RestoreOptions,
    RouteResponse,
    Screenshot,
    SessionId,
    StaleAgentRefError,
    TabInfo,
)
from agentbrowser.cdp import CDPStaleObjectError
from agentbrowser.session import NativeSession
from agentbrowser.session_async import AsyncNativeSession

pytestmark = pytest.mark.sdk_dx

_BROWSER_NAMESPACE_NAMES = {
    "active_frame",
    "agent",
    "capture",
    "cdp",
    "clipboard",
    "cookies",
    "dashboard",
    "dialogs",
    "diagnostics",
    "diff",
    "downloads",
    "find",
    "keyboard",
    "mouse",
    "native",
    "network",
    "page",
    "restore",
    "runtime",
    "scripts",
    "state",
    "storage",
    "tabs",
}
_DEFAULT_NAMESPACE_NAMES = _BROWSER_NAMESPACE_NAMES

_ROOT_EXPORT_CONTRACT = {
    "ActionConfirmationRequired",
    "AgentBrowserError",
    "AgentSnapshot",
    "AsyncBrowser",
    "AsyncPendingAction",
    "Browser",
    "BrowserError",
    "BrowserInstallError",
    "BrowserResponse",
    "BrowserSessionOptions",
    "BrowserSessionOptionsDict",
    "CDPAttach",
    "CDPAttachDict",
    "CDPClosedError",
    "CDPError",
    "ConfirmationTarget",
    "Cookie",
    "DashboardOptions",
    "Frame",
    "InstallResult",
    "LaunchOptions",
    "LaunchOptionsDict",
    "NativeParseError",
    "NetworkRequest",
    "PendingAction",
    "ProxyConfig",
    "ReadMode",
    "ReadResult",
    "RouteResponse",
    "RestoreOptions",
    "RestoreSave",
    "Screenshot",
    "Skill",
    "Snapshot",
    "SnapshotRef",
    "SessionId",
    "SessionIdScope",
    "session_id",
    "StaleAgentRefError",
    "TabInfo",
    "__agent_browser_commit__",
    "__agent_browser_version__",
    "__upstream_commit__",
    "__upstream_version__",
    "__version__",
    "close",
    "configure",
    "default_browser",
    "ensure_installed",
    "reset",
    "skills",
    *_DEFAULT_NAMESPACE_NAMES,
}


class ResponseNative:
    def __init__(
        self,
        responses: Mapping[str, Mapping[str, Any] | list[Mapping[str, Any]]] | None = None,
    ) -> None:
        self.commands: list[dict[str, Any]] = []
        self.responses = dict(responses or {})

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        self.commands.append(command)
        response = self.responses.get(command["action"], {})
        data = response.pop(0) if isinstance(response, list) else response
        data_mapping = cast(Mapping[str, Any], data)
        return json.dumps({"id": command["id"], "success": True, "data": dict(data_mapping)})


class _CDPNative:
    def __init__(self) -> None:
        self.commands: list[dict[str, Any]] = []
        self.current_url = "https://example.com/one"

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        self.commands.append(command)
        action = command["action"]
        if action == "navigate":
            self.current_url = str(command["url"])
        elif action == "tab_switch":
            self.current_url = "https://example.com/two"

        data: Mapping[str, Any]
        if action == "cdp_url":
            data = {"cdpUrl": "ws://cdp"}
        elif action == "url":
            data = {"url": self.current_url}
        elif action == "frame":
            data = {"frame": command.get("selector") or command.get("name") or command.get("url")}
        elif action == "mainframe":
            data = {"frame": "main"}
        else:
            data = {"echo": command}
        return json.dumps({"id": command["id"], "success": True, "data": data})


class _PublicCDPClient:
    def __init__(self, _url: str) -> None:
        self._pending_events: list[Mapping[str, Any]] = []
        self._attached = 0

    def send(
        self,
        method: str,
        params: Mapping[str, Any] | None = None,
        *,
        session_id: str | None = None,
    ) -> Mapping[str, Any]:
        params_dict = dict(params or {})
        if method == "Target.getTargets":
            return {
                "targetInfos": [
                    {
                        "targetId": "one",
                        "type": "page",
                        "url": "https://example.com/one",
                        "title": "One",
                    },
                    {
                        "targetId": "two",
                        "type": "page",
                        "url": "https://example.com/two",
                        "title": "Two",
                    },
                ]
            }
        if method == "Target.attachToTarget":
            self._attached += 1
            target_id = str(params_dict["targetId"])
            session = f"s-{target_id}-{self._attached}"
            self._pending_events = [
                _cdp_context_event(session, 1, f"{session}-main", "main"),
                _cdp_context_event(session, 2, f"{session}-child", "child"),
            ]
            return {"sessionId": session}
        if method in {"Page.enable", "DOM.enable", "Runtime.enable"}:
            return {}
        if method == "Page.getFrameTree":
            return {
                "frameTree": {
                    "frame": {"id": "main", "name": "", "url": "https://example.com"},
                    "childFrames": [
                        {
                            "frame": {
                                "id": "child",
                                "name": "target",
                                "url": "https://example.com/one/frame",
                            }
                        }
                    ],
                }
            }
        if method == "DOM.getDocument":
            return {"root": {"nodeId": 1}}
        if method == "DOM.querySelector":
            return {"nodeId": 2}
        if method == "DOM.describeNode":
            return {"node": {"nodeName": "IFRAME", "frameId": "child"}}
        if method == "Runtime.evaluate":
            context = params_dict.get("uniqueContextId", params_dict.get("contextId"))
            return {"result": {"type": "string", "value": f"context:{context}"}}
        raise AssertionError(f"unexpected CDP method {method}")

    def drain_events(self, *, timeout: float = 0.05) -> list[Mapping[str, Any]]:
        events = self._pending_events
        self._pending_events = []
        return events

    def close(self) -> None:
        pass


def _cdp_context_event(
    session_id: str,
    context_id: int,
    unique_id: str,
    frame_id: str,
) -> Mapping[str, Any]:
    return {
        "sessionId": session_id,
        "method": "Runtime.executionContextCreated",
        "params": {
            "context": {
                "id": context_id,
                "uniqueId": unique_id,
                "origin": "https://example.com",
                "name": "",
                "auxData": {"frameId": frame_id, "type": "default", "isDefault": True},
            }
        },
    }


class TabReuseNative:
    def __init__(self) -> None:
        self.switched_label: str | None = None
        self.navigated_url: str | None = None

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        active = self.switched_label == "t1" and self.navigated_url == "https://example.com/docs"
        if command["action"] == "tab_list":
            data = {
                "tabs": [
                    {
                        "tabId": "t1",
                        "label": "docs",
                        "url": self.navigated_url or "https://example.com/docs",
                        "active": active,
                    }
                ]
            }
        elif command["action"] == "tab_switch":
            self.switched_label = str(command["tabId"])
            data = {}
        elif command["action"] == "navigate":
            self.navigated_url = str(command["url"])
            data = {}
        elif command["action"] in LIFECYCLE_CLOSE_ACTIONS:
            data = {}
        else:
            raise AssertionError(f"unexpected action {command['action']}")
        return json.dumps({"id": command["id"], "success": True, "data": data})


class CdpConnectNative:
    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        action = command["action"]
        if action == "launch":
            data = {
                "launched": command.get("cdpUrl") == "ws://127.0.0.1:9222/devtools/browser/test"
            }
        elif action == "tab_list":
            data = {"tabs": [{"id": "t1", "url": "about:blank"}]}
        elif action in LIFECYCLE_CLOSE_ACTIONS:
            data = {}
        elif action == "navigate":
            raise AssertionError("connect must not navigate")
        else:
            data = {}
        return json.dumps({"id": command["id"], "success": True, "data": data})


class CdpPortConnectNative:
    def __init__(self) -> None:
        self.connected = False

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        action = command["action"]
        if action == "launch":
            self.connected = (
                command.get("cdpPort") == 52980 and command.get("hideScrollbars") is False
            )
            data = {"attached": self.connected}
        elif action == "tab_list":
            if not self.connected:
                raise AssertionError("tab_list requires configured CDP attachment")
            data = {"tabs": [{"id": "t1", "url": "about:blank"}]}
        elif action in LIFECYCLE_CLOSE_ACTIONS:
            data = {}
        elif action == "navigate":
            raise AssertionError("configure connect must not navigate")
        else:
            data = {}
        return json.dumps({"id": command["id"], "success": True, "data": data})


class SemanticLocatorNative:
    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        action = command["action"]
        if action == "getbyrole" and command.get("role") == "button":
            if command.get("name") != "Submit" or command.get("subaction") != "click":
                raise AssertionError(f"unexpected semantic role command: {command}")
            data = {"clicked": True}
        elif action == "getbyplaceholder":
            data = {"text": "Email"}
        elif action == "getbyalttext":
            data = {"text": "Logo"}
        elif action == "getbytitle":
            data = {"text": "Help"}
        elif action in LIFECYCLE_CLOSE_ACTIONS:
            data = {}
        else:
            raise AssertionError(f"unexpected semantic locator command: {command}")
        return json.dumps({"id": command["id"], "success": True, "data": data})


class LocatorStateNative:
    def __init__(self) -> None:
        self.checked = False
        self.waited = False
        self.typed_text: str | None = None

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        action = command["action"]
        selector = command.get("selector")
        if selector != "#email" and action not in LIFECYCLE_CLOSE_ACTIONS:
            raise AssertionError(f"unexpected locator target: {command}")
        if action == "check":
            self.checked = True
            data = {}
        elif action == "wait":
            if command.get("timeout") != 500:
                raise AssertionError(f"unexpected locator wait: {command}")
            self.waited = True
            data = {}
        elif action == "type":
            self.typed_text = str(command.get("text"))
            data = {}
        elif action == "inputvalue":
            data = {"value": self.typed_text or ""}
        elif action in LIFECYCLE_CLOSE_ACTIONS:
            data = {}
        else:
            raise AssertionError(f"unexpected locator action: {command}")
        return json.dumps({"id": command["id"], "success": True, "data": data})


class CookieNative:
    def __init__(self) -> None:
        self.commands: list[dict[str, Any]] = []

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        self.commands.append(command)
        if command["action"] == "cookies_get":
            data = {
                "cookies": [
                    {"name": "kept", "value": "1", "domain": ".example.com"},
                    {"name": "dropped", "value": "1", "domain": "evil.example"},
                    {"name": "missing-domain", "value": "1"},
                ]
            }
            return json.dumps({"id": command["id"], "success": True, "data": data})
        if command["action"] == "cookies_clear":
            return json.dumps({"id": command["id"], "success": True, "data": {"cleared": True}})
        return json.dumps({"id": command["id"], "success": True, "data": {}})


def _mixed_storage_state() -> dict[str, Any]:
    return {
        "cookies": [
            {"name": "kept", "value": "1", "domain": "example.com"},
            {"name": "dropped", "value": "1", "domain": "evil.example"},
        ],
        "origins": [
            {
                "origin": "https://example.com",
                "localStorage": [{"name": "theme", "value": "dark"}],
            },
            {
                "origin": "https://evil.example",
                "localStorage": [{"name": "token", "value": "secret"}],
            },
        ],
    }


class StorageStateNative:
    def __init__(self, state: Mapping[str, Any]) -> None:
        self.state = state
        self.commands: list[dict[str, Any]] = []
        self.loaded_state: Mapping[str, Any] | None = None

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        self.commands.append(command)
        if command["action"] == "state_load":
            self.loaded_state = json.loads(Path(command["path"]).read_text())
            return json.dumps({"id": command["id"], "success": True, "data": {}})
        if command["action"] == "state_save":
            Path(command["path"]).write_text(json.dumps(self.state))
            return json.dumps(
                {
                    "id": command["id"],
                    "success": True,
                    "data": {"path": command["path"]},
                }
            )
        return json.dumps({"id": command["id"], "success": True, "data": {}})


class ClipboardNative:
    def __init__(self) -> None:
        self.written_text: str | None = None

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        data: Mapping[str, Any]
        if command["action"] == "clipboard" and command.get("subAction") == "read":
            data = {"text": "hello"}
        elif command["action"] == "clipboard" and command.get("subAction") == "write":
            self.written_text = str(command["text"])
            data = {}
        else:
            raise AssertionError(f"unexpected clipboard command: {command}")
        return json.dumps({"id": command["id"], "success": True, "data": data})


class ReadmeWorkflowNative:
    def __init__(self) -> None:
        self.clicked_more = False
        self.current_url = "https://example.com"

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        action = command["action"]
        if action == "launch":
            data = {"launched": True}
        elif action == "navigate":
            data = {}
        elif action == "snapshot":
            data = {
                "snapshot": '@e1 [link] "Learn more"',
                "origin": "https://example.com",
                "refs": {"e1": {"role": "link", "name": "Learn more"}},
            }
        elif action == "getbytext" and command.get("text") == "Learn more":
            self.clicked_more = command.get("subaction") == "click"
            self.current_url = "https://www.iana.org/help/example-domains"
            data = {}
        elif action == "wait" and command.get("url") == "*://www.iana.org/*":
            data = {}
        elif action == "title" and self.clicked_more:
            data = {"title": "Example Domains"}
        elif action == "url" and self.clicked_more:
            data = {"url": self.current_url}
        elif action in LIFECYCLE_CLOSE_ACTIONS:
            data = {}
        else:
            raise AssertionError(f"unexpected workflow action {command}")
        return json.dumps({"id": command["id"], "success": True, "data": data})


def test_browser_native_data_preserves_raw_escape_hatch_payload() -> None:
    native = EchoNative()
    browser = Browser(native_session=NativeSession(native=native))

    browser.native.data("raw_null", value=None, nested={"keep": None})

    assert native.commands[0]["action"] == "raw_null"
    assert native.commands[0]["value"] is None
    assert native.commands[0]["nested"] == {"keep": None}


def test_browser_page_open_normalizes_host_like_url() -> None:
    native = EchoNative()
    browser = Browser(native_session=NativeSession(native=native))

    browser.page.open("example.com", wait_until="domcontentloaded")

    navigation = next(command for command in native.commands if command["action"] == "navigate")
    assert navigation["url"] == "https://example.com"
    assert navigation["waitUntil"] == "domcontentloaded"


def test_browser_tabs_new_uses_public_namespace() -> None:
    native = ResponseNative(
        {"tab_new": {"tab": {"id": "t1", "url": "https://example.com/docs", "label": "docs"}}}
    )
    browser = Browser(native_session=NativeSession(native=native))

    tab = browser.tabs.new("https://example.com/docs", label="docs")

    assert tab.id == "t1"
    assert tab.label == "docs"


def test_browser_tabs_list_uses_public_namespace() -> None:
    browser = Browser(native_session=NativeSession(native=ResponseNative()))

    tabs = browser.tabs.list()

    assert tabs == ()


def test_browser_semantic_locator_click_returns_chainable_handle() -> None:
    native = SemanticLocatorNative()
    browser = Browser(native_session=NativeSession(native=native))
    submit = browser.find.role("button", name="Submit", exact=True)

    assert submit.click() is submit


def test_browser_default_timeout_is_15_seconds() -> None:
    assert BrowserSessionOptions().default_timeout_ms == 15_000


def test_native_execute_returns_browser_response() -> None:
    browser = Browser(native_session=NativeSession(native=EchoNative()))

    response = browser.native.execute("launch")

    assert isinstance(response, BrowserResponse)
    assert response.success is True


def test_native_execute_pending_confirmation_can_be_confirmed() -> None:
    browser = Browser(native_session=NativeSession(native=ConfirmationNative()))

    response = browser.native.execute("click")
    response_data = cast(dict[str, Any], response.data)
    pending = browser.pending_action(response)

    assert response_data["confirmation_required"] is True
    assert isinstance(pending, PendingAction)
    assert pending.confirm() == {"clicked": "#danger"}


def test_native_execute_launch_marks_browser_launched() -> None:
    browser = Browser(native_session=NativeSession(native=EchoNative()))

    browser.native.execute("launch")

    assert browser.is_launched is True


def test_native_execute_close_marks_browser_not_launched() -> None:
    browser = Browser(native_session=NativeSession(native=EchoNative()))
    browser.native.execute("launch")

    browser.native.execute("close")

    assert browser.is_launched is False


def test_native_execute_confirm_unwraps_nested_failure_and_clears_pending() -> None:
    browser = Browser(native_session=NativeSession(native=FailingConfirmationNative()))

    response = browser.native.execute("click")
    response_data = cast(dict[str, Any], response.data)
    assert response_data["confirmation_required"] is True

    confirmed = browser.native.execute("confirm", confirmation_id=response_data["confirmation_id"])

    assert confirmed.success is False
    assert confirmed.action == "click"
    with pytest.raises(TypeError):
        cast(Any, browser.confirm)()


def test_pending_action_reports_confirmed_action_failure() -> None:
    browser = Browser(native_session=NativeSession(native=FailingConfirmationNative()))

    with pytest.raises(ActionConfirmationRequired) as confirmation:
        browser.native.data("click")
    pending = confirmation.value.pending_action
    with pytest.raises(BrowserError) as failed:
        pending.confirm()

    assert failed.value.action == "click"
    with pytest.raises(BrowserError) as retry_failed:
        pending.confirm()
    assert retry_failed.value.action == "click"


def test_failed_confirm_validation_keeps_pending_confirmation_for_retry() -> None:
    browser = Browser(
        native_session=NativeSession(
            native=StatefulConfirmationNative(fail_confirm_before_consuming=True)
        )
    )

    response = browser.native.execute("click")
    pending = browser.pending_action(response)
    with pytest.raises(BrowserError) as first_confirm:
        pending.confirm()
    retry = pending.confirm()

    assert first_confirm.value.action == "confirm"
    assert retry == {"clicked": "#danger"}


def test_confirmed_close_marks_browser_not_launched() -> None:
    native = ConfirmingActionNative("close")
    browser = Browser(native_session=NativeSession(native=native))
    browser.launch_process()

    browser.close()

    assert native.commands[-1]["action"] == "__agent_browser_internal_shutdown"
    assert browser.is_launched is False


def test_confirmed_navigation_marks_browser_launched() -> None:
    native = ConfirmingActionNative("navigate", {"url": "https://example.com"})
    browser = Browser(native_session=NativeSession(native=native))

    with pytest.raises(ActionConfirmationRequired) as confirmation:
        browser.page.open("example.com")

    confirmation.value.pending_action.confirm()

    assert browser.is_launched is True


def test_native_execute_confirmed_tab_switch_returns_native_tab_data() -> None:
    native = ConfirmingActionNative("tab_switch", {"id": "docs"})
    browser = Browser(native_session=NativeSession(native=native))

    with pytest.raises(ActionConfirmationRequired) as confirmation:
        browser.tabs.switch(id="docs")

    response = browser.native.execute("confirm", confirmation_id=confirmation.value.confirmation_id)

    assert response.success is True
    assert response.data == {"id": "docs"}


def test_native_data_can_return_non_object_protocol_data() -> None:
    browser = Browser(native_session=NativeSession(native=RawValueNative(["ok", 1, None])))

    assert browser.native.data("raw_array", expect="any") == ["ok", 1, None]


def test_native_execute_preserves_non_object_protocol_data() -> None:
    browser = Browser(native_session=NativeSession(native=RawValueNative(["ok", 1, None])))

    response = browser.native.execute("raw_array")

    assert response.data == ["ok", 1, None]


def test_native_data_rejects_non_object_protocol_data_by_default() -> None:
    browser = Browser(native_session=NativeSession(native=RawValueNative(["ok", 1, None])))

    with pytest.raises(BrowserError, match='expect="any"'):
        browser.native.data("raw_array")


def test_launch_without_url_marks_browser_launched() -> None:
    native = EchoNative()
    browser = Browser(native_session=NativeSession(native=native))

    browser.launch_process()

    launch = next(command for command in native.commands if command["action"] == "launch")
    assert "url" not in launch
    assert browser.is_launched is True


def test_restore_options_are_attached_to_native_commands() -> None:
    native = EchoNative()
    browser = Browser(
        native_session=NativeSession(
            native=native,
            session="next-loop",
            restore=RestoreOptions(
                key="next-loop",
                save="never",
                check_url="**/dashboard",
                check_text="Dashboard",
                check_fn="window.ready === true",
            ),
        ),
    )

    browser.page.open("https://example.com/dashboard")

    command = native.commands[0]
    assert command["action"] == "launch"
    assert command["restoreKey"] == "next-loop"
    assert command["restoreSave"] == "never"
    assert command["restoreCheckUrl"] == "**/dashboard"
    assert command["restoreCheckText"] == "Dashboard"
    assert command["restoreCheckFn"] == "window.ready === true"


def test_restore_accepts_explicit_key() -> None:
    native = EchoNative()
    browser = Browser(
        native_session=NativeSession(
            native=native,
            restore=RestoreOptions(key="login-state"),
        )
    )

    browser.launch_process()

    command = native.commands[0]
    assert command["action"] == "launch"
    assert command["restoreKey"] == "login-state"


def test_restore_options_reject_invalid_key() -> None:
    with pytest.raises(ValueError, match="Invalid restore key"):
        RestoreOptions(key="")


def test_browser_rejects_ignored_native_session_restore_options() -> None:
    with pytest.raises(ValueError, match="restore must be set on NativeSession"):
        Browser(
            session=BrowserSessionOptions(restore=RestoreOptions(key="login-state")),
            native_session=NativeSession(native=EchoNative()),
        )


def test_async_restore_options_are_attached_to_native_commands() -> None:
    async def run() -> None:
        native = EchoNative()
        browser = AsyncBrowser(
            native_session=AsyncNativeSession(
                native=native,
                session="async-loop",
                restore=RestoreOptions(key="async-loop", check_text="Dashboard"),
            ),
        )

        await browser.launch_process()
        await browser.aclose()

        command = native.commands[0]
        assert command["action"] == "launch"
        assert command["restoreKey"] == "async-loop"
        assert command["restoreCheckText"] == "Dashboard"

    asyncio.run(run())


def test_session_id_uses_canonical_cwd_and_sanitized_prefix() -> None:
    current = str(Path.cwd().resolve())
    expected_hash = hashlib.sha256(current.encode()).hexdigest()[:12]

    session_id = ab.session_id(
        scope="cwd",
        prefix="Next Dev Loop: /tmp!",
        path=Path.cwd(),
    )

    assert session_id == SessionId(
        session=f"next-dev-loop-tmp-{expected_hash}",
        scope="cwd",
        path=current,
        hash=expected_hash,
    )
    assert str(session_id) == session_id.session


def test_session_info_uses_native_session_command() -> None:
    native = ResponseNative({"session_info": {"session": "next-loop", "browserLaunched": False}})
    browser = Browser(native_session=NativeSession(native=native))

    assert browser.runtime.info()["session"] == "next-loop"
    assert native.commands[0]["action"] == "session_info"


def test_page_open_requires_url() -> None:
    browser = Browser(native_session=NativeSession(native=EchoNative()))

    with pytest.raises(TypeError):
        cast(Any, browser.page.open)()


def test_browser_connect_uses_constructor_cdp_options_without_navigation() -> None:
    browser = ab.configure(
        force=True,
        attach={"url": "ws://127.0.0.1:9222/devtools/browser/test"},
        native_session=NativeSession(native=CdpConnectNative()),
    )
    try:
        assert browser.connect() == {"launched": True}
        assert browser.tabs.list()[0].id == "t1"
    finally:
        ab.reset(force=True)


def test_browser_launch_classmethod_starts_with_named_options() -> None:
    native = EchoNative()

    browser = Browser.launch(
        {"headless": False, "hide_scrollbars": False},
        session={"allowed_domains": "example.com"},
        native_session=NativeSession(native=native),
    )

    assert browser.is_launched is True
    assert native.commands[0]["action"] == "launch"
    assert native.commands[0]["headless"] is False
    assert native.commands[0]["hideScrollbars"] is False
    assert native.commands[0]["allowedDomains"] == "example.com"


def test_browser_attach_classmethod_starts_cdp_target() -> None:
    browser = Browser.attach(
        {"port": 52980},
        launch={"hide_scrollbars": False},
        native_session=NativeSession(native=CdpPortConnectNative()),
    )

    assert browser.is_launched is True
    assert browser.tabs.list()[0].id == "t1"


def test_browser_from_session_names_lazy_session_controller() -> None:
    browser = Browser.from_session(
        "next-loop",
        restore=RestoreOptions(key="next-loop"),
        session={"allowed_domains": "example.com"},
    )

    assert isinstance(browser, Browser)
    assert browser.is_launched is False


def test_cdp_attach_requires_one_target() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        CDPAttach()
    with pytest.raises(ValueError, match="exactly one"):
        CDPAttach(url="ws://127.0.0.1:9222/devtools/browser/test", port=9222)


def test_native_execute_returns_failed_response_for_native_errors() -> None:
    browser = Browser(native_session=NativeSession(native=ErrorNative()))

    response = browser.native.execute("explode")

    assert response.success is False
    assert response.action == "explode"


def test_close_error_preserves_launched_state() -> None:
    browser = Browser(native_session=NativeSession(native=CloseErrorNative()))
    browser.launch_process()

    with pytest.raises(BrowserError) as error:
        browser.close()

    assert error.value.action == "close"
    assert browser.is_launched is True


def test_browser_context_manager_preserves_body_exception_when_close_fails() -> None:
    native = CloseErrorNative()

    with (
        pytest.raises(RuntimeError, match="body failed"),
        Browser(native_session=NativeSession(native=native)),
    ):
        raise RuntimeError("body failed")

    assert native.commands[-1]["action"] == "__agent_browser_internal_shutdown"


def test_browser_context_manager_surfaces_close_error_without_body_exception() -> None:
    native = CloseErrorNative()

    with (
        pytest.raises(BrowserError) as exc_info,
        Browser(native_session=NativeSession(native=native)),
    ):
        pass

    assert exc_info.value.action == "close"
    assert native.commands[-1]["action"] == "__agent_browser_internal_shutdown"


def test_default_session_keeps_handle_when_close_fails() -> None:
    native = CloseErrorNative()
    browser = ab.configure(native_session=NativeSession(native=native))
    browser.launch_process()

    with pytest.raises(BrowserError) as exc_info:
        ab.close()

    assert exc_info.value.action == "close"
    assert ab.default_browser() is browser
    assert browser.is_launched is True


def test_default_session_force_close_discards_stale_handle_when_close_fails() -> None:
    native = CloseErrorNative()
    browser = ab.configure(native_session=NativeSession(native=native))
    browser.launch_process()

    ab.close(force=True)

    assert ab.default_browser() is not browser
    assert native.commands[-1]["action"] == "__agent_browser_internal_shutdown"


def test_default_session_configure_rolls_back_when_old_browser_close_fails() -> None:
    native = CloseErrorNative()
    original = ab.configure(native_session=NativeSession(native=native))
    original.launch_process()

    with pytest.raises(BrowserError):
        ab.configure(native_session=NativeSession(native=EchoNative()))

    assert ab.default_browser() is original
    assert original.is_launched is True


def test_default_session_force_configure_recovers_from_stale_default_browser() -> None:
    native = CloseErrorNative()
    original = ab.configure(native_session=NativeSession(native=native))
    original.launch_process()

    replacement = ab.configure(force=True, native_session=NativeSession(native=EchoNative()))

    assert replacement is ab.default_browser()
    assert replacement is not original
    assert native.commands[-1]["action"] == "__agent_browser_internal_shutdown"


def test_default_session_force_reset_discards_stale_handle_after_close_failure() -> None:
    native = CloseErrorNative()
    browser = ab.configure(
        launch={"headless": False},
        native_session=NativeSession(native=native),
    )
    browser.launch_process()

    ab.reset(force=True)

    assert ab.default_browser() is not browser
    assert native.commands[-1]["action"] == "__agent_browser_internal_shutdown"


def test_default_session_configure_keeps_cdp_attachment_explicit() -> None:
    native = CdpPortConnectNative()

    try:
        browser = ab.configure(
            attach={"port": 52980},
            launch={"hide_scrollbars": False},
            native_session=NativeSession(native=native),
        )

        assert browser.is_launched is False
        assert native.connected is False
        browser.connect()
        assert browser.is_launched is True
        assert ab.tabs.list()[0].id == "t1"
    finally:
        ab.reset()


def test_confirm_helper_replays_pending_action() -> None:
    native = ConfirmationNative()
    browser = Browser(native_session=NativeSession(native=native))

    try:
        browser.find.role("button", name="Delete", exact=True).click()
    except ActionConfirmationRequired as confirmation:
        result = confirmation.pending_action.confirm()
    else:  # pragma: no cover
        raise AssertionError("confirmation was not required")

    assert result == {"clicked": "#danger"}


def test_deny_helper_returns_native_denial() -> None:
    native = ConfirmationNative()
    browser = Browser(native_session=NativeSession(native=native))

    try:
        browser.find.role("button", name="Delete", exact=True).click()
    except ActionConfirmationRequired as confirmation:
        denied = confirmation.pending_action.deny()

    assert denied == {"denied": True, "action": "click"}


def _first_launch_command(
    browser: Browser,
    native: EchoNative,
    options: Any = None,
) -> dict[str, Any]:
    browser.launch_process(options=options)
    return native.commands[0]


def test_start_serializes_configured_path_options() -> None:
    native = EchoNative()
    Browser.launch(
        {
            "profile": Path("profile"),
            "storage_state": Path("state.json"),
            "extensions": [Path("extension")],
        },
        native_session=NativeSession(native=native),
    )

    command = native.commands[0]

    assert command["profile"] == "profile"
    assert command["storageState"] == "state.json"
    assert command["extensions"] == ["extension"]


def test_start_serializes_named_connection_options() -> None:
    native = EchoNative()
    Browser.attach(
        {"url": "ws://127.0.0.1:9222/devtools/browser/test"},
        launch={
            "proxy": ProxyConfig(
                "http://proxy:8080",
                bypass="localhost",
                username="u",
                password="p",
            ),
            "provider": "browserbase",
        },
        native_session=NativeSession(native=native),
    )

    command = native.commands[0]

    assert command["proxy"] == {
        "server": "http://proxy:8080",
        "bypass": "localhost",
        "username": "u",
        "password": "p",
    }
    assert command["provider"] == "browserbase"
    assert command["cdpUrl"] == "ws://127.0.0.1:9222/devtools/browser/test"


def test_start_serializes_configured_display_options() -> None:
    native = EchoNative()
    Browser.launch(
        LaunchOptions(color_scheme="dark", hide_scrollbars=False),
        native_session=NativeSession(native=native),
    )

    command = native.commands[0]

    assert command["colorScheme"] == "dark"
    assert command["hideScrollbars"] is False


def test_start_serializes_configured_browser_args() -> None:
    native = EchoNative()
    Browser.launch(
        LaunchOptions(args=["--disable-gpu"]),
        native_session=NativeSession(native=native),
    )

    command = native.commands[0]

    assert command["args"] == ["--disable-gpu"]


def test_start_serializes_explicit_launch_mapping() -> None:
    native = EchoNative()
    browser = Browser(native_session=NativeSession(native=native))

    command = _first_launch_command(
        browser,
        native,
        {"download_path": Path("downloads")},
    )

    assert command["downloadPath"] == "downloads"


def test_dashboard_start_after_native_start_raises() -> None:
    browser = Browser(native_session=NativeSession(native=EchoNative()))

    browser.page.title()

    with pytest.raises(RuntimeError, match="dashboard must be started before"):
        browser.dashboard.start()


def test_launch_uses_configured_default_execution_options() -> None:
    native = EchoNative()
    Browser.launch(
        {"headless": False},
        native_session=NativeSession(native=native),
    )

    command = native.commands[0]

    assert command["headless"] is False


def test_launch_installs_browser_and_passes_resolved_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = EchoNative()
    browser = Browser(native_session=NativeSession(native=native))
    browser._auto_install = True
    result = InstallResult(
        executable_path=Path("/tmp/chrome-for-testing"),
        version="123",
        source="download",
        installed=True,
    )
    monkeypatch.setattr("agentbrowser.browser.ensure_installed", lambda: result)

    browser.launch_process()

    assert native.commands[0]["executablePath"] == "/tmp/chrome-for-testing"


def test_launch_skips_install_for_explicit_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = EchoNative()
    browser = Browser(native_session=NativeSession(native=native))
    browser._auto_install = True

    def fail_install() -> InstallResult:
        raise AssertionError("install should not run")

    monkeypatch.setattr("agentbrowser.browser.ensure_installed", fail_install)

    browser.launch_process(options={"executable_path": "/custom/chrome"})

    assert native.commands[0]["executablePath"] == "/custom/chrome"


def test_implicit_native_launch_prepares_install_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = EchoNative()
    browser = Browser(native_session=NativeSession(native=native))
    browser._auto_install = True
    calls = []

    def install() -> InstallResult:
        calls.append("install")
        return InstallResult(
            executable_path=Path("/tmp/chrome-for-testing"),
            version="123",
            source="cache",
            installed=False,
        )

    monkeypatch.setattr("agentbrowser.browser.ensure_installed", install)

    browser._command("screenshot")
    browser._command("title")

    assert calls == ["install"]
    assert [command["action"] for command in native.commands] == ["screenshot", "title"]


def test_launch_skips_install_for_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = EchoNative()
    browser = Browser(native_session=NativeSession(native=native))
    browser._auto_install = True

    def fail_install() -> InstallResult:
        raise AssertionError("install should not run")

    monkeypatch.setattr("agentbrowser.browser.ensure_installed", fail_install)

    browser.launch_process(options={"provider": "browserbase"})

    assert native.commands[0]["provider"] == "browserbase"
    assert "executablePath" not in native.commands[0]


def test_launch_uses_configured_default_allowlist() -> None:
    native = EchoNative()
    browser = Browser(
        native_session=NativeSession(native=native),
        session=BrowserSessionOptions(allowed_domains="*.example.com"),
    )

    command = _first_launch_command(browser, native)

    assert command["allowedDomains"] == "*.example.com"


def test_launch_uses_configured_default_display_options() -> None:
    native = EchoNative()
    Browser.launch(
        LaunchOptions(color_scheme="dark", hide_scrollbars=False),
        native_session=NativeSession(native=native),
    )

    command = native.commands[0]

    assert command["colorScheme"] == "dark"
    assert command["hideScrollbars"] is False


def test_launch_call_options_override_configured_defaults() -> None:
    native = EchoNative()
    browser = ab.configure(
        force=True,
        launch={"headless": False, "hide_scrollbars": False},
        native_session=NativeSession(native=native),
    )

    try:
        command = _first_launch_command(
            browser,
            native,
            {"headless": True, "hide_scrollbars": True},
        )
    finally:
        ab.reset(force=True)

    assert command["headless"] is True
    assert command["hideScrollbars"] is True


def test_allowed_domains_allow_raw_navigation_inside_allowlist() -> None:
    native = EchoNative()
    browser = Browser(native_session=NativeSession(native=native, allowed_domains="*.example.com"))

    browser.native.data("tab_new", url="https://docs.example.com")

    assert native.commands[0]["action"] == "tab_new"


def test_allowed_domains_block_raw_navigation_outside_allowlist() -> None:
    native = EchoNative()
    browser = Browser(native_session=NativeSession(native=native, allowed_domains="*.example.com"))

    with pytest.raises(BrowserError, match="allowed domains") as tab_error:
        browser.native.data("tab_new", url="https://evil.example")

    assert tab_error.value.code == "allowed_domains"
    assert native.commands == []


def test_allowed_domains_allow_cookie_domain_inside_allowlist() -> None:
    native = EchoNative()
    browser = Browser(native_session=NativeSession(native=native, allowed_domains="*.example.com"))

    browser.cookies.set("session", "abc", domain=".example.com")

    assert native.commands[0]["action"] == "cookies_set"


def test_allowed_domains_block_cookie_domain_outside_allowlist() -> None:
    native = EchoNative()
    browser = Browser(native_session=NativeSession(native=native, allowed_domains="*.example.com"))

    with pytest.raises(BrowserError, match="Cookie domain") as cookie_error:
        browser.cookies.set("session", "abc", domain="evil.example")

    assert cookie_error.value.code == "allowed_domains"
    assert native.commands == []


def test_allowed_domains_require_cookie_domain_for_validation() -> None:
    native = EchoNative()
    browser = Browser(native_session=NativeSession(native=native, allowed_domains="*.example.com"))

    with pytest.raises(BrowserError, match="cannot be validated"):
        browser.cookies.set("session", "abc")

    assert native.commands == []


def test_allowed_domains_filter_cookie_reads() -> None:
    browser = Browser(
        native_session=NativeSession(native=CookieNative(), allowed_domains="example.com")
    )

    scoped = browser.cookies.get()

    assert [cookie.name for cookie in scoped] == ["kept"]


def test_allowed_domains_unsafe_export_all_returns_unscoped_cookies() -> None:
    native = CookieNative()
    browser = Browser(native_session=NativeSession(native=native, allowed_domains="example.com"))

    exported = browser.cookies.get(unsafe_export_all=True)

    assert {cookie.name for cookie in exported} == {"kept", "dropped", "missing-domain"}
    assert native.commands[0]["unsafeExportAll"] is True


def test_allowed_domains_block_unscoped_cookie_clear() -> None:
    native = CookieNative()
    browser = Browser(native_session=NativeSession(native=native, allowed_domains="example.com"))

    with pytest.raises(BrowserError, match="unsafe_clear_all") as clear_error:
        browser.cookies.clear()

    assert clear_error.value.code == "allowed_domains"
    assert native.commands == []


def test_allowed_domains_unsafe_clear_all_reaches_native() -> None:
    native = CookieNative()
    browser = Browser(native_session=NativeSession(native=native, allowed_domains="example.com"))

    cleared = browser.cookies.clear(unsafe_clear_all=True)

    assert cleared == {"cleared": True}
    assert native.commands[0]["action"] == "cookies_clear"
    assert native.commands[0]["unsafeClearAll"] is True


def test_allowed_domains_filter_confirmed_cookie_reads() -> None:
    browser = Browser(
        native_session=NativeSession(native=ConfirmedCookieNative(), allowed_domains="example.com")
    )

    with pytest.raises(ActionConfirmationRequired) as confirmation:
        browser.cookies.get()
    data = confirmation.value.pending_action.confirm()

    assert [cookie["name"] for cookie in data["cookies"]] == ["kept"]


def test_allowed_domains_preserve_confirmed_unsafe_cookie_export() -> None:
    native = ConfirmedCookieNative()
    browser = Browser(native_session=NativeSession(native=native, allowed_domains="example.com"))

    with pytest.raises(ActionConfirmationRequired) as confirmation:
        browser.cookies.get(unsafe_export_all=True)
    data = confirmation.value.pending_action.confirm()

    assert {cookie["name"] for cookie in data["cookies"]} == {"kept", "dropped"}
    assert native.commands[0]["unsafeExportAll"] is True


def test_allowed_domains_applies_to_supplied_native_session() -> None:
    native = EchoNative()
    browser = Browser(
        session=BrowserSessionOptions(allowed_domains="example.com"),
        native_session=NativeSession(native=native),
    )

    with pytest.raises(BrowserError, match="allowed domains") as denied:
        browser.native.data("tab_new", url="https://evil.example")
    browser.native.data("tab_new", url="https://example.com")

    assert denied.value.code == "allowed_domains"
    assert [command["url"] for command in native.commands] == ["https://example.com"]


def test_allowed_domains_raw_command_cannot_weaken_session_policy() -> None:
    native = EchoNative()
    browser = Browser(native_session=NativeSession(native=native, allowed_domains="example.com"))

    browser.native.data("device_list", allowedDomains="evil.example")
    with pytest.raises(BrowserError, match="allowed domains") as denied:
        browser.native.data("tab_new", url="https://evil.example")

    assert denied.value.code == "allowed_domains"
    assert [command["action"] for command in native.commands] == ["device_list"]


@pytest.mark.parametrize(
    ("action", "params"),
    [
        (
            "auth_save",
            {
                "name": "login",
                "url": "https://evil.example/login",
                "username": "u",
                "password": "p",
            },
        ),
        ("diff_url", {"url1": "https://evil.example/a", "url2": "https://example.com/b"}),
        ("frame", {"url": "https://evil.example/frame"}),
        ("pushstate", {"url": "https://evil.example/state"}),
        ("read", {"url": "https://evil.example/docs"}),
        ("recording_start", {"path": "recording.json", "url": "https://evil.example"}),
        ("responsebody", {"url": "https://evil.example/api"}),
        ("vitals", {"url": "https://evil.example/vitals"}),
        ("wait", {"url": "https://evil.example/ready"}),
    ],
)
def test_allowed_domains_guard_raw_url_target_actions(
    action: str,
    params: Mapping[str, Any],
) -> None:
    native = EchoNative()
    browser = Browser(native_session=NativeSession(native=native, allowed_domains="example.com"))

    with pytest.raises(BrowserError, match="allowed domains") as denied:
        browser.native.data(action, **params)

    assert denied.value.code == "allowed_domains"
    assert native.commands == []


@pytest.mark.parametrize(
    ("action", "pattern"),
    [
        ("route", "*evil.example/secret"),
        ("route", "*://evil.example/secret"),
        ("route", "*.evil.example/*"),
        ("route", "//evil.example/path"),
        ("route", "//sub.example.com/path"),
        ("route", "*//evil.example/*"),
        ("waitforurl", "*evil.example/secret"),
        ("waitforurl", "*://evil.example/secret"),
        ("waitforurl", "*.evil.example/*"),
        ("waitforurl", "//evil.example/path"),
        ("waitforurl", "//sub.example.com/path"),
        ("waitforurl", "*//evil.example/*"),
        ("unroute", "*//evil.example/*"),
        ("frame", "//evil.example/path"),
        ("responsebody", "//evil.example/path"),
    ],
)
def test_allowed_domains_guard_host_qualified_patterns(
    action: str,
    pattern: str,
) -> None:
    native = EchoNative()
    browser = Browser(native_session=NativeSession(native=native, allowed_domains="example.com"))

    with pytest.raises(BrowserError, match="allowed domains") as denied:
        browser.native.data(action, url=pattern)

    assert denied.value.code == "allowed_domains"
    assert native.commands == []


@pytest.mark.parametrize(
    "pattern",
    [
        "/api/*",
        "**/api",
        "*api/message",
    ],
)
def test_allowed_domains_allow_relative_wildcard_patterns(pattern: str) -> None:
    native = EchoNative()
    browser = Browser(native_session=NativeSession(native=native, allowed_domains="example.com"))

    browser.native.data("route", url=pattern)

    assert native.commands[0]["url"] == pattern


@pytest.mark.parametrize(
    "pattern",
    [
        "localhost",
        "localhost/path",
        "*localhost",
        "*localhost/path",
        "*localhost*",
        "[::1]/path",
        "assets/*.js",
    ],
)
def test_allowed_domains_guard_single_label_and_ipv6_pattern_hosts(pattern: str) -> None:
    native = EchoNative()
    browser = Browser(native_session=NativeSession(native=native, allowed_domains="example.com"))

    with pytest.raises(BrowserError, match="allowed domains") as denied:
        browser.native.data("route", url=pattern)

    assert denied.value.code == "allowed_domains"
    assert native.commands == []


@pytest.mark.parametrize(
    "action",
    ["route", "wait", "waitforurl", "unroute", "frame", "responsebody"],
)
@pytest.mark.parametrize(
    "pattern",
    [
        "*/evil.example/*",
        "**/evil.example/*",
        "*/localhost/*",
        "**/[::1]/*",
    ],
)
def test_allowed_domains_guard_wildcard_slash_host_patterns(
    action: str,
    pattern: str,
) -> None:
    native = EchoNative()
    browser = Browser(native_session=NativeSession(native=native, allowed_domains="example.com"))

    with pytest.raises(BrowserError, match="allowed domains") as denied:
        browser.native.data(action, url=pattern)

    assert denied.value.code == "allowed_domains"
    assert native.commands == []


@pytest.mark.parametrize(
    ("pattern", "allowed_domains"),
    [
        ("localhost", "localhost"),
        ("localhost/path", "localhost"),
        ("*://localhost/path", "localhost"),
        ("//localhost/path", "localhost"),
        ("[::1]/path", "::1"),
    ],
)
def test_allowed_domains_allow_single_label_and_ipv6_pattern_hosts(
    pattern: str,
    allowed_domains: str,
) -> None:
    native = EchoNative()
    browser = Browser(native_session=NativeSession(native=native, allowed_domains=allowed_domains))

    browser.native.data("route", url=pattern)

    assert native.commands[0]["url"] == pattern


@pytest.mark.parametrize(
    "pattern",
    [
        "*localhost",
        "*localhost/path",
        "*localhost:3000/path",
        "*localhost*",
    ],
)
def test_allowed_domains_reject_unanchored_wildcard_localhost_pattern_hosts(
    pattern: str,
) -> None:
    native = EchoNative()
    browser = Browser(native_session=NativeSession(native=native, allowed_domains="localhost"))

    with pytest.raises(BrowserError, match="allowed domains") as denied:
        browser.native.data("route", url=pattern)

    assert denied.value.code == "allowed_domains"
    assert native.commands == []


@pytest.mark.parametrize(
    "pattern",
    [
        "example.com/*",
        "*://example.com/*",
        "//example.com/path",
    ],
)
def test_allowed_domains_allow_exact_host_patterns_inside_allowlist(pattern: str) -> None:
    native = EchoNative()
    browser = Browser(native_session=NativeSession(native=native, allowed_domains="example.com"))

    browser.native.data("route", url=pattern)

    assert native.commands[0]["url"] == pattern


@pytest.mark.parametrize(
    "pattern",
    [
        "*.example.com/*",
        "https://*.example.com/*",
    ],
)
def test_allowed_domains_exact_host_denies_wildcard_host_patterns(pattern: str) -> None:
    native = EchoNative()
    browser = Browser(native_session=NativeSession(native=native, allowed_domains="example.com"))

    with pytest.raises(BrowserError, match="allowed domains") as denied:
        browser.native.data("route", url=pattern)

    assert denied.value.code == "allowed_domains"
    assert native.commands == []


@pytest.mark.parametrize(
    "pattern",
    [
        "*.example.com/*",
        "https://*.example.com/*",
        "*.api.example.com/*",
        "//sub.example.com/path",
    ],
)
def test_allowed_domains_allow_wildcard_host_patterns_inside_wildcard_allowlist(
    pattern: str,
) -> None:
    native = EchoNative()
    browser = Browser(native_session=NativeSession(native=native, allowed_domains="*.example.com"))

    browser.native.data("route", url=pattern)

    assert native.commands[0]["url"] == pattern


def test_allowed_domains_filters_storage_state_before_load(tmp_path: Path) -> None:
    mixed_state = _mixed_storage_state()
    load_path = tmp_path / "mixed-state.json"
    load_path.write_text(json.dumps(mixed_state))
    native = StorageStateNative(mixed_state)
    browser = Browser(native_session=NativeSession(native=native, allowed_domains="example.com"))

    browser.state.load(load_path)

    assert native.loaded_state is not None
    assert [cookie["name"] for cookie in native.loaded_state["cookies"]] == ["kept"]
    assert [origin["origin"] for origin in native.loaded_state["origins"]] == [
        "https://example.com"
    ]
    assert json.loads(load_path.read_text()) == mixed_state


def test_allowed_domains_filters_saved_storage_state(tmp_path: Path) -> None:
    native = StorageStateNative(_mixed_storage_state())
    browser = Browser(native_session=NativeSession(native=native, allowed_domains="example.com"))
    save_path = tmp_path / "saved-state.json"

    browser.state.save(save_path)

    saved_state = json.loads(save_path.read_text())
    assert [cookie["name"] for cookie in saved_state["cookies"]] == ["kept"]
    assert [origin["origin"] for origin in saved_state["origins"]] == ["https://example.com"]


def test_async_allowed_domains_applies_to_supplied_native_session() -> None:
    native = EchoNative()

    async def run() -> None:
        browser = AsyncBrowser(
            session=BrowserSessionOptions(allowed_domains="example.com"),
            native_session=AsyncNativeSession(native=native),
        )

        with pytest.raises(BrowserError, match="allowed domains") as denied:
            await browser.native.data("tab_new", url="https://evil.example")
        await browser.native.data("tab_new", url="https://example.com")
        await browser.aclose()

        assert denied.value.code == "allowed_domains"

    asyncio.run(run())
    assert [command["url"] for command in native.commands if command["action"] == "tab_new"] == [
        "https://example.com"
    ]


def test_async_allowed_domains_filter_confirmed_cookie_reads() -> None:
    native = ConfirmedCookieNative()

    async def run() -> Mapping[str, Any]:
        browser = AsyncBrowser(
            native_session=AsyncNativeSession(native=native, allowed_domains="example.com")
        )
        try:
            with pytest.raises(ActionConfirmationRequired) as confirmation:
                await browser.cookies.get()
            return await confirmation.value.pending_action.confirm()
        finally:
            await browser.aclose()

    data = asyncio.run(run())

    assert [cookie["name"] for cookie in data["cookies"]] == ["kept"]


def test_cookie_get_returns_typed_cookie() -> None:
    native = ResponseNative(
        {
            "cookies_get": {"cookies": [{"name": "session", "value": "abc"}]},
        }
    )
    browser = Browser(native_session=NativeSession(native=native))

    cookie = browser.cookies.get(["https://example.com"])[0]

    assert isinstance(cookie, Cookie)
    assert cookie.name == "session"
    assert cookie.value == "abc"


def test_cookie_set_serializes_http_only_option() -> None:
    native = ResponseNative()
    browser = Browser(native_session=NativeSession(native=native))

    browser.cookies.set("session", "abc", url="https://example.com", http_only=True)

    assert native.commands[0]["action"] == "cookies_set"
    assert native.commands[0]["httpOnly"] is True


def test_storage_get_returns_value() -> None:
    native = ResponseNative({"storage_get": {"value": "dark"}})
    browser = Browser(native_session=NativeSession(native=native))

    assert browser.storage.get("theme") == "dark"


def test_storage_set_serializes_area_option() -> None:
    native = ResponseNative()
    browser = Browser(native_session=NativeSession(native=native))

    browser.storage.set("theme", "dark", area="session")

    assert native.commands[0]["action"] == "storage_set"
    assert native.commands[0]["type"] == "session"


def test_state_show_returns_native_state_path() -> None:
    native = ResponseNative({"state_show": {"path": "session.json"}})
    browser = Browser(native_session=NativeSession(native=native))

    assert browser.state.show(Path("session.json")) == {"path": "session.json"}


def test_network_requests_return_typed_models() -> None:
    native = ResponseNative(
        {
            "requests": {"requests": [{"requestId": "r1", "url": "https://example.com/api"}]},
        }
    )
    browser = Browser(native_session=NativeSession(native=native))

    request = browser.network.requests(method="POST", status="2xx")[0]

    assert isinstance(request, NetworkRequest)
    assert request.id == "r1"


def test_network_requests_raise_parse_error_for_missing_required_fields() -> None:
    browser = Browser(
        native_session=NativeSession(
            native=ResponseNative({"requests": {"requests": [{"url": "/"}]}})
        )
    )

    with pytest.raises(NativeParseError, match="NetworkRequest"):
        browser.network.requests()


def test_network_request_detail_returns_typed_model() -> None:
    native = ResponseNative(
        {
            "request_detail": {
                "requestId": "r1",
                "url": "https://example.com/api",
                "method": "GET",
                "status": 200,
            },
        }
    )
    browser = Browser(native_session=NativeSession(native=native))

    detail = browser.network.request_detail("r1")

    assert isinstance(detail, RequestDetail)
    assert detail.status == 200


def test_tabs_list_raises_parse_error_for_missing_required_fields() -> None:
    browser = Browser(
        native_session=NativeSession(native=ResponseNative({"tab_list": {"tabs": [{"id": "t1"}]}}))
    )

    with pytest.raises(NativeParseError, match="TabInfo"):
        browser.tabs.list()


def test_bounding_box_raises_parse_error_for_partial_native_box() -> None:
    browser = Browser(
        native_session=NativeSession(native=ResponseNative({"boundingbox": {"x": 1}}))
    )

    with pytest.raises(NativeParseError, match="BoundingBox"):
        browser.find.css("#box").bounding_box()


def test_network_route_serializes_route_response() -> None:
    native = ResponseNative()
    browser = Browser(native_session=NativeSession(native=native))

    browser.network.route("**/api", response=RouteResponse(status=201, body="{}"))

    assert native.commands[0]["action"] == "route"
    assert native.commands[0]["response"]["status"] == 201


def test_keyboard_insert_text_serializes_native_keyboard_action() -> None:
    native = ResponseNative()
    browser = Browser(native_session=NativeSession(native=native))

    browser.keyboard.insert_text("hello")

    assert native.commands[0]["action"] == "keyboard"
    assert native.commands[0]["subaction"] == "insertText"


def test_mouse_wheel_serializes_native_coordinates() -> None:
    native = ResponseNative()
    browser = Browser(native_session=NativeSession(native=native))

    browser.mouse.wheel(250, x=10, y=20)

    assert native.commands[0]["action"] == "wheel"
    assert native.commands[0]["deltaY"] == 250
    assert native.commands[0]["x"] == 10


@pytest.mark.parametrize(
    ("method_name", "text"),
    [
        ("placeholder", "Email"),
        ("alt_text", "Logo"),
        ("title", "Help"),
    ],
)
def test_find_semantic_helper_returns_native_text_result(method_name: str, text: str) -> None:
    native = SemanticLocatorNative()
    finder = Browser(native_session=NativeSession(native=native)).find

    assert getattr(finder, method_name)(text, exact=True).text() == text


def test_tabs_list_returns_typed_models_through_browser_namespace() -> None:
    native = ResponseNative(
        {
            "tab_list": {
                "tabs": [
                    {
                        "id": "t1",
                        "url": "https://example.com",
                        "title": "Example",
                        "label": "main",
                        "active": True,
                    }
                ]
            },
        }
    )
    browser = Browser(native_session=NativeSession(native=native))

    tab = browser.tabs.list()[0]

    assert isinstance(tab, TabInfo)
    assert tab.id == "t1"
    assert tab.label == "main"


def test_tabs_new_returns_typed_model_through_browser_namespace() -> None:
    native = ResponseNative({"tab_new": {"tab": {"id": "t2", "url": "https://example.com/docs"}}})
    browser = Browser(native_session=NativeSession(native=native))

    new_tab = browser.tabs.new("https://example.com/docs")

    assert isinstance(new_tab, TabInfo)
    assert new_tab.id == "t2"


def test_tabs_switch_requires_one_named_selector() -> None:
    browser = Browser(native_session=NativeSession(native=EchoNative()))

    with pytest.raises(ValueError, match="one of id, label, or index"):
        browser.tabs.switch()
    with pytest.raises(ValueError, match="exactly one"):
        browser.tabs.switch(id="t1", label="main")
    with pytest.raises(ValueError, match="non-negative"):
        browser.tabs.switch(index=-1)


def test_tabs_close_accepts_named_selector_or_active_tab() -> None:
    native = ResponseNative(
        {
            "tab_list": {
                "tabs": [{"id": "t-docs", "url": "https://example.com/docs", "label": "docs"}]
            },
            "tab_close": {},
        }
    )
    browser = Browser(native_session=NativeSession(native=native))

    browser.tabs.close(label="docs")
    browser.tabs.close()

    assert native.commands[1]["tabId"] == "t-docs"
    assert "tabId" not in native.commands[2]


def test_diagnostics_console_returns_typed_models_through_browser_namespace() -> None:
    native = ResponseNative(
        {
            "console": {
                "messages": [
                    {"type": "log", "text": "ready", "url": "https://example.com", "line": 7}
                ]
            },
        }
    )
    browser = Browser(native_session=NativeSession(native=native))

    message = browser.diagnostics.console()[0]

    assert isinstance(message, ConsoleMessage)
    assert message.text == "ready"


def test_bounding_box_returns_typed_model_through_browser_locator() -> None:
    native = ResponseNative({"boundingbox": {"x": 1, "y": 2, "width": 30, "height": 12}})
    browser = Browser(native_session=NativeSession(native=native))

    box = browser.find.css("#box").bounding_box()

    assert isinstance(box, BoundingBox)
    assert box.width == 30


def test_page_ready_rejects_negative_min_text_length() -> None:
    native = EchoNative()
    browser = Browser(native_session=NativeSession(native=native))

    with pytest.raises(ValueError, match="min_text_length"):
        browser.page.ready(min_text_length=-1)

    assert native.commands == []


def test_xpath_locator_serializes_native_xpath_selector() -> None:
    native = ResponseNative(
        {
            "getattribute": {"value": "https://example.com/story"},
            "count": {"count": 1},
        }
    )
    browser = Browser(native_session=NativeSession(native=native))

    link = browser.find.xpath("//a[normalize-space()='Read the full story']")
    href = link.attribute("href")
    count = link.count()

    assert href == "https://example.com/story"
    assert count == 1
    assert native.commands[0]["selector"] == "xpath=//a[normalize-space()='Read the full story']"
    assert native.commands[0]["attribute"] == "href"
    assert native.commands[1]["selector"] == "xpath=//a[normalize-space()='Read the full story']"


def test_xpath_locator_normalizes_native_prefix() -> None:
    native = ResponseNative({"count": {"count": 2}})
    browser = Browser(native_session=NativeSession(native=native))

    assert browser.find.xpath("xpath=//button").count() == 2
    assert native.commands[0]["selector"] == "xpath=//button"


def test_xpath_locator_rejects_empty_expression() -> None:
    browser = Browser(native_session=NativeSession(native=ResponseNative()))

    with pytest.raises(ValueError, match="XPath expression"):
        browser.find.xpath(" ")


def test_tabs_open_reuses_labelled_tabs_before_navigation() -> None:
    native = TabReuseNative()
    browser = Browser(native_session=NativeSession(native=native))

    tab = browser.tabs.open("example.com/docs", label="docs", wait_until="domcontentloaded")

    assert tab.id == "t1"
    assert tab.label == "docs"
    assert tab.url == "https://example.com/docs"
    assert tab.active is True


def test_har_stop_requires_native_path() -> None:
    browser = Browser(native_session=NativeSession(native=ResponseNative({"har_stop": {}})))

    with pytest.raises(BrowserError, match="path"):
        browser.network.har_stop()


def test_sdk_errors_share_common_base() -> None:
    assert issubclass(BrowserError, AgentBrowserError)
    assert issubclass(BrowserInstallError, AgentBrowserError)
    assert issubclass(ActionConfirmationRequired, AgentBrowserError)
    assert issubclass(StaleAgentRefError, AgentBrowserError)


def test_page_title_and_url_return_page_values() -> None:
    native = ResponseNative({"title": {"title": "Example"}, "url": {"url": "https://example.com"}})
    browser = Browser(native_session=NativeSession(native=native))

    assert browser.page.title() == "Example"
    assert browser.page.url() == "https://example.com"


def test_page_read_returns_typed_result_and_command_payload() -> None:
    native = ResponseNative(
        {
            "read": {
                "url": "https://example.com/docs",
                "finalUrl": "https://example.com/docs/index.md",
                "status": 200,
                "contentType": "text/markdown",
                "source": "path-markdown",
                "truncated": False,
                "content": "# Docs\n",
            }
        }
    )
    browser = Browser(native_session=NativeSession(native=native))

    result = browser.page.read(
        "example.com/docs",
        mode=ReadMode.llms_index(require_markdown=True),
        filter="auth",
        timeout_ms=2500,
        headers={"X-Agent": "pyagentbrowser"},
        allowed_domains=["example.com"],
    )

    assert isinstance(result, ReadResult)
    assert result.final_url == "https://example.com/docs/index.md"
    assert result.content == "# Docs\n"
    assert native.commands == [
        {
            "id": "py1",
            "action": "read",
            "url": "https://example.com/docs",
            "raw": False,
            "requireMd": True,
            "llms": "index",
            "outline": False,
            "filter": "auth",
            "timeout": 2500,
            "headers": {"X-Agent": "pyagentbrowser"},
            "allowedDomains": ["example.com"],
        }
    ]


def test_page_read_without_url_launches_before_reading_active_page() -> None:
    native = ResponseNative(
        {
            "launch": {"launched": True},
            "read": {
                "url": "https://example.com/app",
                "finalUrl": "https://example.com/app",
                "status": 200,
                "contentType": "text/html",
                "source": "active-tab-html-outline",
                "truncated": False,
                "content": "# Outline\n",
            },
        }
    )
    browser = Browser(native_session=NativeSession(native=native))

    result = browser.page.read(mode=ReadMode.outline_only())

    assert result.source == "active-tab-html-outline"
    assert [command["action"] for command in native.commands] == ["launch", "read"]
    assert "url" not in native.commands[1]
    assert native.commands[1]["outline"] is True


def test_page_read_rejects_conflicting_or_invalid_options() -> None:
    browser = Browser(native_session=NativeSession(native=EchoNative()))
    invalid_llms = cast(Any, "toc")

    with pytest.raises(ValueError, match="llms"):
        browser.page.read("example.com", mode=ReadMode(llms=invalid_llms))
    with pytest.raises(ValueError, match="llms"):
        browser.page.read("example.com", mode=ReadMode(llms="full", outline=True))
    with pytest.raises(ValueError, match=r"ReadMode\.html"):
        browser.page.read("example.com", mode=ReadMode(raw=True, require_markdown=True))
    with pytest.raises(ValueError, match=r"ReadMode\.html"):
        browser.page.read("example.com", mode=ReadMode(raw=True, llms="index"))
    with pytest.raises(ValueError, match=r"ReadMode\.outline_only"):
        browser.page.read("example.com", mode=ReadMode(require_markdown=True, outline=True))
    with pytest.raises(ValueError, match="timeout_ms"):
        browser.page.read("example.com", timeout_ms=0)

    assert browser.is_launched is False


def test_screenshot_result_reads_file_bytes_and_mime_bundle(tmp_path: Path) -> None:
    from PIL import Image

    path = tmp_path / "page.png"
    Image.new("RGB", (3, 2), (255, 0, 0)).save(path)
    native = ScreenshotNative(path)
    browser = Browser(native_session=NativeSession(native=native))

    result = browser.capture.screenshot(format="png")

    assert isinstance(result, Screenshot)
    assert result.path == path
    assert result.bytes() == path.read_bytes()
    assert result._repr_png_() == path.read_bytes()
    mime_data, mime_metadata = result._repr_mimebundle_()
    assert mime_data == {"image/png": path.read_bytes()}
    assert mime_metadata == {}


def test_screenshot_result_loads_image(tmp_path: Path) -> None:
    from PIL import Image

    path = tmp_path / "page.png"
    Image.new("RGB", (3, 2), (255, 0, 0)).save(path)
    browser = Browser(native_session=NativeSession(native=ScreenshotNative(path)))

    result = browser.capture.screenshot(format="png")

    assert result.pil(mode="L").mode == "L"
    assert result.image.size == (3, 2)


def test_screenshot_result_saves_copy(tmp_path: Path) -> None:
    path = tmp_path / "page.png"
    saved_path = tmp_path / "saved" / "copy.png"
    path.write_bytes(b"fake png bytes")
    browser = Browser(native_session=NativeSession(native=ScreenshotNative(path)))

    result = browser.capture.screenshot(format="png")
    saved = result.save(saved_path)

    assert saved.path == saved_path
    assert saved.bytes() == result.bytes()


def test_screenshot_result_exposes_parsed_annotations(
    tmp_path: Path,
) -> None:
    path = tmp_path / "page.png"
    path.write_bytes(b"fake png bytes")
    browser = Browser(native_session=NativeSession(native=ScreenshotNative(path)))

    result = browser.capture.screenshot(format="png", annotate=True)

    assert result.annotations[0].ref == "e1"


def test_screenshot_capture_serializes_annotate_option(
    tmp_path: Path,
) -> None:
    path = tmp_path / "page.png"
    path.write_bytes(b"fake png bytes")
    native = ScreenshotNative(path)
    browser = Browser(native_session=NativeSession(native=native))

    browser.capture.screenshot(format="png", annotate=True)

    assert native.commands[0]["action"] == "screenshot"
    assert native.commands[0]["annotate"] is True


def test_screenshot_marimo_helper_is_optional_and_notebook_friendly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shot = Screenshot(tmp_path / "page.png", "png", (), {})
    calls: list[dict[str, Any]] = []

    def image(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {"kind": "marimo-image", **kwargs}

    monkeypatch.setitem(sys.modules, "marimo", types.SimpleNamespace(image=image))

    view = shot.marimo(width="50%", rounded=True, caption="Viewport")

    assert view["kind"] == "marimo-image"
    assert len(calls) == 1
    assert calls[0]["src"] == str(tmp_path / "page.png")
    assert calls[0]["width"] == "50%"
    assert calls[0]["rounded"] is True
    assert calls[0]["caption"] == "Viewport"


def test_screenshot_marimo_helper_reports_missing_optional_dependency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shot = Screenshot(tmp_path / "page.png", "png", (), {})
    monkeypatch.setitem(sys.modules, "marimo", None)

    with pytest.raises(ImportError, match=r"Screenshot\.marimo"):
        shot.marimo()


def test_screenshot_wait_ms_zero_still_captures(tmp_path: Path) -> None:
    path = tmp_path / "page.png"
    path.write_bytes(b"fake png bytes")
    native = ScreenshotNative(path)
    browser = Browser(native_session=NativeSession(native=native))

    result = browser.capture.screenshot(wait_ms=0)

    assert result.path == path


def test_screenshot_wait_ms_rejects_negative_values(tmp_path: Path) -> None:
    native = ScreenshotNative(tmp_path / "page.png")
    browser = Browser(native_session=NativeSession(native=native))

    with pytest.raises(ValueError, match="wait_ms"):
        browser.capture.screenshot(wait_ms=-1)

    assert native.commands == []


def test_package_root_default_browser_session_uses_configured_browser() -> None:
    native = EchoNative()
    browser = ab.configure(
        native_session=NativeSession(native=native),
        launch={"headless": False},
        session={"allowed_domains": "*.example.com"},
    )

    try:
        assert browser is ab.default_browser()
        assert ab.page.title() == ""
    finally:
        ab.reset()


def test_package_root_capture_namespace_returns_screenshot_view(tmp_path: Path) -> None:
    path = tmp_path / "page.png"
    path.write_bytes(b"fake png bytes")
    ab.configure(native_session=NativeSession(native=ScreenshotNative(path)))

    try:
        shot = ab.capture.screenshot()
        assert isinstance(shot, Screenshot)
        assert shot.path == path
    finally:
        ab.reset()


def _configure_package_root_cdp(monkeypatch: pytest.MonkeyPatch) -> None:
    cdp_controller = importlib.import_module("agentbrowser.cdp.controller")
    monkeypatch.setattr(cdp_controller, "CDPClient", _PublicCDPClient)
    ab.configure(native_session=NativeSession(native=_CDPNative()))


def test_default_cdp_frames_list_returns_frame_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_package_root_cdp(monkeypatch)

    try:
        frames = {frame.id: frame for frame in ab.cdp.frames.list()}
        assert frames["main"].url == "https://example.com"
        assert frames["child"].name == "target"
    finally:
        ab.reset()


def test_default_cdp_frames_get_by_url_returns_matching_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_package_root_cdp(monkeypatch)

    try:
        assert ab.cdp.frames.get(url="https://example.com/one/frame").id == "child"
    finally:
        ab.reset()


def test_package_root_cdp_evaluate_uses_frame_selector(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_package_root_cdp(monkeypatch)

    try:
        assert ab.cdp.evaluate("document.title", frame="#target-frame").endswith("-child")
    finally:
        ab.reset()


def test_default_cdp_frames_lookup_by_selector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_package_root_cdp(monkeypatch)

    try:
        assert ab.cdp.frames.get(selector="#target-frame").id == "child"
    finally:
        ab.reset()


def test_default_cdp_frames_lookup_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_package_root_cdp(monkeypatch)

    try:
        assert ab.cdp.frames.get(name="target").id == "child"
    finally:
        ab.reset()


def test_default_active_frame_select_returns_selected_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_package_root_cdp(monkeypatch)

    try:
        assert ab.active_frame.select(selector="#target-frame")["frame"] == ("#target-frame")
    finally:
        ab.reset()


def test_default_active_frame_main_restores_main_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_package_root_cdp(monkeypatch)

    try:
        assert ab.active_frame.main()["frame"] == "main"
    finally:
        ab.reset()


def test_package_root_exports_supported_public_names() -> None:
    exported = set(ab.__all__)
    assert exported >= _ROOT_EXPORT_CONTRACT
    assert CDPClosedError is ab.CDPClosedError
    assert ConfirmationTarget is ab.ConfirmationTarget
    for name in ab.__all__:
        assert hasattr(ab, name), name
        assert not name.startswith("_") or name in {
            "__agent_browser_commit__",
            "__agent_browser_version__",
            "__upstream_commit__",
            "__upstream_version__",
            "__version__",
        }


def test_package_versions_expose_upstream_alias() -> None:
    assert ab.__version__
    assert ab.__agent_browser_version__ == ab.__upstream_version__
    assert ab.__agent_browser_commit__ == ab.__upstream_commit__


def test_package_root_exposes_default_browser_controls() -> None:
    default_root_names = _DEFAULT_NAMESPACE_NAMES | {
        "close",
        "configure",
        "default_browser",
        "reset",
    }

    assert default_root_names <= set(ab.__all__)
    assert callable(ab.configure)
    assert callable(ab.close)
    assert callable(ab.default_browser)
    assert callable(ab.reset)
    for namespace in _DEFAULT_NAMESPACE_NAMES:
        assert namespace in ab.__all__


@pytest.mark.parametrize("namespace", sorted(_DEFAULT_NAMESPACE_NAMES))
def test_default_namespace_proxy_is_non_callable(namespace: str) -> None:
    assert namespace in ab.__all__
    assert not callable(getattr(ab, namespace))


@pytest.mark.parametrize("namespace", sorted(_DEFAULT_NAMESPACE_NAMES))
def test_default_namespace_proxy_matches_browser_methods(namespace: str) -> None:
    browser = Browser(native_session=NativeSession(native=EchoNative()))
    proxy_methods = _public_method_names(getattr(ab, namespace))
    browser_methods = _public_method_names(getattr(browser, namespace))
    assert proxy_methods == browser_methods


def test_package_root_exposes_pure_session_id_helper() -> None:
    assert ab.session_id(prefix="docs").session.startswith("docs-")


def _browser_with_public_cdp(monkeypatch: pytest.MonkeyPatch) -> Browser:
    cdp_controller = importlib.import_module("agentbrowser.cdp.controller")
    monkeypatch.setattr(cdp_controller, "CDPClient", _PublicCDPClient)
    browser = Browser(native_session=NativeSession(native=_CDPNative()))
    browser.page.open("https://example.com/one")
    return browser


def test_cdp_navigation_invalidates_frame_and_context_handles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    browser = _browser_with_public_cdp(monkeypatch)
    frame = browser.cdp.frames.get(name="target")
    context = frame.context()
    assert frame.evaluate("location.href").startswith("context:s-one")

    browser.page.set_content("<h1>Next</h1>")

    with pytest.raises(CDPStaleObjectError):
        frame.evaluate("location.href")
    with pytest.raises(CDPStaleObjectError):
        context.evaluate("location.href")


def test_cdp_refreshed_frame_works_after_navigation(monkeypatch: pytest.MonkeyPatch) -> None:
    browser = _browser_with_public_cdp(monkeypatch)

    browser.page.set_content("<h1>Next</h1>")

    refreshed = browser.cdp.frames.get(name="target")
    assert refreshed.evaluate("location.href").startswith("context:s-one")


def test_cdp_tab_switch_invalidates_old_target_handles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    browser = _browser_with_public_cdp(monkeypatch)
    frame = browser.cdp.frames.get(name="target")

    browser.tabs.switch(id="docs")

    with pytest.raises(CDPStaleObjectError):
        frame.evaluate("location.href")
    assert browser.cdp.evaluate("location.href").startswith("context:s-two")


def test_package_root_default_session_matches_readme_agent_workflow() -> None:
    try:
        ab.configure(native_session=NativeSession(native=ReadmeWorkflowNative()))
        ab.page.open("example.com")
        page = ab.agent.observe()
        assert "Learn more" in page.text
        ab.find.text("Learn more").click()
        ab.page.wait_for_url("*://www.iana.org/*")
        assert ab.page.title() == "Example Domains"
        assert ab.page.url() == "https://www.iana.org/help/example-domains"
    finally:
        ab.reset()


def test_locator_check_returns_chainable_handle() -> None:
    native = LocatorStateNative()
    browser = Browser(native_session=NativeSession(native=native))
    email = browser.find.css("#email")

    assert email.check() is email


def test_locator_wait_returns_chainable_handle() -> None:
    native = LocatorStateNative()
    browser = Browser(native_session=NativeSession(native=native))
    email = browser.find.css("#email")

    assert email.wait(timeout_ms=500) is email


def test_locator_type_returns_chainable_handle() -> None:
    native = LocatorStateNative()
    browser = Browser(native_session=NativeSession(native=native))
    email = browser.find.css("#email")

    assert email.type("Ada") is email


def test_locator_input_value_returns_typed_text() -> None:
    native = LocatorStateNative()
    browser = Browser(native_session=NativeSession(native=native))
    email = browser.find.css("#email")

    email.type("Ada")

    assert email.input_value() == "Ada"


def test_locator_screenshot_returns_capture_result(tmp_path: Path) -> None:
    native = ScreenshotNative(tmp_path / "panel.png")
    browser = Browser(native_session=NativeSession(native=native))

    panel = browser.find.css("#panel")

    shot = panel.screenshot(tmp_path / "panel.png", wait_ms=0)

    assert shot.path == tmp_path / "panel.png"


def test_async_context_manager_preserves_body_exception_when_close_fails() -> None:
    async def run() -> None:
        native = CloseErrorNative()
        with pytest.raises(RuntimeError, match="body failed"):
            async with AsyncBrowser(native_session=AsyncNativeSession(native=native)) as browser:
                await browser.launch_process()
                raise RuntimeError("body failed")

        assert native.commands[-1]["action"] == "__agent_browser_internal_shutdown"

    asyncio.run(run())


def test_async_context_manager_surfaces_close_error_without_body_exception() -> None:
    async def run() -> None:
        native = CloseErrorNative()
        with pytest.raises(BrowserError) as exc_info:
            async with AsyncBrowser(native_session=AsyncNativeSession(native=native)) as browser:
                await browser.launch_process()

        assert exc_info.value.action == "close"
        assert native.commands[-1]["action"] == "__agent_browser_internal_shutdown"

    asyncio.run(run())


def test_async_launch_installs_browser_and_passes_resolved_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run() -> None:
        native = EchoNative()
        browser = AsyncBrowser(native_session=AsyncNativeSession(native=native))
        browser._auto_install = True
        result = InstallResult(
            executable_path=Path("/tmp/async-chrome"),
            version="123",
            source="download",
            installed=True,
        )
        monkeypatch.setattr("agentbrowser.browser_async.ensure_installed", lambda: result)

        await browser.launch_process()
        await browser.aclose()

        assert native.commands[0]["executablePath"] == "/tmp/async-chrome"

    asyncio.run(run())


def test_async_locator_screenshot_returns_capture_result(tmp_path: Path) -> None:
    async def run() -> None:
        native = ScreenshotNative(tmp_path / "async-panel.png")
        browser = AsyncBrowser(native_session=AsyncNativeSession(native=native))

        panel = browser.find.css("#panel")

        shot = await panel.screenshot(
            tmp_path / "async-panel.png",
            wait_ms=0,
        )

        assert shot.path == tmp_path / "async-panel.png"

    asyncio.run(run())


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ({"code": "top"}, "top"),
        ({"error_code": "snake"}, "snake"),
        ({"errorCode": "camel"}, "camel"),
        ({"data": {"code": "nested"}}, "nested"),
        ({"data": {"error_code": "nested_snake"}}, "nested_snake"),
        ({"data": {"errorCode": "nested_camel"}}, "nested_camel"),
        ({}, None),
    ],
)
def test_browser_error_code_extraction_is_table_driven(
    response: Mapping[str, Any],
    expected: str | None,
) -> None:
    assert BrowserError("click", "failed", response).code == expected


def test_browser_async_native_data_preserves_raw_escape_hatch_payload() -> None:
    async def run() -> None:
        native = EchoNative()
        browser = AsyncBrowser(native_session=AsyncNativeSession(native=native))

        await browser.native.data(
            "dispatch",
            selector="#target",
            event="click",
            eventInit={"bubbles": True},
        )
        await browser.aclose()

        assert native.commands[0]["action"] == "dispatch"
        assert native.commands[0]["eventInit"] == {"bubbles": True}

    asyncio.run(run())


def test_browser_async_page_open_normalizes_host_like_url() -> None:
    async def run() -> None:
        native = EchoNative()
        browser = AsyncBrowser(native_session=AsyncNativeSession(native=native))

        await browser.page.open("example.com")
        await browser.aclose()

        navigation = next(command for command in native.commands if command["action"] == "navigate")
        assert navigation["url"] == "https://example.com"

    asyncio.run(run())


def test_browser_async_page_read_returns_typed_result() -> None:
    async def run() -> None:
        native = ResponseNative(
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
        browser = AsyncBrowser(native_session=AsyncNativeSession(native=native))

        result = await browser.page.read(
            "example.com/docs",
            mode=ReadMode.outline_only(),
            timeout_ms=1000,
        )
        await browser.aclose()

        assert isinstance(result, ReadResult)
        assert result.source == "accept-markdown-outline"
        assert native.commands[0]["action"] == "read"
        assert native.commands[0]["url"] == "https://example.com/docs"
        assert native.commands[0]["outline"] is True

    asyncio.run(run())


def test_browser_async_tabs_new_uses_public_namespace() -> None:
    async def run() -> None:
        native = ResponseNative(
            {"tab_new": {"tab": {"id": "t1", "url": "https://example.com/docs", "label": "docs"}}}
        )
        browser = AsyncBrowser(native_session=AsyncNativeSession(native=native))

        tab = await browser.tabs.new("https://example.com/docs", label="docs")
        await browser.aclose()

        assert tab.id == "t1"
        assert tab.label == "docs"

    asyncio.run(run())


def test_browser_async_tabs_list_uses_public_namespace() -> None:
    async def run() -> None:
        browser = AsyncBrowser(native_session=AsyncNativeSession(native=ResponseNative()))

        tabs = await browser.tabs.list()
        await browser.aclose()

        assert tabs == ()

    asyncio.run(run())


def test_browser_async_semantic_locator_click_returns_chainable_handle() -> None:
    async def run() -> None:
        native = SemanticLocatorNative()
        browser = AsyncBrowser(native_session=AsyncNativeSession(native=native))
        submit = browser.find.role("button", name="Submit", exact=True)

        clicked = await submit.click()
        await browser.aclose()

        assert clicked is submit

    asyncio.run(run())


def test_browser_async_locator_check_returns_chainable_handle() -> None:
    async def run() -> None:
        native = LocatorStateNative()
        browser = AsyncBrowser(native_session=AsyncNativeSession(native=native))
        email = browser.find.css("#email")

        assert await email.check() is email
        await browser.aclose()

    asyncio.run(run())


def test_browser_async_locator_wait_returns_chainable_handle() -> None:
    async def run() -> None:
        native = LocatorStateNative()
        browser = AsyncBrowser(native_session=AsyncNativeSession(native=native))
        email = browser.find.css("#email")

        assert await email.wait(timeout_ms=500) is email
        await browser.aclose()

    asyncio.run(run())


def test_browser_async_locator_type_returns_chainable_handle() -> None:
    async def run() -> None:
        native = LocatorStateNative()
        browser = AsyncBrowser(native_session=AsyncNativeSession(native=native))
        email = browser.find.css("#email")

        assert await email.type("Ada") is email
        await browser.aclose()

    asyncio.run(run())


def test_browser_async_locator_input_value_returns_typed_text() -> None:
    async def run() -> None:
        native = LocatorStateNative()
        browser = AsyncBrowser(native_session=AsyncNativeSession(native=native))
        email = browser.find.css("#email")

        await email.type("Ada")

        assert await email.input_value() == "Ada"
        await browser.aclose()

    asyncio.run(run())


def test_browser_async_connect_uses_constructor_cdp_options_without_navigation() -> None:
    async def run() -> None:
        browser = await AsyncBrowser.attach(
            CDPAttach(url="ws://127.0.0.1:9222/devtools/browser/test"),
            native_session=AsyncNativeSession(native=CdpConnectNative()),
        )

        assert (await browser.tabs.list())[0].id == "t1"
        await browser.aclose()

    asyncio.run(run())


def test_async_page_ready_rejects_negative_min_text_length() -> None:
    async def run() -> None:
        native = EchoNative()
        browser = AsyncBrowser(native_session=AsyncNativeSession(native=native))

        with pytest.raises(ValueError, match="min_text_length"):
            await browser.page.ready(min_text_length=-1)

        assert native.commands == []
        await browser.aclose()

    asyncio.run(run())


def test_async_xpath_locator_serializes_native_xpath_selector() -> None:
    async def run() -> None:
        native = ResponseNative({"count": {"count": 1}})
        browser = AsyncBrowser(native_session=AsyncNativeSession(native=native))

        count = await browser.find.xpath("//a").count()
        await browser.aclose()

        assert count == 1
        assert native.commands[0]["selector"] == "xpath=//a"

    asyncio.run(run())


def test_async_tabs_open_reuses_labelled_tab() -> None:
    async def run() -> None:
        native = TabReuseNative()
        browser = AsyncBrowser(native_session=AsyncNativeSession(native=native))

        tab = await browser.tabs.open("example.com/docs", label="docs")
        await browser.aclose()

        assert tab.id == "t1"
        assert tab.label == "docs"
        assert tab.url == "https://example.com/docs"
        assert tab.active is True

    asyncio.run(run())


def _public_method_names(target: object) -> set[str]:
    if isinstance(target, type):
        names: set[str] = set()
        for name in dir(target):
            if name.startswith("_"):
                continue
            try:
                value = inspect.getattr_static(target, name)
            except AttributeError:
                continue
            if callable(value):
                names.add(name)
        return names

    names: set[str] = set()
    for name in dir(target):
        if name.startswith("_"):
            continue
        try:
            value = getattr(target, name)
        except (AttributeError, TypeError):
            continue
        if callable(value):
            names.add(name)
    return names


def test_browser_and_browser_async_public_methods_stay_in_parity() -> None:
    sync_methods = _public_method_names(Browser)
    async_methods = _public_method_names(AsyncBrowser) - {"aclose"}

    assert async_methods == sync_methods


@pytest.mark.parametrize("name", sorted(_public_method_names(Browser)))
def test_browser_and_browser_async_public_signature_stays_in_parity(name: str) -> None:
    sync_params = tuple(inspect.signature(getattr(Browser, name)).parameters.values())
    async_params = tuple(inspect.signature(getattr(AsyncBrowser, name)).parameters.values())
    assert async_params == sync_params


def _sync_async_namespace_pairs() -> list[tuple[object, object, str]]:
    browser = Browser(native_session=NativeSession(native=EchoNative()))
    async_browser = AsyncBrowser(native_session=AsyncNativeSession(native=EchoNative()))
    return [
        *[
            (getattr(browser, namespace), getattr(async_browser, namespace), namespace)
            for namespace in sorted(_BROWSER_NAMESPACE_NAMES)
        ],
        (browser.find.css("#target"), async_browser.find.css("#target"), "locator"),
        (browser.find.text("Continue"), async_browser.find.text("Continue"), "semantic locator"),
    ]


def _sync_async_namespace_method_cases() -> list[tuple[object, object, str, str]]:
    cases: list[tuple[object, object, str, str]] = []
    for sync_object, async_object, label in _sync_async_namespace_pairs():
        for name in sorted(_public_method_names(sync_object)):
            cases.append((sync_object, async_object, label, name))
    return cases


@pytest.mark.parametrize(
    ("sync_object", "async_object", "label"),
    _sync_async_namespace_pairs(),
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_sync_async_namespace_public_methods_have_same_names(
    sync_object: object,
    async_object: object,
    label: str,
) -> None:
    assert _public_method_names(async_object) == _public_method_names(sync_object), label


@pytest.mark.parametrize(
    ("sync_object", "async_object", "label", "name"),
    _sync_async_namespace_method_cases(),
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_sync_async_namespace_public_method_signatures_stay_in_parity(
    sync_object: object,
    async_object: object,
    label: str,
    name: str,
) -> None:
    assert name in _public_method_names(async_object), label

    sync_params = tuple(inspect.signature(getattr(sync_object, name)).parameters.values())
    async_params = tuple(inspect.signature(getattr(async_object, name)).parameters.values())
    assert async_params == sync_params, f"{label}.{name}"


def test_async_screenshot_wait_ms_zero_still_captures(tmp_path: Path) -> None:
    async def run() -> None:
        path = tmp_path / "page.png"
        path.write_bytes(b"fake png bytes")
        native = ScreenshotNative(path)
        browser = AsyncBrowser(native_session=AsyncNativeSession(native=native))

        result = await browser.capture.screenshot(wait_ms=0)

        assert result.path == path

    asyncio.run(run())


def test_async_screenshot_wait_ms_rejects_negative_values(tmp_path: Path) -> None:
    async def run() -> None:
        native = ScreenshotNative(tmp_path / "page.png")
        browser = AsyncBrowser(native_session=AsyncNativeSession(native=native))

        with pytest.raises(ValueError, match="wait_ms"):
            await browser.capture.screenshot(wait_ms=-1)

        assert native.commands == []

    asyncio.run(run())


def test_browser_async_public_surface_does_not_block_event_loop() -> None:
    async def run() -> None:
        native = BlockingNative()
        browser = AsyncBrowser(native_session=AsyncNativeSession(native=native))
        blocked = asyncio.create_task(browser.native.data("block"))
        assert await asyncio.to_thread(native.started.wait, 1.0)

        ticks = 0

        async def ticker() -> None:
            nonlocal ticks
            for _ in range(3):
                await asyncio.sleep(0.01)
                ticks += 1

        await ticker()
        assert ticks == 3
        native.release.set()
        assert await blocked == {"ok": True}
        await browser.aclose()

    asyncio.run(run())


def test_async_close_reports_queued_work_without_cancelling_active_native_work() -> None:
    async def run() -> None:
        native = BlockingNative()
        browser = AsyncBrowser(native_session=AsyncNativeSession(native=native))
        active = asyncio.create_task(browser.native.data("block"))
        assert await asyncio.to_thread(native.started.wait, 1.0)
        queued = asyncio.create_task(browser.native.data("queued"))

        with pytest.raises(RuntimeError, match="worker did not stop"):
            await browser.aclose(timeout=0.1)

        assert not active.done()
        with pytest.raises(RuntimeError, match="AsyncNativeSession is closed"):
            await queued
        native.release.set()
        assert await active == {"ok": True}
        await browser.aclose()
        assert [command["action"] for command in native.commands] == [
            "block",
            "__agent_browser_internal_shutdown",
        ]

    asyncio.run(run())


def test_async_close_skips_queued_work_after_active_command_finishes() -> None:
    async def run() -> None:
        native = BlockingNative()
        browser = AsyncBrowser(native_session=AsyncNativeSession(native=native))
        active = asyncio.create_task(browser.native.data("block"))
        assert await asyncio.to_thread(native.started.wait, 1.0)
        queued = asyncio.create_task(browser.native.data("queued"))

        close_task = asyncio.create_task(browser.close(timeout=1.0))
        await asyncio.sleep(0)
        native.release.set()

        assert await active == {"ok": True}
        with pytest.raises(RuntimeError, match="AsyncNativeSession is closed"):
            await queued
        await close_task
        assert [command["action"] for command in native.commands] == [
            "block",
            "__agent_browser_internal_shutdown",
        ]

    asyncio.run(run())


def test_async_confirm_rejects_wrong_id() -> None:
    async def run() -> None:
        browser = AsyncBrowser(
            native_session=AsyncNativeSession(native=StatefulConfirmationNative())
        )
        try:
            with pytest.raises(ActionConfirmationRequired) as exc_info:
                await browser.native.data("click")
            with pytest.raises(BrowserError) as wrong_id:
                await browser.confirm("wrong")
            assert wrong_id.value.action == "confirm"
            assert exc_info.value.confirmation_id
        finally:
            await browser.aclose()

    asyncio.run(run())


def test_async_confirm_replays_pending_action() -> None:
    async def run() -> None:
        browser = AsyncBrowser(
            native_session=AsyncNativeSession(native=StatefulConfirmationNative())
        )
        try:
            with pytest.raises(ActionConfirmationRequired) as exc_info:
                await browser.native.data("click")
            assert isinstance(exc_info.value.pending_action, AsyncPendingAction)
            assert await exc_info.value.pending_action.confirm() == {"clicked": "#danger"}
        finally:
            await browser.aclose()

    asyncio.run(run())


def test_async_pending_action_reports_confirmed_action_failure() -> None:
    async def run() -> None:
        browser = AsyncBrowser(
            native_session=AsyncNativeSession(native=FailingConfirmationNative())
        )
        try:
            with pytest.raises(ActionConfirmationRequired) as confirmation:
                await browser.native.data("click")
            pending = confirmation.value.pending_action
            with pytest.raises(BrowserError) as failed:
                await pending.confirm()
            assert failed.value.action == "click"
            with pytest.raises(BrowserError) as retry_failed:
                await pending.confirm()
            assert retry_failed.value.action == "click"
        finally:
            await browser.aclose()

    asyncio.run(run())


def test_async_confirmed_navigation_marks_browser_launched() -> None:
    async def run() -> None:
        browser = AsyncBrowser(
            native_session=AsyncNativeSession(
                native=ConfirmingActionNative("navigate", {"url": "https://example.com"})
            )
        )
        try:
            with pytest.raises(ActionConfirmationRequired) as confirmation:
                await browser.page.open("example.com")
            await confirmation.value.pending_action.confirm()
            assert browser.is_launched is True
        finally:
            await browser.aclose()

    asyncio.run(run())


def test_async_confirmed_close_marks_browser_not_launched() -> None:
    async def run() -> None:
        browser = AsyncBrowser(
            native_session=AsyncNativeSession(native=ConfirmingActionNative("close"))
        )
        await browser.launch_process()
        await browser.close()
        assert browser.is_launched is False

    asyncio.run(run())


def test_async_native_data_returns_non_object_native_data() -> None:
    async def run() -> None:
        browser = AsyncBrowser(native_session=AsyncNativeSession(native=RawValueNative(["items"])))
        try:
            assert await browser.native.data("raw_array", expect="any") == ["items"]
        finally:
            await browser.aclose()

    asyncio.run(run())


def test_scripts_add_init_launches_and_returns_identifier(tmp_path: Path) -> None:
    native = AgentNative()
    browser = Browser(native_session=NativeSession(native=native))
    script = tmp_path / "init.js"
    script.write_text("window.__agentBrowserReady = true")

    identifier = browser.scripts.add_init(path=script)

    assert identifier == "init-1"
    assert browser.is_launched is True


def test_clipboard_read_returns_native_text() -> None:
    browser = Browser(native_session=NativeSession(native=ClipboardNative()))

    assert browser.clipboard.read() == "hello"


def test_clipboard_write_sends_text_to_native() -> None:
    native = ClipboardNative()
    browser = Browser(native_session=NativeSession(native=native))

    browser.clipboard.write("hello")

    assert native.written_text == "hello"


def test_dialog_status_returns_native_status() -> None:
    native = ResponseNative({"dialog": {"open": False}})
    browser = Browser(native_session=NativeSession(native=native))

    assert browser.dialogs.status() == {"open": False}


class _FrameNative:
    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        if command["action"] == "frame":
            data = {"frame": command["selector"]}
        elif command["action"] == "mainframe":
            data = {"frame": "main"}
        else:
            raise AssertionError(f"unexpected frame command: {command}")
        return json.dumps({"id": command["id"], "success": True, "data": data})


def test_active_frame_selects_selector() -> None:
    native = _FrameNative()
    browser = Browser(native_session=NativeSession(native=native))

    assert browser.active_frame.select(selector="@e1") == {"frame": "@e1"}


def test_active_frame_restores_main_frame() -> None:
    native = _FrameNative()
    browser = Browser(native_session=NativeSession(native=native))

    assert browser.active_frame.main() == {"frame": "main"}


def test_download_wait_returns_requested_path() -> None:
    class DownloadNative:
        def execute_json(self, command_json: str) -> str:
            command = json.loads(command_json)
            if command["action"] != "waitfordownload":
                raise AssertionError(f"unexpected download command: {command}")
            data = {"path": command["path"]}
            return json.dumps({"id": command["id"], "success": True, "data": data})

    native = DownloadNative()
    browser = Browser(native_session=NativeSession(native=native))

    assert browser.downloads.wait(Path("next.bin")) == Path("next.bin")


def test_pdf_capture_returns_requested_path() -> None:
    class PdfNative:
        def execute_json(self, command_json: str) -> str:
            command = json.loads(command_json)
            if command["action"] != "pdf":
                raise AssertionError(f"unexpected pdf command: {command}")
            data = {"path": command["path"]}
            return json.dumps({"id": command["id"], "success": True, "data": data})

    native = PdfNative()
    browser = Browser(native_session=NativeSession(native=native))

    assert browser.capture.pdf(Path("page.pdf")) == Path("page.pdf")
