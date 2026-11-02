from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from agentbrowser.contracts.protocol import OMIT, optional
from agentbrowser.features.network.models import HarContentMode, RouteResponse

HAR_CONTENT_MODES = frozenset({"all", "text", "none"})


def har_start_params(content: HarContentMode = "text") -> dict[str, HarContentMode]:
    if not isinstance(content, str) or content not in HAR_CONTENT_MODES:
        raise ValueError("content must be 'all', 'text', or 'none'")
    return {"content": content}


def route_params(
    url: str,
    response: RouteResponse | None,
    *,
    abort: bool,
    resource_types: Sequence[str] | None,
) -> dict[str, Any]:
    if abort and response is not None:
        raise ValueError("route takes either abort=True or a response, not both")
    if response is not None and not isinstance(response, RouteResponse):
        raise TypeError("route response must be a RouteResponse")
    if isinstance(resource_types, str):
        raise TypeError("resource_types must be a sequence of resource type names")
    return {
        "url": url,
        "abort": abort,
        "response": response.as_command_value() if response is not None else OMIT,
        "resourceTypes": list(resource_types) if resource_types is not None else OMIT,
    }


def requests_params(
    *,
    url_pattern: str | None = None,
    resource_type: str | None = None,
    method: str | None = None,
    status: str | int | None = None,
) -> dict[str, Any]:
    return {
        "filter": optional(url_pattern),
        "type": optional(resource_type),
        "method": optional(method),
        "status": str(status) if status is not None else OMIT,
    }
