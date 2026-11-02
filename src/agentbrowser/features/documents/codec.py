from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agentbrowser.contracts.decode import (
    optional_int_field,
    required_bool,
    required_string,
)
from agentbrowser.features.documents.read import ReadResult


def read_result_from_data(data: Mapping[str, Any]) -> ReadResult:
    action = "read"
    return ReadResult(
        url=required_string(data, "url", action=action),
        final_url=required_string(data, "finalUrl", action=action),
        status=optional_int_field(data, "status", action=action),
        content_type=required_string(data, "contentType", action=action),
        source=required_string(data, "source", action=action),
        truncated=required_bool(data, "truncated", action=action),
        content=required_string(data, "content", action=action),
        raw=data,
    )
