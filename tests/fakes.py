from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from threading import Event
from typing import Any

LIFECYCLE_CLOSE_ACTIONS = {"close", "__agent_browser_internal_shutdown"}


class EchoNative:
    def __init__(self) -> None:
        self.commands: list[dict[str, Any]] = []

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        self.commands.append(command)
        return json.dumps({"id": command["id"], "success": True, "data": {"echo": command}})


class ErrorNative:
    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        return json.dumps(
            {
                "id": command["id"],
                "success": False,
                "error": "native rejected this command",
            }
        )


class CloseErrorNative:
    def __init__(self) -> None:
        self.commands: list[dict[str, Any]] = []

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        self.commands.append(command)
        if command["action"] in LIFECYCLE_CLOSE_ACTIONS:
            return json.dumps(
                {
                    "id": command["id"],
                    "success": False,
                    "error": "native rejected close",
                }
            )
        return json.dumps({"id": command["id"], "success": True, "data": {"echo": command}})


class WarningNative:
    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        return json.dumps(
            {
                "id": command["id"],
                "success": True,
                "warning": "dialog is blocking the page",
                "data": {"ok": True},
            }
        )


class ConfirmationNative:
    def __init__(self) -> None:
        self.commands: list[dict[str, Any]] = []

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        self.commands.append(command)
        if command["action"] in LIFECYCLE_CLOSE_ACTIONS:
            return json.dumps({"id": command["id"], "success": True, "data": {}})
        if command["action"] == "confirm":
            return json.dumps(
                {
                    "id": command["id"],
                    "success": True,
                    "data": {
                        "confirmed": True,
                        "action": "click",
                        "result": {
                            "id": "native1",
                            "success": True,
                            "data": {"clicked": "#danger"},
                        },
                    },
                }
            )
        if command["action"] == "deny":
            return json.dumps(
                {
                    "id": command["id"],
                    "success": True,
                    "data": {"denied": True, "action": "click"},
                }
            )
        return json.dumps(
            {
                "id": command["id"],
                "success": True,
                "data": {
                    "confirmation_required": True,
                    "confirmation_id": command["id"],
                    "action": command["action"],
                },
            }
        )


class ConfirmedCookieNative:
    def __init__(self) -> None:
        self.commands: list[dict[str, Any]] = []
        self.pending_id: str | None = None

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        self.commands.append(command)
        if command["action"] == "cookies_get":
            self.pending_id = command["id"]
            return json.dumps(
                {
                    "id": command["id"],
                    "success": True,
                    "data": {
                        "confirmation_required": True,
                        "confirmation_id": command["id"],
                        "action": "cookies_get",
                    },
                }
            )
        if command["action"] == "confirm":
            assert command["confirmation_id"] == self.pending_id
            return json.dumps(
                {
                    "id": command["id"],
                    "success": True,
                    "data": {
                        "confirmed": True,
                        "action": "cookies_get",
                        "result": {
                            "id": "native-confirmed",
                            "success": True,
                            "data": {
                                "cookies": [
                                    {"name": "kept", "value": "1", "domain": ".example.com"},
                                    {
                                        "name": "dropped",
                                        "value": "1",
                                        "domain": "evil.example",
                                    },
                                ]
                            },
                        },
                    },
                }
            )
        if command["action"] in LIFECYCLE_CLOSE_ACTIONS:
            return json.dumps({"id": command["id"], "success": True, "data": {}})
        return json.dumps({"id": command["id"], "success": True, "data": {}})


class ConfirmingActionNative:
    def __init__(self, confirmed_action: str, result_data: Mapping[str, Any] | None = None) -> None:
        self.confirmed_action = confirmed_action
        self.result_data = dict(result_data or {})
        self.commands: list[dict[str, Any]] = []
        self.pending_id: str | None = None
        self.confirmed = False

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        self.commands.append(command)
        action = command["action"]
        if action == "confirm":
            if command.get("confirmation_id") != self.pending_id:
                return json.dumps(
                    {
                        "id": command["id"],
                        "success": False,
                        "error": "confirmation_id does not match pending confirmation",
                    }
                )
            self.pending_id = None
            response = {
                "id": command["id"],
                "success": True,
                "data": {
                    "confirmed": True,
                    "action": self.confirmed_action,
                    "result": {
                        "id": "native-confirmed",
                        "success": True,
                        "data": dict(self.result_data),
                    },
                },
            }
            self.confirmed = True
            return json.dumps(response)
        if action in LIFECYCLE_CLOSE_ACTIONS:
            return json.dumps({"id": command["id"], "success": True, "data": {}})
        if action == "launch":
            return json.dumps({"id": command["id"], "success": True, "data": {"launched": True}})
        if action == self.confirmed_action:
            self.pending_id = command["id"]
            return json.dumps(
                {
                    "id": command["id"],
                    "success": True,
                    "data": {
                        "confirmation_required": True,
                        "confirmation_id": command["id"],
                        "action": action,
                    },
                }
            )
        return json.dumps({"id": command["id"], "success": True, "data": {"echo": command}})


class FailingConfirmationNative:
    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        if command["action"] in LIFECYCLE_CLOSE_ACTIONS:
            return json.dumps({"id": command["id"], "success": True, "data": {}})
        if command["action"] == "confirm":
            return json.dumps(
                {
                    "id": command["id"],
                    "success": True,
                    "data": {
                        "confirmed": True,
                        "action": "click",
                        "result": {
                            "id": "native1",
                            "success": False,
                            "error": "confirmed click failed",
                        },
                    },
                }
            )
        return json.dumps(
            {
                "id": command["id"],
                "success": True,
                "data": {
                    "confirmation_required": True,
                    "confirmation_id": command["id"],
                    "action": command["action"],
                },
            }
        )


class StatefulConfirmationNative:
    def __init__(self, *, fail_confirm_before_consuming: bool = False) -> None:
        self.commands: list[dict[str, Any]] = []
        self.pending_id: str | None = None
        self.fail_confirm_before_consuming = fail_confirm_before_consuming

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        self.commands.append(command)
        action = command["action"]
        if action in LIFECYCLE_CLOSE_ACTIONS:
            return json.dumps({"id": command["id"], "success": True, "data": {}})
        if action in {"confirm", "deny"}:
            confirmation_id = command.get("confirmation_id")
            if self.pending_id is None:
                return json.dumps(
                    {
                        "id": command["id"],
                        "success": False,
                        "error": "No pending confirmation",
                    }
                )
            if confirmation_id != self.pending_id:
                return json.dumps(
                    {
                        "id": command["id"],
                        "success": False,
                        "error": "confirmation_id does not match pending confirmation",
                    }
                )
            if action == "confirm" and self.fail_confirm_before_consuming:
                self.fail_confirm_before_consuming = False
                return json.dumps(
                    {
                        "id": command["id"],
                        "success": False,
                        "error": "policy denied before replay",
                    }
                )
            self.pending_id = None
            if action == "deny":
                return json.dumps(
                    {
                        "id": command["id"],
                        "success": True,
                        "data": {"denied": True, "action": "click"},
                    }
                )
            return json.dumps(
                {
                    "id": command["id"],
                    "success": True,
                    "data": {
                        "confirmed": True,
                        "action": "click",
                        "result": {
                            "id": "native1",
                            "success": True,
                            "data": {"clicked": "#danger"},
                        },
                    },
                }
            )

        self.pending_id = command["id"]
        return json.dumps(
            {
                "id": command["id"],
                "success": True,
                "data": {
                    "confirmation_required": True,
                    "confirmation_id": command["id"],
                    "action": action,
                },
            }
        )


class RawValueNative:
    def __init__(self, value: Any) -> None:
        self.value = value
        self.commands: list[dict[str, Any]] = []

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        self.commands.append(command)
        if command["action"] in LIFECYCLE_CLOSE_ACTIONS:
            return json.dumps({"id": command["id"], "success": True, "data": {}})
        return json.dumps({"id": command["id"], "success": True, "data": self.value})


class AgentNative:
    def __init__(self) -> None:
        self.commands: list[dict[str, Any]] = []

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        self.commands.append(command)
        data: Mapping[str, Any]
        match command["action"]:
            case "snapshot":
                data = {
                    "snapshot": '@e1 [button] "Submit"\n@e2 [input] "Email"',
                    "origin": "https://example.com",
                    "refs": {
                        "e1": {"role": "button", "name": "Submit", "nth": 0},
                        "e2": {"role": "textbox", "name": "Email", "nth": 0},
                    },
                }
            case "addinitscript":
                data = {"identifier": "init-1"}
            case "diff_snapshot":
                data = {
                    "diff": "+ changed",
                    "additions": 1,
                    "removals": 0,
                    "unchanged": 1,
                    "changed": True,
                }
            case "download" | "waitfordownload" | "pdf":
                data = {"path": command.get("path", "artifact.bin")}
            case _:
                data = {"echo": command}
        return json.dumps({"id": command["id"], "success": True, "data": data})


class TransitionSnapshotNative:
    def __init__(self) -> None:
        self.commands: list[dict[str, Any]] = []
        self.snapshot_count = 0

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        self.commands.append(command)
        if command["action"] == "snapshot":
            self.snapshot_count += 1
            if self.snapshot_count == 1:
                data = {
                    "snapshot": '@e1 [button] "Submit"\n@e2 [input] "Email"',
                    "origin": "https://example.com/form",
                    "refs": {
                        "e1": {"role": "button", "name": "Submit"},
                        "e2": {"role": "textbox", "name": "Email"},
                    },
                }
            else:
                data = {
                    "snapshot": '@e3 [button] "Continue"\n@e4 [text] "Saved"',
                    "origin": "https://example.com/done",
                    "refs": {
                        "e3": {"role": "button", "name": "Continue"},
                        "e4": {"role": "text", "name": "Saved"},
                    },
                }
            return json.dumps({"id": command["id"], "success": True, "data": data})
        if command["action"] == "diff_snapshot":
            return json.dumps(
                {
                    "id": command["id"],
                    "success": True,
                    "data": {
                        "diff": '+ @e3 [button] "Continue"',
                        "additions": 1,
                        "removals": 1,
                        "unchanged": 0,
                        "changed": True,
                    },
                }
            )
        return json.dumps({"id": command["id"], "success": True, "data": {"echo": command}})


class StaleRefNative:
    def __init__(self, *, error: str = "Unknown ref: e1", code: str | None = "unknown_ref") -> None:
        self.commands: list[dict[str, Any]] = []
        self.snapshot_count = 0
        self.error = error
        self.code = code

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        self.commands.append(command)
        if command["action"] == "snapshot":
            self.snapshot_count += 1
            ref_id = "e1" if self.snapshot_count == 1 else "e2"
            return json.dumps(
                {
                    "id": command["id"],
                    "success": True,
                    "data": {
                        "snapshot": f'@{ref_id} [button] "Submit"',
                        "origin": "https://example.com",
                        "refs": {ref_id: {"role": "button", "name": "Submit"}},
                    },
                }
            )
        if command["action"] == "click" and command.get("selector") == "@e1":
            response: dict[str, Any] = {
                "id": command["id"],
                "success": False,
                "error": self.error,
            }
            if self.code is not None:
                response["code"] = self.code
            return json.dumps(response)
        return json.dumps({"id": command["id"], "success": True, "data": {"echo": command}})


class ScreenshotNative:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.commands: list[dict[str, Any]] = []

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        self.commands.append(command)
        return json.dumps(
            {
                "id": command["id"],
                "success": True,
                "data": {
                    "path": str(self.path),
                    "annotations": [
                        {
                            "ref": "e1",
                            "number": 1,
                            "role": "button",
                            "name": "Save",
                            "box": {"x": 1, "y": 2, "width": 30, "height": 12},
                        }
                    ],
                },
            }
        )


class BlockingNative:
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
        return self.response
