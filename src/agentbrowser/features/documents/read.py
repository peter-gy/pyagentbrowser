from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

LlmsMode = Literal["index", "full"]


@dataclass(frozen=True, slots=True)
class ReadResult:
    """Markdown-oriented content returned by `browser.page.read()`."""

    url: str
    final_url: str
    status: int | None
    content_type: str
    source: str
    truncated: bool
    content: str
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ReadMode:
    """Native read mode passed to `browser.page.read(mode=...)`."""

    raw: bool = False
    require_markdown: bool = False
    llms: LlmsMode | None = None
    outline: bool = False

    def __post_init__(self) -> None:
        if self.llms not in {None, "index", "full"}:
            raise ValueError("llms must be 'index', 'full', or None")
        if self.raw and (self.require_markdown or self.llms is not None or self.outline):
            raise ValueError("ReadMode.html() cannot be combined with markdown, llms, or outline")
        if self.outline and (self.require_markdown or self.llms is not None):
            raise ValueError("ReadMode.outline_only() cannot be combined with markdown or llms")

    @classmethod
    def html(cls) -> ReadMode:
        """Return raw HTML content when native read supports it."""
        return cls(raw=True)

    @classmethod
    def markdown(cls, *, require: bool = False) -> ReadMode:
        """Return Markdown-oriented content."""
        return cls(require_markdown=require)

    @classmethod
    def llms_index(cls, *, require_markdown: bool = False) -> ReadMode:
        """Read through llms.txt index discovery."""
        return cls(require_markdown=require_markdown, llms="index")

    @classmethod
    def llms_full(cls, *, require_markdown: bool = False) -> ReadMode:
        """Read through full llms.txt content discovery."""
        return cls(require_markdown=require_markdown, llms="full")

    @classmethod
    def outline_only(cls) -> ReadMode:
        """Return outline extraction content."""
        return cls(outline=True)
