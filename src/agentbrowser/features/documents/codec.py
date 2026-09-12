from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agentbrowser.contracts.decode import first_mapping, float_value, optional_int, require_keys
from agentbrowser.features.documents.models import BoundingBox
from agentbrowser.features.documents.read import ReadResult


def bounding_box_from_data(data: Mapping[str, Any]) -> BoundingBox | None:
    box = first_mapping(data, "box", "boundingBox", "rect") or data
    if not any(key in box for key in ("x", "y", "width", "height")):
        return None
    require_keys(box, "BoundingBox", "x", "y", "width", "height")
    return BoundingBox(
        x=float_value(box.get("x")),
        y=float_value(box.get("y")),
        width=float_value(box.get("width")),
        height=float_value(box.get("height")),
        raw=box,
    )


def read_result_from_data(data: Mapping[str, Any]) -> ReadResult:
    require_keys(data, "ReadResult", "content")
    return ReadResult(
        url=str(data.get("url", "")),
        final_url=str(data.get("finalUrl") or data.get("final_url") or data.get("url") or ""),
        status=optional_int(data.get("status")),
        content_type=str(data.get("contentType") or data.get("content_type") or ""),
        source=str(data.get("source", "")),
        truncated=bool(data.get("truncated", False)),
        content=str(data.get("content", "")),
        raw=data,
    )
