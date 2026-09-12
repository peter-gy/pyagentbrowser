from __future__ import annotations

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


def nullable_string(
    data: Mapping[str, Any],
    field: str,
    *,
    action: str,
) -> str | None:
    if field not in data:
        raise NativeParseError(f"{action} field '{field}' is required")
    return optional_string(data, field, action=action)


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


def first_mapping(data: Mapping[str, Any], *keys: str) -> Mapping[str, Any] | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, Mapping):
            return value
    return None


def require_keys(raw: Mapping[str, Any], model: str, *keys: str) -> None:
    missing = [key for key in keys if raw.get(key) is None]
    if missing:
        raise NativeParseError(f"{model} missing required native field: {', '.join(missing)}")


def first_present(
    raw: Mapping[str, Any],
    *keys: str,
    model: str,
    field: str,
) -> Any:
    for key in keys:
        value = raw.get(key)
        if value is not None:
            return value
    raise NativeParseError(f"{model} missing required native field: {field}")


def optional_flag(data: Mapping[str, Any], field: str, *, model: str) -> bool:
    value = data.get(field, False)
    if not isinstance(value, bool):
        raise NativeParseError(f"{model} field '{field}' must be a boolean")
    return value


def optional_bool(value: Any) -> bool | None:
    return bool(value) if value is not None else None


def optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def float_value(value: Any) -> float:
    return float(value if value is not None else 0)
