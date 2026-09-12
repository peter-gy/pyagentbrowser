from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from agentbrowser.contracts.decode import first_mapping, first_present, optional_int
from agentbrowser.contracts.errors import NativeParseError
from agentbrowser.features.network.models import NetworkRequest, RequestDetail


def network_requests_from_data(data: Mapping[str, Any]) -> tuple[NetworkRequest, ...]:
    raw_requests = data.get("requests")
    if not isinstance(raw_requests, list):
        raise NativeParseError("NetworkRequest collection field 'requests' must be an array")
    if any(not isinstance(item, Mapping) for item in raw_requests):
        raise NativeParseError("NetworkRequest collection entries must be objects")
    return tuple(_network_request(cast(Mapping[str, Any], item)) for item in raw_requests)


def request_detail_from_data(data: Mapping[str, Any]) -> RequestDetail:
    raw = first_mapping(data, "request", "detail") or data
    id_value = first_present(raw, "requestId", "id", model="RequestDetail", field="id")
    url_value = first_present(raw, "url", model="RequestDetail", field="url")
    request_headers = raw.get("requestHeaders") or raw.get("headers") or {}
    response_headers = raw.get("responseHeaders") or {}
    return RequestDetail(
        id=str(id_value),
        url=str(url_value),
        method=str(raw.get("method", "")),
        status=optional_int(raw.get("status")),
        request_headers=dict(request_headers) if isinstance(request_headers, Mapping) else {},
        response_headers=dict(response_headers) if isinstance(response_headers, Mapping) else {},
        body=str(raw["body"]) if raw.get("body") is not None else None,
        raw=raw,
    )


def _network_request(raw: Mapping[str, Any]) -> NetworkRequest:
    id_value = first_present(raw, "requestId", "id", model="NetworkRequest", field="id")
    url_value = first_present(raw, "url", model="NetworkRequest", field="url")
    return NetworkRequest(
        id=str(id_value),
        url=str(url_value),
        method=str(raw.get("method", "")),
        resource_type=str(raw.get("type") or raw.get("resourceType") or ""),
        status=optional_int(raw.get("status")),
        raw=raw,
    )
