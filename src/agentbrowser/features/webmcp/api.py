from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from agentbrowser.execution.commands import AsyncExecutor, Command, Executor
from agentbrowser.features.webmcp.codec import webmcp_invocation_from_data, webmcp_tools_from_data
from agentbrowser.features.webmcp.models import WebMCPInvocation, WebMCPTool
from agentbrowser.features.webmcp.params import (
    webmcp_cancel_params,
    webmcp_invoke_params,
    webmcp_result_params,
)


@dataclass(frozen=True, slots=True)
class WebMCP:
    """Discover and invoke tools exposed by the active page."""

    executor: Executor

    def list(self) -> tuple[WebMCPTool, ...]:
        """Return WebMCP tools exposed by the active page and its frames."""
        return self.executor.execute(Command("webmcp_list", {}, decode=webmcp_tools_from_data))

    def invoke(
        self,
        tool: str,
        params: Mapping[str, Any] | None = None,
        *,
        frame_id: str | None = None,
        detach: bool = False,
        timeout_ms: int | None = None,
    ) -> WebMCPInvocation:
        """Invoke a page tool and return its current lifecycle state."""
        return self.executor.execute(
            Command(
                "webmcp_invoke",
                {
                    **webmcp_invoke_params(
                        tool, params, frame_id=frame_id, detach=detach, timeout_ms=timeout_ms
                    )
                },
                decode=webmcp_invocation_from_data,
            )
        )

    def result(self, invocation_id: str, *, timeout_ms: int | None = None) -> WebMCPInvocation:
        """Wait for a detached invocation and return its current state."""
        return self.executor.execute(
            Command(
                "webmcp_result",
                {**webmcp_result_params(invocation_id, timeout_ms=timeout_ms)},
                decode=webmcp_invocation_from_data,
            )
        )

    def cancel(self, invocation_id: str) -> WebMCPInvocation:
        """Cancel an active invocation and return its terminal state."""
        return self.executor.execute(
            Command(
                "webmcp_cancel",
                {**webmcp_cancel_params(invocation_id)},
                decode=webmcp_invocation_from_data,
            )
        )


@dataclass(frozen=True, slots=True)
class AsyncWebMCP:
    """Async discovery and invocation for tools exposed by the active page."""

    executor: AsyncExecutor

    async def list(self) -> tuple[WebMCPTool, ...]:
        """Return WebMCP tools exposed by the active page and its frames."""
        return await self.executor.execute(
            Command("webmcp_list", {}, decode=webmcp_tools_from_data)
        )

    async def invoke(
        self,
        tool: str,
        params: Mapping[str, Any] | None = None,
        *,
        frame_id: str | None = None,
        detach: bool = False,
        timeout_ms: int | None = None,
    ) -> WebMCPInvocation:
        """Invoke a page tool and return its current lifecycle state."""
        return await self.executor.execute(
            Command(
                "webmcp_invoke",
                {
                    **webmcp_invoke_params(
                        tool, params, frame_id=frame_id, detach=detach, timeout_ms=timeout_ms
                    )
                },
                decode=webmcp_invocation_from_data,
            )
        )

    async def result(
        self, invocation_id: str, *, timeout_ms: int | None = None
    ) -> WebMCPInvocation:
        """Wait for a detached invocation and return its current state."""
        return await self.executor.execute(
            Command(
                "webmcp_result",
                {**webmcp_result_params(invocation_id, timeout_ms=timeout_ms)},
                decode=webmcp_invocation_from_data,
            )
        )

    async def cancel(self, invocation_id: str) -> WebMCPInvocation:
        """Cancel an active invocation and return its terminal state."""
        return await self.executor.execute(
            Command(
                "webmcp_cancel",
                {**webmcp_cancel_params(invocation_id)},
                decode=webmcp_invocation_from_data,
            )
        )
