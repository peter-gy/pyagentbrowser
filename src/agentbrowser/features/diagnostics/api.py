from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from agentbrowser.contracts.connection import normalize_url
from agentbrowser.contracts.decode import none
from agentbrowser.contracts.protocol import optional
from agentbrowser.execution.commands import AsyncExecutor, Command, Executor
from agentbrowser.features.diagnostics.codec import (
    accessibility_audit_from_data,
    console_messages_from_data,
    page_errors_from_data,
)
from agentbrowser.features.diagnostics.models import AccessibilityAudit, ConsoleMessage, PageError
from agentbrowser.features.diagnostics.params import accessibility_audit_params


@dataclass(frozen=True, slots=True)
class Diagnostics:
    """Accessibility, console, error, vitals, and framework diagnostics."""

    executor: Executor

    def console(self) -> tuple[ConsoleMessage, ...]:
        """Return captured console messages."""
        return self.executor.execute(Command("console", {}, decode=console_messages_from_data))

    def clear_console(self) -> None:
        """Discard every captured console message."""
        self.executor.execute(Command("console", {"clear": True}, decode=none))

    def errors(self) -> tuple[PageError, ...]:
        """Return captured uncaught page exceptions."""
        return self.executor.execute(Command("errors", {}, decode=page_errors_from_data))

    def clear_errors(self) -> None:
        """Discard every captured page error."""
        self.executor.execute(Command("errors", {"clear": True}, decode=none))

    def vitals(self) -> Mapping[str, Any]:
        """Return page vitals when supported by the native engine."""
        return self.executor.execute(Command("vitals", {}))

    def accessibility(
        self,
        url: str | None = None,
        *,
        tags: Sequence[str] = (),
        selector: str | None = None,
    ) -> AccessibilityAudit:
        """Run an axe-core accessibility audit for a URL or the active page."""
        normalized_url = normalize_url(url) if url is not None else None
        return self.executor.execute(
            Command(
                "a11y",
                {**accessibility_audit_params(normalized_url, tags=tags, selector=selector)},
                decode=accessibility_audit_from_data,
            )
        )

    def react_tree(self, *, selector: str | None = None) -> Mapping[str, Any]:
        """Return React tree diagnostics, optionally scoped by selector."""
        return self.executor.execute(Command("react_tree", {"selector": optional(selector)}))


@dataclass(frozen=True, slots=True)
class AsyncDiagnostics:
    """Async accessibility, console, error, vitals, and framework diagnostics."""

    executor: AsyncExecutor

    async def console(self) -> tuple[ConsoleMessage, ...]:
        """Return captured console messages."""
        return await self.executor.execute(
            Command("console", {}, decode=console_messages_from_data)
        )

    async def clear_console(self) -> None:
        """Discard every captured console message."""
        await self.executor.execute(Command("console", {"clear": True}, decode=none))

    async def errors(self) -> tuple[PageError, ...]:
        """Return captured uncaught page exceptions."""
        return await self.executor.execute(Command("errors", {}, decode=page_errors_from_data))

    async def clear_errors(self) -> None:
        """Discard every captured page error."""
        await self.executor.execute(Command("errors", {"clear": True}, decode=none))

    async def vitals(self) -> Mapping[str, Any]:
        """Return page vitals when supported by the native engine."""
        return await self.executor.execute(Command("vitals", {}))

    async def accessibility(
        self,
        url: str | None = None,
        *,
        tags: Sequence[str] = (),
        selector: str | None = None,
    ) -> AccessibilityAudit:
        """Run an axe-core accessibility audit for a URL or the active page."""
        normalized_url = normalize_url(url) if url is not None else None
        return await self.executor.execute(
            Command(
                "a11y",
                {**accessibility_audit_params(normalized_url, tags=tags, selector=selector)},
                decode=accessibility_audit_from_data,
            )
        )

    async def react_tree(self, *, selector: str | None = None) -> Mapping[str, Any]:
        """Return React tree diagnostics, optionally scoped by selector."""
        return await self.executor.execute(Command("react_tree", {"selector": optional(selector)}))
