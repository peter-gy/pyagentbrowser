from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from agentbrowser.contracts.connection import normalize_url
from agentbrowser.contracts.protocol import optional
from agentbrowser.execution.commands import AsyncExecutor, Command, Executor
from agentbrowser.features.diagnostics.codec import (
    accessibility_audit_from_data,
    console_messages_from_data,
)
from agentbrowser.features.diagnostics.models import AccessibilityAudit, ConsoleMessage
from agentbrowser.features.diagnostics.params import accessibility_audit_params


@dataclass(frozen=True, slots=True)
class Diagnostics:
    """Accessibility, console, error, vitals, and framework diagnostics."""

    executor: Executor

    def console(self, *, clear: bool = False) -> tuple[ConsoleMessage, ...]:
        """Return captured console messages."""
        return self.executor.execute(
            Command("console", {"clear": clear}, decode=console_messages_from_data)
        )

    def errors(self) -> Mapping[str, Any]:
        """Return captured page errors."""
        return self.executor.execute(Command("errors", {}))

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

    async def console(self, *, clear: bool = False) -> tuple[ConsoleMessage, ...]:
        """Return captured console messages."""
        return await self.executor.execute(
            Command("console", {"clear": clear}, decode=console_messages_from_data)
        )

    async def errors(self) -> Mapping[str, Any]:
        """Return captured page errors."""
        return await self.executor.execute(Command("errors", {}))

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
