from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from agentbrowser.contracts.types import JSONObject

HarContentMode = Literal["all", "text", "none"]


@dataclass(frozen=True, slots=True)
class NetworkRequest:
    """Captured network request summary."""

    id: str
    url: str
    method: str = ""
    resource_type: str = ""
    status: int | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RequestDetail:
    """Detailed request and response metadata."""

    id: str
    url: str = ""
    method: str = ""
    status: int | None = None
    request_headers: Mapping[str, Any] = field(default_factory=dict)
    response_headers: Mapping[str, Any] = field(default_factory=dict)
    body: str | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RouteResponse:
    """Static route response used by `browser.network.route()`."""

    status: int | None = None
    body: str | None = None
    content_type: str | None = None
    headers: Mapping[str, str] | None = None

    def as_command_value(self) -> JSONObject:
        return {
            key: value
            for key, value in {
                "status": self.status,
                "body": self.body,
                "contentType": self.content_type,
                "headers": dict(self.headers) if self.headers is not None else None,
            }.items()
            if value is not None
        }
