from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agentbrowser.contracts.decode import required_path
from agentbrowser.contracts.protocol import optional, path_value
from agentbrowser.execution.commands import AsyncExecutor, Command, Executor


@dataclass(frozen=True, slots=True)
class Downloads:
    """Download triggering and waiting helpers."""

    executor: Executor

    def download(self, selector: str, path: str | Path) -> Path:
        """Click a selector that starts a download and return the path."""
        return self.executor.execute(
            Command(
                "download",
                {"selector": selector, "path": path_value(path)},
                decode=lambda data: required_path(data, action="download"),
            )
        )

    def wait(self, path: str | Path | None = None, *, timeout_ms: int | None = None) -> Path:
        """Wait for the next download and return the path."""
        return self.executor.execute(
            Command(
                "waitfordownload",
                {"path": optional(path_value(path)), "timeout": optional(timeout_ms)},
                decode=lambda data: required_path(data, action="waitfordownload"),
            )
        )


@dataclass(frozen=True, slots=True)
class AsyncDownloads:
    """Async download triggering and waiting helpers."""

    executor: AsyncExecutor

    async def download(self, selector: str, path: str | Path) -> Path:
        """Click a selector that starts a download and return the path."""
        return await self.executor.execute(
            Command(
                "download",
                {"selector": selector, "path": path_value(path)},
                decode=lambda data: required_path(data, action="download"),
            )
        )

    async def wait(self, path: str | Path | None = None, *, timeout_ms: int | None = None) -> Path:
        """Wait for the next download and return the path."""
        return await self.executor.execute(
            Command(
                "waitfordownload",
                {"path": optional(path_value(path)), "timeout": optional(timeout_ms)},
                decode=lambda data: required_path(data, action="waitfordownload"),
            )
        )
