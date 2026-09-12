from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


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
