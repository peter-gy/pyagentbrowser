from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from agentbrowser.contracts.decode import optional_string, required_int, required_string
from agentbrowser.contracts.errors import NativeParseError
from agentbrowser.features.network.models import NetworkRequest


def network_requests_from_data(data: Mapping[str, Any]) -> tuple[NetworkRequest, ...]:
    raw_requests = data.get("requests")
    if not isinstance(raw_requests, list):
        raise NativeParseError("requests field 'requests' must be an array")
    if any(not isinstance(item, Mapping) for item in raw_requests):
        raise NativeParseError("requests field 'requests' entries must be objects")
    return tuple(
        network_request_from_data(cast(Mapping[str, Any], item), action="requests")
        for item in raw_requests
    )


def network_request_from_data(
    data: Mapping[str, Any], *, action: str = "request_detail"
) -> NetworkRequest:
    status = data.get("status")
    if status is not None and (isinstance(status, bool) or not isinstance(status, int)):
        raise NativeParseError(f"{action} field 'status' must be an integer or absent")
    return NetworkRequest(
        id=required_string(data, "requestId", action=action),
        url=required_string(data, "url", action=action),
        method=required_string(data, "method", action=action),
        resource_type=required_string(data, "resourceType", action=action),
        timestamp=required_int(data, "timestamp", action=action),
        headers=_headers(data, "headers", action=action) or {},
        status=status,
        response_headers=_headers(data, "responseHeaders", action=action),
        mime_type=optional_string(data, "mimeType", action=action),
        post_data=optional_string(data, "postData", action=action),
        response_body=optional_string(data, "responseBody", action=action),
        raw=data,
    )


def _headers(data: Mapping[str, Any], field: str, *, action: str) -> Mapping[str, Any] | None:
    value = data.get(field)
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise NativeParseError(f"{action} field '{field}' must be an object")
    return cast(Mapping[str, Any], value)
