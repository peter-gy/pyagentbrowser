from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agentbrowser.contracts.errors import NativeParseError


def _string_field(data: Mapping[str, Any], field: str, *, action: str) -> str:
    value = data.get(field)
    if not isinstance(value, str):
        raise NativeParseError(f"{action} field '{field}' must be a string")
    return value


def _bool_field(data: Mapping[str, Any], field: str, *, action: str) -> bool:
    value = data.get(field)
    if not isinstance(value, bool):
        raise NativeParseError(f"{action} field '{field}' must be a boolean")
    return value


def _optional_attribute(data: Mapping[str, Any]) -> str | None:
    value = data.get("value")
    if value is None:
        return None
    if not isinstance(value, str):
        raise NativeParseError("getattribute field 'value' must be a string or null")
    return value
