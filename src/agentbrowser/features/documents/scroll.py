from __future__ import annotations

from dataclasses import dataclass

from agentbrowser.features.documents.base import _Document
from agentbrowser.features.documents.base_async import _AsyncDocument
from agentbrowser.features.documents.commands import scroll
from agentbrowser.features.documents.models import ScrollResult


@dataclass(frozen=True, slots=True)
class Scroll:
    """Measured scrolling bound to one page or frame document."""

    page: _Document

    def by(self, *, x: float = 0, y: float = 0, selector: str | None = None) -> ScrollResult:
        """Scroll a document or container and return its offsets before and after."""
        return self.page.execute(scroll(self.page._executor, x=x, y=y, selector=selector))


@dataclass(frozen=True, slots=True)
class AsyncScroll:
    """Async measured scrolling bound to one page or frame document."""

    page: _AsyncDocument

    async def by(self, *, x: float = 0, y: float = 0, selector: str | None = None) -> ScrollResult:
        """Scroll a document or container and return its offsets before and after."""
        return await self.page.execute(scroll(self.page._executor, x=x, y=y, selector=selector))
