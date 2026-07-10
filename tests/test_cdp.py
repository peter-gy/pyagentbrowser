from __future__ import annotations

import asyncio
import builtins
import importlib
import json
from collections import deque
from collections.abc import Mapping
from typing import Any, cast

import pytest

from agentbrowser import AgentBrowserError, AsyncBrowser, Browser
from agentbrowser.cdp import (
    AsyncCDPClient,
    AsyncCDPController,
    CDPClient,
    CDPClosedError,
    CDPContextNotFoundError,
    CDPController,
    CDPError,
    CDPFrameNotFoundError,
    CDPPageSession,
    CDPStaleObjectError,
    CDPTargetAmbiguityError,
    CDPTimeoutError,
)
from agentbrowser.models import TabInfo
from agentbrowser.session import NativeSession
from agentbrowser.session_async import AsyncNativeSession

pytestmark = pytest.mark.sdk_dx


class FakeWebSocket:
    def __init__(
        self,
        messages: list[Mapping[str, Any]] | None = None,
        *,
        responses: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        self.messages = deque(json.dumps(message) for message in messages or [])
        self.responses = dict(responses or {})
        self.sent: list[dict[str, Any]] = []
        self.closed = False

    def send(self, message: str) -> None:
        request = json.loads(message)
        self.sent.append(request)
        result = self.responses.get(str(request["method"]))
        if result is not None:
            self.messages.append(json.dumps({"id": request["id"], "result": dict(result)}))

    def recv(self, timeout: float | None = None) -> str:
        if not self.messages:
            raise TimeoutError
        return self.messages.popleft()

    def close(self) -> None:
        self.closed = True


class DelayedAsyncWebSocket:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.sent_event = asyncio.Event()
        self.response_event = asyncio.Event()
        self.closed = False

    async def send(self, message: str) -> None:
        self.sent.append(json.loads(message))
        self.sent_event.set()

    async def recv(self) -> str:
        await self.response_event.wait()
        return json.dumps({"id": self.sent[0]["id"], "result": {"ok": True}})

    async def close(self) -> None:
        self.closed = True


class FakeCDPTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any], str | None]] = []
        self.events = [_context_event(1, "main-unique", "main", is_default=True)]

    def send(
        self,
        method: str,
        params: Mapping[str, Any] | None = None,
        *,
        session_id: str | None = None,
    ) -> Mapping[str, Any]:
        self.calls.append((method, dict(params or {}), session_id))
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
                                "url": "https://example.com/frame",
                            }
                        }
                    ],
                }
            }
        if method == "DOM.getDocument":
            return {"root": {"nodeId": 10}}
        if method == "DOM.querySelector":
            selector = str(dict(params or {}).get("selector", ""))
            node_ids = {
                "#target": 11,
                "#target-frame": 11,
                "#not-a-frame": 12,
            }
            return {"nodeId": node_ids.get(selector, 0)}
        if method == "DOM.describeNode":
            node_id = dict(params or {}).get("nodeId")
            if node_id == 11:
                return {"node": {"nodeName": "IFRAME", "frameId": "child"}}
            if node_id == 12:
                return {"node": {"nodeName": "DIV"}}
            raise AssertionError(f"unexpected node id {node_id!r}")
        if method == "Runtime.evaluate":
            params_dict = dict(params or {})
            context_id = params_dict.get("uniqueContextId", params_dict.get("contextId"))
            return {"result": {"type": "string", "value": f"context:{context_id}"}}
        raise AssertionError(f"unexpected CDP method {method}")

    def drain_events(self, *, timeout: float = 0.05) -> list[Mapping[str, Any]]:
        events = self.events
        self.events = []
        return events


class PublicPathCDPClient(FakeCDPTransport):
    def __init__(self, _url: str) -> None:
        super().__init__()
        self.events = [
            _context_event(1, "main-unique", "main", is_default=True),
            _context_event(2, "child-unique", "child", is_default=True),
        ]

    def send(
        self,
        method: str,
        params: Mapping[str, Any] | None = None,
        *,
        session_id: str | None = None,
    ) -> Mapping[str, Any]:
        if method == "Target.getTargets":
            return {
                "targetInfos": [
                    {
                        "targetId": "target",
                        "type": "page",
                        "url": "https://example.com",
                        "title": "Example",
                    }
                ]
            }
        if method == "Target.attachToTarget":
            return {"sessionId": "s1"}
        return super().send(method, params, session_id=session_id)

    def close(self) -> None:
        pass


class PublicPathAsyncCDPClient:
    def __init__(self, url: str) -> None:
        self._sync = PublicPathCDPClient(url)

    async def send(
        self,
        method: str,
        params: Mapping[str, Any] | None = None,
        *,
        session_id: str | None = None,
    ) -> Mapping[str, Any]:
        return self._sync.send(method, params, session_id=session_id)

    async def drain_events(self, *, timeout: float = 0.05) -> list[Mapping[str, Any]]:
        return self._sync.drain_events(timeout=timeout)

    async def close(self) -> None:
        pass


class PublicPathNative:
    def __init__(self) -> None:
        self.commands: list[dict[str, Any]] = []

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        self.commands.append(command)
        if command["action"] == "evaluate":
            data: Mapping[str, Any] = {"result": 2}
        elif command["action"] == "cdp_url":
            data = {"cdpUrl": "ws://cdp"}
        elif command["action"] == "url":
            data = {"url": "https://example.com"}
        elif command["action"] == "__agent_browser_internal_shutdown":
            data = {
                "closed": True,
                "restoreStatus": "not_configured",
                "saveStatus": "not_configured",
            }
        else:
            data = {}
        return json.dumps({"id": command["id"], "success": True, "data": data})


class MultiTargetBrowser:
    is_launched = True

    def __init__(self) -> None:
        self.current_url = "https://example.com/one"
        self.page = self
        self.tabs = self

    def url(self) -> str:
        return self.current_url

    def list(self) -> tuple[TabInfo, ...]:
        return (
            TabInfo(
                id="t1",
                url="https://example.com/one",
                title="One",
                label="first",
                raw={"targetId": "one"},
            ),
            TabInfo(
                id="t2",
                url="https://example.com/two",
                title="Two",
                label="second",
                raw={"targetId": "two"},
            ),
        )

    def _command(self, action: str, **_params: Any) -> Mapping[str, Any]:
        assert action == "cdp_url"
        return {"cdpUrl": "ws://cdp"}


class MultiTargetClient:
    def __init__(self, _url: str) -> None:
        self.calls: list[tuple[str, dict[str, Any], str | None]] = []
        self._pending_events: list[Mapping[str, Any]] = []

    def send(
        self,
        method: str,
        params: Mapping[str, Any] | None = None,
        *,
        session_id: str | None = None,
    ) -> Mapping[str, Any]:
        params_dict = dict(params or {})
        self.calls.append((method, params_dict, session_id))
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
            target_id = str(params_dict["targetId"])
            self._pending_events = [_context_event_for_session(f"s-{target_id}", "main")]
            return {"sessionId": f"s-{target_id}"}
        if method in {"Page.enable", "DOM.enable", "Runtime.enable"}:
            return {}
        if method == "Page.getFrameTree":
            assert session_id is not None
            return {
                "frameTree": {
                    "frame": {
                        "id": "main",
                        "name": "",
                        "url": f"https://example.com/{session_id.removeprefix('s-')}",
                    }
                }
            }
        if method == "Runtime.evaluate":
            return {"result": {"type": "string", "value": session_id}}
        raise AssertionError(f"unexpected CDP method {method}")

    def drain_events(self, *, timeout: float = 0.05) -> list[Mapping[str, Any]]:
        events = self._pending_events
        self._pending_events = []
        return events

    def close(self) -> None:
        pass


def _multi_target_controller(browser: MultiTargetBrowser) -> CDPController:
    return CDPController(browser, client_factory=cast(Any, MultiTargetClient))


def test_cdp_client_queues_events_while_waiting_for_response() -> None:
    class EventBeforeResponseWebSocket(FakeWebSocket):
        def send(self, message: str) -> None:
            request = json.loads(message)
            self.sent.append(request)
            if request["method"] == "Runtime.evaluate":
                self.messages.extend(
                    [
                        json.dumps(
                            {
                                "method": "Runtime.executionContextCreated",
                                "params": {"context": {"id": 1}},
                            }
                        ),
                        json.dumps({"id": request["id"], "result": {"ok": True}}),
                    ]
                )

    websocket = EventBeforeResponseWebSocket()
    client = CDPClient("ws://cdp", connect=lambda _url: websocket)

    assert client.send("Runtime.evaluate", {"expression": "1"}, session_id="s1") == {"ok": True}
    assert client.pop_events()[0]["method"] == "Runtime.executionContextCreated"


def test_cdp_client_timeout_is_typed_sdk_error() -> None:
    client = CDPClient("ws://cdp", timeout=0.25, connect=lambda _url: FakeWebSocket([]))

    with pytest.raises(CDPTimeoutError) as exc_info:
        client.send("Runtime.evaluate", {"expression": "1"})

    assert exc_info.value.method == "Runtime.evaluate"
    assert isinstance(exc_info.value, CDPError)
    assert isinstance(exc_info.value, AgentBrowserError)


def test_cdp_client_rejects_send_after_close() -> None:
    client = CDPClient("ws://cdp", connect=lambda _url: FakeWebSocket([]))

    client.close()

    with pytest.raises(CDPClosedError, match="CDP client is closed"):
        client.send("Runtime.evaluate", {"expression": "1"})


def test_cdp_client_rejects_event_drain_after_close() -> None:
    client = CDPClient("ws://cdp", connect=lambda _url: FakeWebSocket([]))

    client.close()

    with pytest.raises(CDPClosedError, match="CDP client is closed"):
        client.drain_events()


def test_async_cdp_client_rejects_send_after_close() -> None:
    async def run() -> None:
        client = AsyncCDPClient("ws://cdp")

        await client.close()

        with pytest.raises(CDPClosedError, match="CDP client is closed"):
            await client.send("Runtime.evaluate", {"expression": "1"})

    asyncio.run(run())


def test_async_cdp_client_close_wins_over_in_flight_response() -> None:
    async def run() -> None:
        websocket = DelayedAsyncWebSocket()

        async def connect(_url: str) -> DelayedAsyncWebSocket:
            return websocket

        client = AsyncCDPClient("ws://cdp", connect=connect)
        pending = asyncio.create_task(client.send("Runtime.evaluate"))
        await websocket.sent_event.wait()

        await client.close()
        websocket.response_event.set()

        with pytest.raises(CDPClosedError, match="CDP client is closed"):
            await pending
        assert websocket.closed is True

    asyncio.run(run())


def test_cdp_controller_reresolves_active_target_after_invalidation() -> None:
    browser = MultiTargetBrowser()
    controller = _multi_target_controller(browser)

    assert controller.evaluate("location.href") == "s-one"
    browser.current_url = "https://example.com/two"
    controller.invalidate()
    assert controller.evaluate("location.href") == "s-two"


def test_cdp_controller_selects_explicit_target_id() -> None:
    browser = MultiTargetBrowser()
    controller = _multi_target_controller(browser)

    assert controller.target(target_id="one").evaluate("location.href") == "s-one"


def test_cdp_controller_selects_native_tab_label() -> None:
    browser = MultiTargetBrowser()
    controller = _multi_target_controller(browser)

    assert controller.target(label="second").evaluate("location.href") == "s-two"


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


def test_active_target_ambiguity_is_explicit() -> None:
    class FakeBrowser:
        is_launched = True
        page: FakeBrowser

        def __init__(self) -> None:
            self.page = self

        def url(self) -> str:
            return "https://example.com"

        def _command(self, action: str, **_params: Any) -> Mapping[str, Any]:
            assert action == "cdp_url"
            return {"cdpUrl": "ws://cdp"}

    class AmbiguousTargetClient:
        def __init__(self, _url: str) -> None:
            pass

        def send(
            self,
            method: str,
            params: Mapping[str, Any] | None = None,
            *,
            session_id: str | None = None,
        ) -> Mapping[str, Any]:
            del params, session_id
            if method != "Target.getTargets":
                return {}
            return {
                "targetInfos": [
                    {"targetId": "a", "type": "page", "url": "https://example.com"},
                    {"targetId": "b", "type": "page", "url": "https://example.com"},
                ]
            }

    with pytest.raises(
        CDPTargetAmbiguityError,
        match=r"Pass label=\.\.\., url=\.\.\., or target_id=\.\.\.",
    ):
        CDPController(
            FakeBrowser(),
            client_factory=cast(Any, AmbiguousTargetClient),
        ).evaluate("location.href")


def test_stale_frame_errors_after_invalidation() -> None:
    page = CDPPageSession(FakeCDPTransport(), session_id="s1", target_id="target")
    page.enable()
    frame = page.frame()

    page.invalidate()

    with pytest.raises(CDPStaleObjectError, match="frame is stale"):
        frame.evaluate("location.href")


def test_cdp_controller_close_blocks_reopen_and_stales_frame() -> None:
    browser = MultiTargetBrowser()
    controller = _multi_target_controller(browser)
    frame = controller.frame()

    controller.close()

    with pytest.raises(CDPStaleObjectError, match="frame is stale"):
        frame.evaluate("location.href")
    with pytest.raises(CDPClosedError, match="CDP controller is closed"):
        controller.evaluate("location.href")


def test_async_cdp_controller_close_blocks_reopen_and_stales_frame() -> None:
    async def run() -> None:
        browser = AsyncBrowser(_native_session=AsyncNativeSession(native=PublicPathNative()))
        controller = AsyncCDPController(
            browser,
            client_factory=cast(Any, PublicPathAsyncCDPClient),
        )
        frame = await controller.frame()

        await controller.close()

        with pytest.raises(CDPStaleObjectError, match="frame is stale"):
            await frame.evaluate("location.href")
        with pytest.raises(CDPClosedError, match="CDP controller is closed"):
            await controller.evaluate("location.href")
        await browser.close()

    asyncio.run(run())


def test_page_evaluate_without_context_uses_native_command() -> None:
    browser = Browser(_native_session=NativeSession(native=PublicPathNative()))

    assert browser.evaluate("1 + 1") == 2


def _browser_with_public_path_cdp(monkeypatch: pytest.MonkeyPatch) -> Browser:
    cdp_controller = importlib.import_module("agentbrowser.cdp.controller")
    monkeypatch.setattr(cdp_controller, "CDPClient", PublicPathCDPClient)
    return Browser(_native_session=NativeSession(native=PublicPathNative()))


def test_browser_cdp_frames_list_uses_public_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    browser = _browser_with_public_path_cdp(monkeypatch)

    frames = {frame.id: frame for frame in browser.cdp.frames.list()}
    assert frames["main"].url == "https://example.com"
    assert frames["child"].name == "target"


def test_browser_cdp_frames_lookup_by_name_uses_public_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    browser = _browser_with_public_path_cdp(monkeypatch)

    assert browser.cdp.frames.get(name="target").id == "child"


def test_browser_cdp_frames_lookup_by_selector_uses_public_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    browser = _browser_with_public_path_cdp(monkeypatch)

    assert browser.cdp.frames.get(selector="#target").id == "child"


def test_browser_cdp_evaluate_uses_frame_selector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cdp_controller = importlib.import_module("agentbrowser.cdp.controller")
    monkeypatch.setattr(cdp_controller, "CDPClient", PublicPathCDPClient)

    browser = Browser(_native_session=NativeSession(native=PublicPathNative()))

    assert browser.cdp.evaluate("document.title", frame="#target") == "context:child-unique"


def _block_websockets_import(monkeypatch: pytest.MonkeyPatch) -> None:
    original_import = builtins.__import__

    def import_without_websockets(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.startswith("websockets"):
            raise ModuleNotFoundError("No module named 'websockets'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_websockets)


def test_cdp_client_optional_extra_error_is_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    _block_websockets_import(monkeypatch)

    with pytest.raises(ImportError, match=r"pyagentbrowser\[cdp\]"):
        CDPClient("ws://cdp").send("Browser.getVersion")


def test_async_cdp_client_optional_extra_error_is_actionable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _block_websockets_import(monkeypatch)

    async def run() -> None:
        with pytest.raises(ImportError, match=r"pyagentbrowser\[cdp\]"):
            await AsyncCDPClient("ws://cdp").send("Browser.getVersion")

    asyncio.run(run())


async def _async_browser_with_public_path_cdp(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncBrowser:
    cdp_controller = importlib.import_module("agentbrowser.cdp.controller")
    monkeypatch.setattr(cdp_controller, "AsyncCDPClient", PublicPathAsyncCDPClient)
    return AsyncBrowser(_native_session=AsyncNativeSession(native=PublicPathNative()))


def test_browser_async_cdp_frames_list_uses_public_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run() -> None:
        browser = await _async_browser_with_public_path_cdp(monkeypatch)

        frames = {frame.id: frame for frame in await browser.cdp.frames.list()}
        assert frames["main"].url == "https://example.com"
        assert frames["child"].name == "target"
        await browser.close()

    asyncio.run(run())


def _context_event(
    context_id: int,
    unique_id: str,
    frame_id: str,
    *,
    origin: str = "https://example.com",
    name: str = "",
    context_type: str = "default",
    is_default: bool = True,
) -> Mapping[str, Any]:
    return {
        "sessionId": "s1",
        "method": "Runtime.executionContextCreated",
        "params": {
            "context": {
                "id": context_id,
                "uniqueId": unique_id,
                "origin": origin,
                "name": name,
                "auxData": {
                    "frameId": frame_id,
                    "type": context_type,
                    "isDefault": is_default,
                },
            }
        },
    }


def _context_event_for_session(session_id: str, frame_id: str) -> Mapping[str, Any]:
    event = dict(_context_event(1, f"{session_id}-unique", frame_id))
    event["sessionId"] = session_id
    return event
