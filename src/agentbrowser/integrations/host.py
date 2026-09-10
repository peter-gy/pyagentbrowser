"""Contracts shared by browser automation hosts and code-mode agents."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextvars import Token
from dataclasses import dataclass, field
from typing import Literal, Protocol, TypeAlias, cast, runtime_checkable

from agentbrowser.contracts.execution import (
    ExecutionContext,
    ExecutionProvider,
    bind_execution_provider,
    current_execution_provider,
    reset_execution_provider,
)
from agentbrowser.contracts.images import ImageContent, ImageDelivery
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

    connection: CDPTarget = field(repr=False)
    target_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.connection, CDPTarget):
            raise TypeError("AttachedTarget.connection must be CDPTarget")
        if not isinstance(self.target_id, str) or not self.target_id.strip():
            raise ValueError("AttachedTarget.target_id must be a non-empty string")


BrowserTarget: TypeAlias = OpenTarget | AttachedTarget


@dataclass(frozen=True, slots=True)
class AgentConnectionStatus:
    """Identity and ownership of one process-local agent controller."""

    name: str
    process_id: int
    ownership: Literal["owned", "attached"]
    session_id: str | None
    browser_launched: bool
    browser_closed: bool
    target_id: str | None = None
    url: str | None = None


@dataclass(frozen=True, slots=True)
class ManagedTaskStatus:
    """Observable state for one host-managed task."""

    id: str
    state: Literal["queued", "running", "completed", "failed", "cancelled"]
    progress: float | None = None
    detail: str | None = None


@runtime_checkable
class ManagedTask(Protocol):
    """Work that remains observable across agent tool calls."""

    @property
    def id(self) -> str: ...

    def status(self) -> ManagedTaskStatus: ...

    def report(
        self, progress: float | None = None, detail: str | None = None
    ) -> ManagedTaskStatus: ...

    async def result(self, *, timeout_ms: int | None = None) -> object: ...

    async def cancel(self) -> ManagedTaskStatus: ...


@runtime_checkable
class AgentHost(ExecutionProvider, Protocol):
    """Host capabilities consumed by a code-mode browser workflow."""

    @property
    def image_delivery(self) -> bool:
        """Return whether this execution accepts model-facing image content."""

    def current_target(self) -> BrowserTarget:
        """Return the application target associated with this agent call."""

    def emit_image(self, content: ImageContent) -> ImageDelivery:
        """Deliver image content through the host's model-facing channel."""


@runtime_checkable
class ManagedTaskHost(AgentHost, Protocol):
    """Agent host that owns resumable work across tool calls."""

    def start_task(
        self,
        name: str,
        operation: Callable[[], Awaitable[object]],
        *,
        timeout_ms: int | None = None,
    ) -> ManagedTask:
        """Start one named operation and return its managed handle."""


@dataclass(frozen=True, slots=True)
class CallbackHost:
    """AgentHost implemented by application-provided callbacks."""

    target: BrowserTarget | Callable[[], BrowserTarget]
    image_emitter: Callable[[ImageContent], ImageDelivery] | None = field(default=None, repr=False)
    execution: ExecutionContext | Callable[[], ExecutionContext] = field(
        default_factory=ExecutionContext,
        repr=False,
    )

    @property
    def image_delivery(self) -> bool:
        """Return whether an image emitter is configured for this host."""
        return self.image_emitter is not None

    def current_target(self) -> BrowserTarget:
        """Return the target value supplied by the application."""
        if callable(self.target):
            return cast(Callable[[], BrowserTarget], self.target)()
        return self.target

    def emit_image(self, content: ImageContent) -> ImageDelivery:
        """Deliver image content through the application callback."""
        if self.image_emitter is None:
            raise RuntimeError(
                "This host execution does not accept images. Return the screenshot and "
                "emit its content during a code execution with image delivery."
            )
        delivery = self.image_emitter(content)
        if not isinstance(delivery, ImageDelivery):
            raise TypeError("image_emitter must return ImageDelivery")
        return delivery

    def execution_context(self) -> ExecutionContext:
        """Return the execution limits supplied by the application."""
        context = (
            cast(Callable[[], ExecutionContext], self.execution)()
            if callable(self.execution)
            else self.execution
        )
        if not isinstance(context, ExecutionContext):
            raise TypeError("execution callback must return ExecutionContext")
        return context


def bind_host(host: AgentHost) -> Token[ExecutionProvider | None]:
    """Bind an agent host for the current execution context."""
    if not isinstance(host, AgentHost):
        raise TypeError("host must implement AgentHost")
    return bind_execution_provider(host)


def reset_host(token: Token[ExecutionProvider | None]) -> None:
    """Restore the binding represented by a context token."""
    reset_execution_provider(token)


def current_host() -> AgentHost:
    """Return the agent host bound to the current execution context."""
    provider = current_execution_provider()
    if not isinstance(provider, AgentHost):
        raise RuntimeError("no AgentHost is bound to this execution context")
    return provider
