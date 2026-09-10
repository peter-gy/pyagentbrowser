"""Execution budgets carried through ordered browser command dispatch."""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from time import monotonic
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Execution limits for browser commands in the current context."""

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
        """Return an operation timeout that reserves execution time for cleanup."""
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


@runtime_checkable
class ExecutionProvider(Protocol):
    """Supply the execution budget for browser commands."""

    def execution_context(self) -> ExecutionContext: ...


_CURRENT_PROVIDER: ContextVar[ExecutionProvider | None] = ContextVar(
    "agentbrowser_execution_provider", default=None
)


def bind_execution_provider(provider: ExecutionProvider) -> Token[ExecutionProvider | None]:
    """Bind an execution provider and return the previous binding's token."""
    if not isinstance(provider, ExecutionProvider):
        raise TypeError("provider must implement ExecutionProvider")
    return _CURRENT_PROVIDER.set(provider)


def reset_execution_provider(token: Token[ExecutionProvider | None]) -> None:
    """Restore the execution binding represented by a context token."""
    _CURRENT_PROVIDER.reset(token)


def current_execution_provider() -> ExecutionProvider | None:
    """Return the execution provider bound to the current context."""
    return _CURRENT_PROVIDER.get()


def command_parameters(params: dict[str, object]) -> dict[str, object]:
    """Carry the execution deadline across the async session's owner-thread queue."""
    result = dict(params)
    deadline = result.pop("_executionDeadline", None)
    if deadline is None:
        provider = current_execution_provider()
        if provider is None:
            return result
        context = provider.execution_context()
        if context.timeout_ms is None:
            return result
        deadline = context._started + max(0, context.timeout_ms - 1_000) / 1_000
    if not isinstance(deadline, int | float):
        raise TypeError("execution deadline must be a monotonic timestamp")
    remaining = int((deadline - monotonic()) * 1_000)
    if remaining <= 0:
        raise TimeoutError("Execution deadline reached before browser dispatch")
    result["_executionDeadline"] = deadline
    timeout = result.get("_timeoutMs", remaining)
    if not isinstance(timeout, int) or timeout <= 0:
        raise ValueError("execution timeout must be a positive integer")
    result["_timeoutMs"] = min(remaining, timeout)
    return result
