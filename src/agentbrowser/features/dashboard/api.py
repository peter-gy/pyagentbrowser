from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from agentbrowser.execution.commands import AsyncExecutor, Command, Executor


@dataclass(frozen=True, slots=True)
class Dashboard:
    """Dashboard observability lifecycle for a `Browser`."""

    executor: Executor

    def status(self) -> Mapping[str, Any]:
        """Return the configured dashboard stream status."""
        return self.executor.execute(Command("stream_status", {}))

    def stop(self) -> None:
        """Stop dashboard streaming for this browser."""
        self.executor.execute(Command("stream_disable", {}, decode=lambda _data: None))


@dataclass(frozen=True, slots=True)
class AsyncDashboard:
    """Dashboard observability lifecycle for an `AsyncBrowser`."""

    executor: AsyncExecutor

    async def status(self) -> Mapping[str, Any]:
        """Return the configured dashboard stream status."""
        return await self.executor.execute(Command("stream_status", {}))

    async def stop(self) -> None:
        """Stop dashboard streaming for this browser."""
        await self.executor.execute(Command("stream_disable", {}, decode=lambda _data: None))
