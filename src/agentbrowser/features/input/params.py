from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from agentbrowser.contracts.protocol import OMIT, optional, paths_value
from agentbrowser.features.input.models import MouseButton, MouseEventType


def click_params(
    selector: str,
    *,
    button: MouseButton = "left",
    click_count: int = 1,
    new_tab: bool = False,
) -> dict[str, Any]:
    return {
        "selector": selector,
        "button": button,
        "clickCount": click_count,
        "newTab": new_tab,
    }


def dispatch_params(selector: str, event: str, init: Mapping[str, Any]) -> dict[str, Any]:
    return {"selector": selector, "event": event, "eventInit": dict(init) or OMIT}


def upload_params(selector: str, files: Sequence[str | Path]) -> dict[str, Any]:
    return {"selector": selector, "files": paths_value(files)}


def keyboard_params(
    event_type: str,
    *,
    key: str | None = None,
    code: str | None = None,
    text: str | None = None,
) -> dict[str, Any]:
    return {
        "eventType": event_type,
        "key": optional(key),
        "code": optional(code),
        "text": optional(text),
    }


def wheel_params(
    delta_y: float = 100,
    *,
    delta_x: float = 0,
    x: float = 0,
    y: float = 0,
) -> dict[str, Any]:
    return {"x": x, "y": y, "deltaX": delta_x, "deltaY": delta_y}


def mouse_params(
    event_type: MouseEventType,
    *,
    x: float = 0,
    y: float = 0,
    button: str = "none",
    click_count: int = 0,
) -> dict[str, Any]:
    return {
        "eventType": event_type,
        "x": x,
        "y": y,
        "button": button,
        "clickCount": click_count,
    }
