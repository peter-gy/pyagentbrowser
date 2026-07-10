from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from threading import Event
from typing import Any, cast

NativeReply = Mapping[str, Any] | Callable[[dict[str, Any]], Mapping[str, Any]]
CLOSE_DATA = {
    "closed": True,
    "restoreStatus": "not_configured",
    "saveStatus": "not_configured",
}


class ScriptedNative:
    """Recording native boundary with action-specific canned replies."""

    def __init__(
        self,
        replies: Mapping[str, NativeReply] | None = None,
        *,
        default: NativeReply | None = None,
    ) -> None:
        self.replies = dict(replies or {})
        self.default = default
        self.commands: list[dict[str, Any]] = []

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        self.commands.append(command)
        reply = self.replies.get(str(command["action"]), self.default)
        if reply is None:
            raise AssertionError(f"unexpected native action: {command['action']}")
        result = (
            dict(reply)
            if isinstance(reply, Mapping)
            else cast(Callable[[dict[str, Any]], Mapping[str, Any]], reply)(command)
        )
        if command["action"] == "__agent_browser_internal_shutdown" and not result:
            result = dict(CLOSE_DATA)
        if "success" in result:
            response = dict(result)
            response.setdefault("id", command["id"])
        else:
            response = {"id": command["id"], "success": True, "data": dict(result)}
        return json.dumps(response)


class EchoNative(ScriptedNative):
    """Native boundary that returns each command as response data."""

    def __init__(self) -> None:
        super().__init__(default=lambda command: {"echo": command})


class ErrorNative(ScriptedNative):
    def __init__(self) -> None:
        super().__init__(default={"success": False, "error": "native rejected this command"})


class WarningNative(ScriptedNative):
    def __init__(self) -> None:
        super().__init__(
            default={
                "success": True,
                "warning": "dialog is blocking the page",
                "data": {"ok": True},
            }
        )


class ConfirmationNative:
    """One pending action followed by confirm or deny."""

    def __init__(self, *, action: str = "probe", result: Mapping[str, Any] | None = None) -> None:
        self.action = action
        self.result = dict(result or {"confirmed": True})
        self.commands: list[dict[str, Any]] = []
        self.confirmation_id = "confirmation-1"

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        self.commands.append(command)
        action = command["action"]
        if action == "confirm":
            if command.get("confirmation_id") != self.confirmation_id:
                return json.dumps(
                    {
                        "id": command["id"],
                        "success": False,
                        "error": "confirmation id mismatch",
                    }
                )
            data = {
                "confirmed": True,
                "action": self.action,
                "result": {
                    "id": "confirmed-result",
                    "success": True,
                    "data": self.result,
                },
            }
        elif action == "deny":
            data = {"denied": True, "action": self.action}
        elif action == "__agent_browser_internal_shutdown":
            data = dict(CLOSE_DATA)
        else:
            data = {
                "confirmation_required": True,
                "confirmation_id": self.confirmation_id,
                "action": action,
            }
        return json.dumps({"id": command["id"], "success": True, "data": data})


class BlockingNative:
    """Native boundary used to prove async ownership and shutdown ordering."""

    def __init__(self) -> None:
        self.commands: list[dict[str, Any]] = []
        self.started = Event()
        self.release = Event()

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        self.commands.append(command)
        if command["action"] == "block":
            self.started.set()
            self.release.wait(timeout=5)
        return json.dumps({"id": command["id"], "success": True, "data": {"ok": True}})


class RawResponseNative:
    def __init__(self, response: str) -> None:
        self.response = response

    def execute_json(self, command_json: str) -> str:
        del command_json
        return self.response
