from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from agentbrowser.contracts.types import JSONObject

HarContentMode = Literal["all", "text", "none"]


@dataclass(frozen=True, slots=True)
class NetworkRequest:
    """One request captured by the native engine.

    `response_body` is populated by `browser.network.request(id)`. Listings
    from `browser.network.requests()` leave it `None`.
    """

    id: str
    url: str
    method: str
    resource_type: str
    timestamp: int
    headers: Mapping[str, Any]
    status: int | None = None
    response_headers: Mapping[str, Any] | None = None
    mime_type: str | None = None
    post_data: str | None = None
    response_body: str | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RouteResponse:
    """Static response returned for requests matched by `browser.network.route()`.

    `allow_origin` answers CORS preflights for the route and sends
    `Access-Control-Allow-Origin` with the mocked response.
    """

    status: int | None = None
    body: str | None = None
    content_type: str | None = None
    headers: Mapping[str, str] | None = None
    allow_origin: str | None = None

    def as_command_value(self) -> JSONObject:
        return {
            key: value
            for key, value in {
                "status": self.status,
                "body": self.body,
                "contentType": self.content_type,
                "headers": dict(self.headers) if self.headers is not None else None,
                "allowOrigin": self.allow_origin,
            }.items()
            if value is not None
        }
