from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agentbrowser.contracts.protocol import OMIT, optional


def _webmcp_identifier(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value


def _webmcp_timeout(timeout_ms: int | None) -> int | Any:
    if timeout_ms is None:
        return OMIT
    if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int):
        raise TypeError("timeout_ms must be an integer")
    if timeout_ms < 0:
        raise ValueError("timeout_ms must be non-negative")
    return timeout_ms


def webmcp_invoke_params(
    tool: str,
    params: Mapping[str, Any] | None = None,
    *,
    frame_id: str | None = None,
    detach: bool = False,
    timeout_ms: int | None = None,
) -> dict[str, Any]:
    if params is not None and not isinstance(params, Mapping):
        raise TypeError("params must be a mapping")
    return {
        "tool": _webmcp_identifier(tool, "tool"),
        "params": dict(params or {}),
        "frameId": optional(
            _webmcp_identifier(frame_id, "frame_id") if frame_id is not None else None
        ),
        "detach": detach,
        "timeout": _webmcp_timeout(timeout_ms),
    }


def webmcp_result_params(
    invocation_id: str,
    *,
    timeout_ms: int | None = None,
) -> dict[str, Any]:
    return {
        "invocationId": _webmcp_identifier(invocation_id, "invocation_id"),
        "timeout": _webmcp_timeout(timeout_ms),
    }


def webmcp_cancel_params(invocation_id: str) -> dict[str, str]:
    return {"invocationId": _webmcp_identifier(invocation_id, "invocation_id")}
