"""Contracts shared by browser automation hosts and code-mode agents."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic
from typing import Literal, Protocol, TypeAlias, cast, runtime_checkable

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

    def __post_init__(self) -> None:
        if self.status not in {"accepted", "queued", "submitted"}:
            raise ValueError("ImageDelivery.status must be accepted, queued, or submitted")


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Execution limits exposed by the active agent host."""

    timeout_ms: int | None = None
    cancellation: bool = False
    managed_tasks: bool = False
    _started: float = field(
        default_factory=lambda: monotonic(), init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        if self.timeout_ms is not None and self.timeout_ms < 0:
            raise ValueError("ExecutionContext.timeout_ms must be non-negative")

    def limit(self, requested_ms: int | None = None, *, cleanup_ms: int = 1_000) -> int | None:
        """Return an operation timeout that reserves host time for cleanup."""
        if requested_ms is not None and requested_ms < 0:
            raise ValueError("requested_ms must be non-negative")
        if cleanup_ms < 0:
            raise ValueError("cleanup_ms must be non-negative")
        available = (
            None
            if self.timeout_ms is None
            else max(0, self.timeout_ms - int((monotonic() - self._started) * 1_000) - cleanup_ms)
        )
        if requested_ms is None:
            return available
        return requested_ms if available is None else min(requested_ms, available)


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
class AgentHost(Protocol):
    """Host capabilities consumed by a code-mode browser workflow."""

    @property
    def image_delivery(self) -> bool:
        """Return whether this execution accepts model-facing image content."""

    def current_target(self) -> BrowserTarget:
        """Return the application target associated with this agent call."""

    def emit_image(self, content: ImageContent) -> ImageDelivery:
        """Deliver image content through the host's model-facing channel."""

    def execution_context(self) -> ExecutionContext:
        """Return the limits of the current tool execution."""


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


_CURRENT_HOST: ContextVar[AgentHost | None] = ContextVar("agentbrowser_current_host", default=None)


def _execution_params(params: dict[str, object]) -> dict[str, object]:
    """Carry the host deadline across the async session's owner-thread queue."""
    result = dict(params)
    deadline = result.pop("_executionDeadline", None)
    if deadline is None:
        host = _CURRENT_HOST.get()
        if host is None:
            return result
        context = host.execution_context()
        if context.timeout_ms is None:
            return result
        deadline = context._started + max(0, context.timeout_ms - 1_000) / 1_000
    if not isinstance(deadline, int | float):
        raise TypeError("execution deadline must be a monotonic timestamp")
    remaining = int((deadline - monotonic()) * 1_000)
    if remaining <= 0:
        raise TimeoutError("Agent host execution deadline reached before browser dispatch")
    result["_executionDeadline"] = deadline
    timeout = result.get("_timeoutMs", remaining)
    if not isinstance(timeout, int) or timeout <= 0:
        raise ValueError("execution timeout must be a positive integer")
    result["_timeoutMs"] = min(remaining, timeout)
    return result


def bind_host(host: AgentHost) -> Token[AgentHost | None]:
    """Bind an agent host for the current execution context."""
    if not isinstance(host, AgentHost):
        raise TypeError("host must implement AgentHost")
    return _CURRENT_HOST.set(host)


def reset_host(token: Token[AgentHost | None]) -> None:
    """Restore the host binding represented by a context token."""
    _CURRENT_HOST.reset(token)


def current_host() -> AgentHost:
    """Return the agent host bound to the current execution context."""
    host = _CURRENT_HOST.get()
    if host is None:
        raise RuntimeError("no AgentHost is bound to this execution context")
    return host
