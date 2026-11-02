from __future__ import annotations

import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from agentbrowser.contracts.errors import NativeParseError


def required_string(data: Mapping[str, Any], field: str, *, action: str) -> str:
    value = data.get(field)
    if not isinstance(value, str):
        raise NativeParseError(f"{action} field '{field}' must be a string")
    return value


def required_path(data: Mapping[str, Any], *, action: str) -> Path:
    return Path(required_string(data, "path", action=action))


def none(_data: Mapping[str, Any]) -> None:
    return None


_UNSERIALIZABLE_NUMBERS = {
    "NaN": math.nan,
    "Infinity": math.inf,
    "-Infinity": -math.inf,
    "-0": -0.0,
}


def unserializable_value(token: str) -> Any:
    """Return the Python value for a JavaScript result that JSON cannot carry."""
    if token == "undefined":
        return None
    if token in _UNSERIALIZABLE_NUMBERS:
        return _UNSERIALIZABLE_NUMBERS[token]
    if token.endswith("n"):
        try:
            return int(token[:-1])
        except ValueError:
            pass
    raise NativeParseError(f"unknown unserializable JavaScript value {token!r}")


def evaluation_result(data: Mapping[str, Any]) -> Any:
    """Decode the native `evaluate` result, including non-JSON JavaScript values."""
    token = data.get("unserializable")
    if token is None:
        return data.get("result")
    if not isinstance(token, str):
        raise NativeParseError("evaluate field 'unserializable' must be a string")
    return unserializable_value(token)


def optional_string(
    data: Mapping[str, Any],
    field: str,
    *,
    action: str,
) -> str | None:
    value = data.get(field)
    if value is not None and not isinstance(value, str):
        raise NativeParseError(f"{action} field '{field}' must be a string or null")
    return value


def optional_int_field(
    data: Mapping[str, Any],
    field: str,
    *,
    action: str,
) -> int | None:
    value = data.get(field)
    if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
        raise NativeParseError(f"{action} field '{field}' must be an integer or null")
    return value


def nullable_string(
    data: Mapping[str, Any],
    field: str,
    *,
    action: str,
) -> str | None:
    if field not in data:
        raise NativeParseError(f"{action} field '{field}' is required")
    return optional_string(data, field, action=action)


def string_tuple(data: Mapping[str, Any], field: str, *, action: str) -> tuple[str, ...]:
    value = data.get(field)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise NativeParseError(f"{action} field '{field}' must be an array of strings")
    return tuple(value)


def required_bool(data: Mapping[str, Any], field: str, *, action: str) -> bool:
    value = data.get(field)
    if not isinstance(value, bool):
        raise NativeParseError(f"{action} field '{field}' must be a boolean")
    return value


def required_int(data: Mapping[str, Any], field: str, *, action: str) -> int:
    value = data.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise NativeParseError(f"{action} field '{field}' must be an integer")
    return value


def nullable_int(
    data: Mapping[str, Any],
    field: str,
    *,
    action: str,
) -> int | None:
    if field not in data:
        raise NativeParseError(f"{action} field '{field}' is required")
    value = data[field]
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise NativeParseError(f"{action} field '{field}' must be an integer or null")
    return value


def optional_mapping(data: Mapping[str, Any], field: str, *, action: str) -> Mapping[str, Any]:
    value = data.get(field, {})
    if not isinstance(value, Mapping):
        raise NativeParseError(f"{action} field '{field}' must be an object")
    return value


def optional_flag(data: Mapping[str, Any], field: str, *, model: str) -> bool:
    value = data.get(field, False)
    if not isinstance(value, bool):
        raise NativeParseError(f"{model} field '{field}' must be a boolean")
    return value
