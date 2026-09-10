from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from agentbrowser.contracts.errors import NativeParseError
from agentbrowser.features.capture.models import (
    Screenshot,
    ScreenshotAnnotation,
    ScreenshotBox,
    _normalize_image_format,
)


def screenshot_from_data(
    data: Mapping[str, Any],
    *,
    format: str = "png",
) -> Screenshot:
    path = data.get("path")
    if not isinstance(path, str):
        raise NativeParseError("Screenshot field 'path' must be a string")
    return Screenshot(
        path=Path(path),
        format=_normalize_image_format(format),
        annotations=_parse_screenshot_annotations(data.get("annotations")),
        raw=data,
    )


def _parse_screenshot_annotations(value: Any) -> tuple[ScreenshotAnnotation, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(
        annotation
        for item in value
        if isinstance(item, Mapping)
        for annotation in [_parse_screenshot_annotation(item)]
        if annotation is not None
    )


def _parse_screenshot_annotation(raw: Mapping[str, Any]) -> ScreenshotAnnotation | None:
    box_raw = raw.get("box")
    if not isinstance(box_raw, Mapping):
        return None
    return ScreenshotAnnotation(
        ref=str(raw.get("ref", "")),
        number=int(raw.get("number", 0)),
        role=str(raw.get("role", "")),
        name=str(raw["name"]) if raw.get("name") is not None else None,
        box=ScreenshotBox(
            x=int(box_raw.get("x", 0)),
            y=int(box_raw.get("y", 0)),
            width=int(box_raw.get("width", 0)),
            height=int(box_raw.get("height", 0)),
            raw=box_raw,
        ),
        raw=raw,
    )
