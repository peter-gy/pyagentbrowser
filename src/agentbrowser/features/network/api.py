from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from agentbrowser.contracts.decode import none, required_path
from agentbrowser.contracts.protocol import optional, path_value
from agentbrowser.execution.commands import AsyncExecutor, Command, Executor
from agentbrowser.features.network.codec import (
    network_request_from_data,
    network_requests_from_data,
)
from agentbrowser.features.network.models import HarContentMode, NetworkRequest, RouteResponse
from agentbrowser.features.network.params import har_start_params, requests_params, route_params


@dataclass(frozen=True, slots=True)
class Network:
    """Request routing, capture, HAR, and credential helpers."""

    executor: Executor

    def route(
        self,
        url: str,
        response: RouteResponse | None = None,
        *,
        abort: bool = False,
        resource_types: Sequence[str] | None = None,
    ) -> None:
        """Answer requests matching `url` with `response`, or abort them with `abort=True`."""
        self.executor.execute(
            Command(
                "route",
                route_params(url, response, abort=abort, resource_types=resource_types),
                decode=none,
            )
        )

    def unroute(self, url: str | None = None) -> None:
        """Remove the route for `url`, or every route when `url` is omitted."""
        self.executor.execute(Command("unroute", {"url": optional(url)}, decode=none))

    def requests(
        self,
        *,
        url_pattern: str | None = None,
        resource_type: str | None = None,
        method: str | None = None,
        status: str | int | None = None,
    ) -> tuple[NetworkRequest, ...]:
        """Return captured requests, optionally filtered."""
        return self.executor.execute(
            Command(
                "requests",
                requests_params(
                    url_pattern=url_pattern,
                    resource_type=resource_type,
                    method=method,
                    status=status,
                ),
                decode=network_requests_from_data,
            )
        )

    def clear_requests(self) -> None:
        """Discard every captured request."""
        self.executor.execute(Command("requests", {"clear": True}, decode=none))

    def request(self, request_id: str) -> NetworkRequest:
        """Return one captured request with its response body."""
        return self.executor.execute(
            Command("request_detail", {"requestId": request_id}, decode=network_request_from_data)
        )

    def har_start(self, *, content: HarContentMode = "text") -> None:
        """Start HAR capture with the selected response-body content."""
        self.executor.execute(Command("har_start", har_start_params(content), decode=none))

    def har_stop(self, path: str | Path | None = None) -> Path:
        """Stop HAR capture and return the written file path."""
        return self.executor.execute(
            Command(
                "har_stop",
                {"path": optional(path_value(path))},
                decode=lambda data: required_path(data, action="har_stop"),
            )
        )

    def credentials(self, username: str, password: str) -> None:
        """Set HTTP authentication credentials."""
        self.executor.execute(
            Command("credentials", {"username": username, "password": password}, decode=none)
        )


@dataclass(frozen=True, slots=True)
class AsyncNetwork:
    """Async request routing, capture, HAR, and credential helpers."""

    executor: AsyncExecutor

    async def route(
        self,
        url: str,
        response: RouteResponse | None = None,
        *,
        abort: bool = False,
        resource_types: Sequence[str] | None = None,
    ) -> None:
        """Answer requests matching `url` with `response`, or abort them with `abort=True`."""
        await self.executor.execute(
            Command(
                "route",
                route_params(url, response, abort=abort, resource_types=resource_types),
                decode=none,
            )
        )

    async def unroute(self, url: str | None = None) -> None:
        """Remove the route for `url`, or every route when `url` is omitted."""
        await self.executor.execute(Command("unroute", {"url": optional(url)}, decode=none))

    async def requests(
        self,
        *,
        url_pattern: str | None = None,
        resource_type: str | None = None,
        method: str | None = None,
        status: str | int | None = None,
    ) -> tuple[NetworkRequest, ...]:
        """Return captured requests, optionally filtered."""
        return await self.executor.execute(
            Command(
                "requests",
                requests_params(
                    url_pattern=url_pattern,
                    resource_type=resource_type,
                    method=method,
                    status=status,
                ),
                decode=network_requests_from_data,
            )
        )

    async def clear_requests(self) -> None:
        """Discard every captured request."""
        await self.executor.execute(Command("requests", {"clear": True}, decode=none))

    async def request(self, request_id: str) -> NetworkRequest:
        """Return one captured request with its response body."""
        return await self.executor.execute(
            Command("request_detail", {"requestId": request_id}, decode=network_request_from_data)
        )

    async def har_start(self, *, content: HarContentMode = "text") -> None:
        """Start HAR capture with the selected response-body content."""
        await self.executor.execute(Command("har_start", har_start_params(content), decode=none))

    async def har_stop(self, path: str | Path | None = None) -> Path:
        """Stop HAR capture and return the written file path."""
        return await self.executor.execute(
            Command(
                "har_stop",
                {"path": optional(path_value(path))},
                decode=lambda data: required_path(data, action="har_stop"),
            )
        )

    async def credentials(self, username: str, password: str) -> None:
        """Set HTTP authentication credentials."""
        await self.executor.execute(
            Command("credentials", {"username": username, "password": password}, decode=none)
        )
