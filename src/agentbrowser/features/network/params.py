from __future__ import annotations

from collections.abc import Mapping, Sequence
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
    *,
    abort: bool = False,
    response: RouteResponse | Mapping[str, Any] | None = None,
    status: int | None = None,
    body: str | None = None,
    content_type: str | None = None,
    headers: Mapping[str, str] | None = None,
    resource_type: str | None = None,
    resource_types: Sequence[str] | None = None,
) -> dict[str, Any]:
    return {
        "url": url,
        "abort": abort,
        "response": optional(route_response(response, status, body, content_type, headers)),
        "resourceType": optional(resource_type),
        "resourceTypes": list(resource_types) if resource_types is not None else OMIT,
    }


def route_response(
    response: RouteResponse | Mapping[str, Any] | None,
    status: int | None,
    body: str | None,
    content_type: str | None,
    headers: Mapping[str, str] | None,
) -> Mapping[str, Any] | None:
    if isinstance(response, RouteResponse):
        return response.as_command_value()
    if response is not None:
        return dict(response)
    if status is None and body is None and content_type is None and headers is None:
        return None
    return RouteResponse(
        status=status,
        body=body,
        content_type=content_type,
        headers=headers,
    ).as_command_value()


def requests_params(
    *,
    clear: bool = False,
    url_pattern: str | None = None,
    resource_type: str | None = None,
    method: str | None = None,
    status: str | int | None = None,
) -> dict[str, Any]:
    return {
        "clear": clear,
        "filter": optional(url_pattern),
        "type": optional(resource_type),
        "method": optional(method),
        "status": str(status) if status is not None else OMIT,
    }
