from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Generic, Literal, cast

from agentbrowser.contracts.types import T


class AgentBrowserError(RuntimeError):
    """Common catchable base for Python SDK errors."""


class NativeParseError(AgentBrowserError, ValueError):
    """Raised when native payloads cannot be parsed into typed SDK models."""


class BrowserError(AgentBrowserError):
    """Raised when the native agent-browser engine returns an unsuccessful response.

    Command behavior follows https://agent-browser.dev/commands.
    """

    def __init__(
        self,
        action: str,
        message: str,
        response: Mapping[str, Any],
        *,
        code: str | None = None,
    ) -> None:
        super().__init__(f"{action} failed: {message}")
        self.action = action
        self.response = dict(response)
        self.code = code or _error_code_from_response(response)


class FrameLookupError(AgentBrowserError, LookupError):
    """Raised when frame criteria have no unique match in one parent scope."""

    def __init__(
        self,
        reason: Literal["not_found", "ambiguous", "detached", "scope_mismatch"],
        criteria: str,
        candidates: Sequence[str] = (),
    ) -> None:
        self.reason = reason
        self.criteria = criteria
        self.candidates = tuple(candidates)
        available = ", ".join(self.candidates) or "<none>"
        super().__init__(f"frame {reason.replace('_', ' ')} for {criteria}: {available}")


class ConfirmationRequired(BrowserError, Generic[T]):
    """Raised when the native policy requires confirmation before execution."""

    def __init__(
        self,
        action: str,
        data: Mapping[str, Any],
        response: Mapping[str, Any],
    ) -> None:
        confirmation_id = data.get("confirmation_id") or response.get("id")
        super().__init__(
            action,
            f"confirmation required for {action}",
            response,
        )
        self.confirmation_id = str(confirmation_id) if confirmation_id is not None else None
        self.data = dict(data)
        self.pending = cast(T, None)


def _error_code_from_response(response: Mapping[str, Any]) -> str | None:
    for key in ("code", "error_code", "errorCode"):
        value = response.get(key)
        if value is not None:
            return str(value)

    data = response.get("data")
    if isinstance(data, Mapping):
        for key in ("code", "error_code", "errorCode"):
            value = data.get(key)
            if value is not None:
                return str(value)
    return None
