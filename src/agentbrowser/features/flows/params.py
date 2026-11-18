from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from agentbrowser.contracts.protocol import OMIT

_FLOW_NAME = re.compile(r"[A-Za-z0-9_-]+")


def _flow_name(name: str) -> str:
    if not isinstance(name, str):
        raise TypeError("name must be a string")
    if _FLOW_NAME.fullmatch(name) is None:
        raise ValueError(f"invalid flow name {name!r}: use letters, digits, '-' or '_'")
    return name


def _text(value: str | None, name: str, *, allow_empty: bool = False) -> str | Any:
    if value is None:
        return OMIT
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not allow_empty and not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value


def _count(value: int | None, name: str) -> int | Any:
    if value is None:
        return OMIT
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _strings(value: Mapping[str, str] | None, name: str) -> dict[str, str] | Any:
    if value is None:
        return OMIT
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise TypeError(f"{name} entry {key!r} must map a string to a string")
    return dict(value) or OMIT


def _allow_writes(allow_writes: Literal["all"] | Sequence[str]) -> str | list[str] | Any:
    if isinstance(allow_writes, str):
        if allow_writes != "all":
            raise TypeError("allow_writes must be 'all' or a sequence of write ids")
        return "all"
    ids = list(allow_writes)
    for write_id in ids:
        if not isinstance(write_id, str):
            raise TypeError("allow_writes entries must be strings")
        if not write_id.strip():
            raise ValueError("allow_writes entries must not be empty")
    return ids or OMIT


def _fields(fields: Sequence[str]) -> str | Any:
    if isinstance(fields, str):
        raise TypeError("fields must be a sequence, not a string")
    paths = list(fields)
    for path in paths:
        if not isinstance(path, str):
            raise TypeError("fields entries must be strings")
        if not path.strip():
            raise ValueError("fields entries must not be empty")
        if "," in path:
            raise ValueError(f"fields entry {path!r} must not contain a comma")
    return ",".join(paths) or OMIT


def flow_save_params(
    name: str,
    *,
    params: Mapping[str, str] | None = None,
    description: str | None = None,
    output: str | None = None,
    from_step: int | None = None,
    to_step: int | None = None,
    timeout_ms: int | None = None,
) -> dict[str, Any]:
    return {
        "name": _flow_name(name),
        "params": _strings(params, "params"),
        "description": _text(description, "description", allow_empty=True),
        "output": _text(output, "output"),
        "from": _count(from_step, "from_step"),
        "to": _count(to_step, "to_step"),
        "timeout": _count(timeout_ms, "timeout_ms"),
    }


def flow_run_params(
    name: str,
    *,
    params: Mapping[str, str] | None = None,
    origin: str | None = None,
    allow_writes: Literal["all"] | Sequence[str] = (),
    where: Mapping[str, str] | None = None,
    fields: Sequence[str] = (),
    limit: int | None = None,
    timeout_ms: int | None = None,
) -> dict[str, Any]:
    return {
        "name": _flow_name(name),
        "params": _strings(params, "params"),
        "origin": _text(origin, "origin"),
        "allowWrite": _allow_writes(allow_writes),
        "where": _strings(where, "where"),
        "fields": _fields(fields),
        "limit": _count(limit, "limit"),
        "timeout": _count(timeout_ms, "timeout_ms"),
    }


def flow_list_params(*, origin: str | None = None) -> dict[str, Any]:
    return {"origin": _text(origin, "origin")}
