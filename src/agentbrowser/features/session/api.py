from __future__ import annotations

from dataclasses import dataclass

from agentbrowser.execution.commands import AsyncExecutor, Command, Executor
from agentbrowser.features.session.codec import session_status_from_data
from agentbrowser.features.session.models import SessionStatus


@dataclass(frozen=True, slots=True)
class Session:
    """Native session and restore lifecycle."""

    executor: Executor

    def status(self) -> SessionStatus:
        """Return current session, browser, restore, and save state."""
        return self.executor.execute(Command("session_info", {}, decode=session_status_from_data))


@dataclass(frozen=True, slots=True)
class AsyncSession:
    """Async native session and restore lifecycle."""

    executor: AsyncExecutor

    async def status(self) -> SessionStatus:
        """Return current session, browser, restore, and save state."""
        return await self.executor.execute(
            Command("session_info", {}, decode=session_status_from_data)
        )
