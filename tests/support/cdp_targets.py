from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from agentbrowser.cdp import (
    CDPController,
)
from agentbrowser.execution.commands import Command
from tests.support.cdp_transport import _context_event_for_session


class MultiTargetCommands:
    def __init__(self) -> None:
        self.current_url = "https://example.com/one"

    def execute(self, command: Command[Any]) -> Any:
        if command.action == "cdp_url":
            data = {"cdpUrl": "ws://cdp"}
        elif command.action == "url":
            data = {"url": self.current_url}
        elif command.action == "tab_list":
            data = {
                "tabs": [
                    {
                        "id": "t1",
                        "targetId": "one",
                        "url": "https://example.com/one",
                        "title": "One",
                        "label": "first",
                    },
                    {
                        "id": "t2",
                        "targetId": "two",
                        "url": "https://example.com/two",
                        "title": "Two",
                        "label": "second",
                    },
                ]
            }
        else:
            raise AssertionError(command.action)
        return command.decode(data)


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


def _multi_target_controller(browser: MultiTargetCommands) -> CDPController:
    return CDPController(cast(Any, browser), client_factory=cast(Any, MultiTargetClient))
