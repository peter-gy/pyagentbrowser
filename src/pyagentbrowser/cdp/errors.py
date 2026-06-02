from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pyagentbrowser.models import AgentBrowserError


class CDPError(AgentBrowserError):
    """Base error for Python-owned CDP workflows."""


class CDPProtocolError(CDPError):
    """Raised when CDP returns an error response for a method."""

    def __init__(self, method: str, error: object) -> None:
        super().__init__(f"{method} failed: {error}")
        self.method = method
        self.error = error


class CDPTargetNotFoundError(CDPError):
    """Raised when no CDP target matches the requested criteria."""


class CDPTargetAmbiguityError(CDPError):
    """Raised when multiple CDP targets match strict criteria."""


class CDPFrameNotFoundError(CDPError):
    """Raised when no frame matches the requested criteria."""


class CDPFrameAmbiguityError(CDPError):
    """Raised when multiple frames match strict criteria."""


class CDPContextNotFoundError(CDPError):
    """Raised when no execution context matches the requested criteria."""


class CDPContextAmbiguityError(CDPError):
    """Raised when multiple execution contexts match strict criteria."""


class CDPStaleObjectError(CDPError):
    """Raised when a cached frame or context is stale after navigation."""


class CDPEvaluationError(CDPError):
    """Raised when JavaScript evaluation throws in the target context."""

    def __init__(self, details: Mapping[str, Any]) -> None:
        text = str(details.get("text") or details.get("exception", {}).get("description"))
        super().__init__(f"JavaScript evaluation failed: {text}")
        self.details = dict(details)


class CDPTimeoutError(CDPError):
    """Raised when a CDP method does not receive a response in time."""

    def __init__(self, method: str, timeout: float | None) -> None:
        suffix = "" if timeout is None else f" after {timeout:g}s"
        super().__init__(f"{method} timed out waiting for a CDP response{suffix}")
        self.method = method
        self.timeout = timeout
