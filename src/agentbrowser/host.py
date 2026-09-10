"""Contracts shared by browser automation hosts and code-mode agents."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, TypeAlias, runtime_checkable

from agentbrowser.launch import CDPTarget


@dataclass(frozen=True, slots=True)
class OpenTarget:
    """Application URL to open in a new automation browser."""

    url: str

    def __post_init__(self) -> None:
        if not isinstance(self.url, str) or not self.url.strip():
            raise ValueError("OpenTarget.url must be a non-empty string")


@dataclass(frozen=True, slots=True)
class AttachedTarget:
    """Existing browser connection and exact page target to attach."""

    connection: CDPTarget
    page_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.connection, CDPTarget):
            raise TypeError("AttachedTarget.connection must be CDPTarget")
        if not isinstance(self.page_id, str) or not self.page_id.strip():
            raise ValueError("AttachedTarget.page_id must be a non-empty string")


BrowserTarget: TypeAlias = OpenTarget | AttachedTarget


@dataclass(frozen=True, slots=True)
class ImageContent:
    """Image bytes prepared for delivery through an agent host."""

    data: bytes
    media_type: str
    source: Path | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.data, bytes) or not self.data:
            raise ValueError("ImageContent.data must contain image bytes")
        if not self.media_type.startswith("image/"):
            raise ValueError("ImageContent.media_type must be an image MIME type")


@dataclass(frozen=True, slots=True)
class ImageDelivery:
    """Host acknowledgement for image-content delivery."""

    status: Literal["accepted", "queued", "submitted"]
    id: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Execution limits exposed by the active agent host."""

    timeout_ms: int | None = None
    cancellation: bool = False
    managed_tasks: bool = False

    def __post_init__(self) -> None:
        if self.timeout_ms is not None and self.timeout_ms < 0:
            raise ValueError("ExecutionContext.timeout_ms must be non-negative")


@runtime_checkable
class AgentHost(Protocol):
    """Host capabilities consumed by a code-mode browser workflow."""

    def current_target(self) -> BrowserTarget:
        """Return the application target associated with this agent call."""

    def emit_image(self, content: ImageContent) -> ImageDelivery:
        """Deliver image content through the host's model-facing channel."""

    def execution_context(self) -> ExecutionContext:
        """Return the limits of the current tool execution."""
