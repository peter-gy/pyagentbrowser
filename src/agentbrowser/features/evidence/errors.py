from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agentbrowser.contracts.actions import is_stale_ref_error_code
from agentbrowser.contracts.errors import BrowserError

if TYPE_CHECKING:
    from agentbrowser.features.evidence.ref import Ref
    from agentbrowser.features.evidence.ref_async import AsyncRef


class StaleRefError(BrowserError):
    """Raised when an action targets a ref from an expired snapshot."""

    def __init__(self, ref: Ref, error: BrowserError | None = None) -> None:
        if error is None:
            super().__init__(
                "ref",
                f"stale snapshot generation for {ref.selector}",
                {},
                code="stale_ref",
            )
        else:
            super().__init__(
                error.action,
                f"stale snapshot ref {ref.selector}: {error}",
                error.response,
                code=error.code,
            )
        self.ref = ref

    def refresh(self, **criteria: Any) -> Ref:
        """Resolve the ref again from a fresh snapshot."""
        return self.ref.refresh(**criteria)


class AsyncStaleRefError(BrowserError):
    """Raised when an async action targets a ref from an expired snapshot."""

    def __init__(self, ref: AsyncRef, error: BrowserError | None = None) -> None:
        if error is None:
            super().__init__(
                "ref",
                f"stale snapshot generation for {ref.selector}",
                {},
                code="stale_ref",
            )
        else:
            super().__init__(
                error.action,
                f"stale snapshot ref {ref.selector}: {error}",
                error.response,
                code=error.code,
            )
        self.ref = ref

    async def refresh(self, **criteria: Any) -> AsyncRef:
        """Resolve the ref again from a fresh snapshot."""
        return await self.ref.refresh(**criteria)


def stale_error(ref: Ref, error: BaseException) -> BaseException:
    if isinstance(error, StaleRefError):
        return error
    if isinstance(error, BrowserError) and is_stale_ref_error_code(error.code):
        return StaleRefError(ref, error)
    return error


def async_stale_error(ref: AsyncRef, error: BaseException) -> BaseException:
    if isinstance(error, AsyncStaleRefError):
        return error
    if isinstance(error, BrowserError) and is_stale_ref_error_code(error.code):
        return AsyncStaleRefError(ref, error)
    return error
