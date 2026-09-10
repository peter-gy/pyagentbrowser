from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentbrowser.contracts.decode import none, required_path
from agentbrowser.contracts.protocol import optional, path_value
from agentbrowser.execution.commands import AsyncExecutor, Command, Executor
from agentbrowser.features.network.codec import network_requests_from_data, request_detail_from_data
from agentbrowser.features.network.models import (
    HarContentMode,
    NetworkRequest,
    RequestDetail,
    RouteResponse,
)
from agentbrowser.features.network.params import har_start_params, requests_params, route_params


@dataclass(frozen=True, slots=True)
class Network:
    """Request routing, capture, HAR, and credential helpers."""

    executor: Executor

    def route(
        self,
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
    ) -> None:
        """Register a request route."""
        self.executor.execute(
            Command(
                "route",
                {
                    **route_params(
                        url=url,
                        abort=abort,
                        response=response,
                        status=status,
                        body=body,
                        content_type=content_type,
                        headers=headers,
                        resource_type=resource_type,
                        resource_types=resource_types,
                    )
                },
                decode=none,
            )
        )

    def unroute(self, url: str | None = None) -> None:
        """Remove one route or all routes."""
        self.executor.execute(Command("unroute", {"url": optional(url)}, decode=none))

    def requests(
        self,
        *,
        clear: bool = False,
        url_pattern: str | None = None,
        resource_type: str | None = None,
        method: str | None = None,
        status: str | int | None = None,
    ) -> tuple[NetworkRequest, ...]:
        """Return captured network requests."""
        return self.executor.execute(
            Command(
                "requests",
                {
                    **requests_params(
                        clear=clear,
                        url_pattern=url_pattern,
                        resource_type=resource_type,
                        method=method,
                        status=status,
                    )
                },
                decode=network_requests_from_data,
            )
        )

    def request_detail(self, request_id: str) -> RequestDetail:
        """Return detailed request data for a captured request id."""
        return self.executor.execute(
            Command("request_detail", {"requestId": request_id}, decode=request_detail_from_data)
        )

    def har_start(self, *, content: HarContentMode = "text") -> None:
        """Start HAR capture with the selected response-body content."""
        self.executor.execute(Command("har_start", {**har_start_params(content)}, decode=none))

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
        *,
        abort: bool = False,
        response: RouteResponse | Mapping[str, Any] | None = None,
        status: int | None = None,
        body: str | None = None,
        content_type: str | None = None,
        headers: Mapping[str, str] | None = None,
        resource_type: str | None = None,
        resource_types: Sequence[str] | None = None,
    ) -> None:
        """Register a request route."""
        await self.executor.execute(
            Command(
                "route",
                {
                    **route_params(
                        url=url,
                        abort=abort,
                        response=response,
                        status=status,
                        body=body,
                        content_type=content_type,
                        headers=headers,
                        resource_type=resource_type,
                        resource_types=resource_types,
                    )
                },
                decode=none,
            )
        )

    async def unroute(self, url: str | None = None) -> None:
        """Remove one route or all routes."""
        await self.executor.execute(Command("unroute", {"url": optional(url)}, decode=none))

    async def requests(
        self,
        *,
        clear: bool = False,
        url_pattern: str | None = None,
        resource_type: str | None = None,
        method: str | None = None,
        status: str | int | None = None,
    ) -> tuple[NetworkRequest, ...]:
        """Return captured network requests."""
        return await self.executor.execute(
            Command(
                "requests",
                {
                    **requests_params(
                        clear=clear,
                        url_pattern=url_pattern,
                        resource_type=resource_type,
                        method=method,
                        status=status,
                    )
                },
                decode=network_requests_from_data,
            )
        )

    async def request_detail(self, request_id: str) -> RequestDetail:
        """Return detailed request data for a captured request id."""
        return await self.executor.execute(
            Command("request_detail", {"requestId": request_id}, decode=request_detail_from_data)
        )

    async def har_start(self, *, content: HarContentMode = "text") -> None:
        """Start HAR capture with the selected response-body content."""
        await self.executor.execute(
            Command("har_start", {**har_start_params(content)}, decode=none)
        )

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
