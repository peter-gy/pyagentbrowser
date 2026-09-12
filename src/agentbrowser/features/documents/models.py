from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from agentbrowser.contracts.scope import DocumentScope

LoadState = Literal["load", "domcontentloaded", "networkidle", "none"]


WaitSelectorState = Literal["attached", "detached", "hidden", "visible"]


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Element bounding box in CSS pixels."""

    x: float
    y: float
    width: float
    height: float
    raw: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ScrollPosition:
    """Scroll offsets in CSS pixels."""

    x: float
    y: float


@dataclass(frozen=True, slots=True)
class ScrollResult:
    """Measured effect of scrolling one document or container."""

    scope: DocumentScope
    container: str
    before: ScrollPosition
    after: ScrollPosition

    @property
    def moved(self) -> bool:
        """Return whether either scroll offset changed."""
        return self.before != self.after


@dataclass(frozen=True, slots=True)
class ElementGeometry:
    """Element bounds and overflow measurements in CSS pixels."""

    scope: DocumentScope
    selector: str
    x: float
    y: float
    width: float
    height: float
    client_width: float
    client_height: float
    scroll_width: float
    scroll_height: float

    @property
    def overflows_x(self) -> bool:
        """Return whether content exceeds the client width."""
        return self.scroll_width > self.client_width

    @property
    def overflows_y(self) -> bool:
        """Return whether content exceeds the client height."""
        return self.scroll_height > self.client_height
