from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from agentbrowser.features.documents.models import LoadState


@dataclass(frozen=True, slots=True)
class Wait:
    """Condition applied after an agent action."""

    kind: Literal["text", "url", "load", "all"]
    value: str | None = None
    timeout_ms: int | None = None
    conditions: tuple[Wait, ...] = ()

    def __post_init__(self) -> None:
        if self.timeout_ms is not None and self.timeout_ms < 0:
            raise ValueError("timeout_ms must be non-negative")
        if self.kind == "all":
            if not self.conditions:
                raise ValueError("Wait.all requires at least one condition")
            if self.value is not None:
                raise ValueError("Wait.all does not accept a value")
        elif self.value is None or self.conditions:
            raise ValueError(f"Wait.{self.kind} requires one value")

    @classmethod
    def text(cls, text: str, *, timeout_ms: int | None = None) -> Wait:
        """Wait for page text after an action."""
        return cls("text", text, timeout_ms)

    @classmethod
    def url(cls, url: str, *, timeout_ms: int | None = None) -> Wait:
        """Wait for a URL pattern after an action."""
        return cls("url", url, timeout_ms)

    @classmethod
    def loaded(
        cls,
        state: LoadState = "load",
        *,
        timeout_ms: int | None = None,
    ) -> Wait:
        """Wait for a page load state after an action."""
        return cls("load", state, timeout_ms)

    @classmethod
    def all(cls, *conditions: Wait, timeout_ms: int | None = None) -> Wait:
        """Apply several wait conditions within an optional shared timeout."""
        return cls("all", timeout_ms=timeout_ms, conditions=tuple(conditions))
