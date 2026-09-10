from __future__ import annotations

from typing import Any

from agentbrowser import (
    Browser,
)
from agentbrowser.transport.sync import NativeSession


def _browser(native: Any) -> Browser:
    return Browser(_native_session=NativeSession(native=native))


def _command_without_id(command: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in command.items() if key != "id" and not key.startswith("_")}


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


def _accessibility_audit_data() -> dict[str, Any]:
    return {
        "url": "https://example.com/",
        "axeVersion": "4.12.1",
        "counts": {
            "violations": 1,
            "incomplete": 0,
            "passes": 4,
            "inapplicable": 2,
        },
        "violations": [
            {
                "id": "image-alt",
                "impact": "critical",
                "help": "Images must have alternative text",
                "helpUrl": "https://dequeuniversity.com/rules/axe/4.12/image-alt",
                "tags": ["cat.text-alternatives", "wcag2a"],
                "nodeCount": 1,
                "nodes": [
                    {
                        "target": ["#logo", ["#shadow-root", "img"]],
                        "html": '<img id="logo">',
                        "failureSummary": "Fix the missing alternative text.",
                    }
                ],
            }
        ],
        "incomplete": [],
    }
