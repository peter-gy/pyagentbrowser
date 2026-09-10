from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ImageContent:
    """Image bytes, MIME type, and optional source path."""

    data: bytes
    media_type: str
    source: Path | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.data, bytes) or not self.data:
            raise ValueError("ImageContent.data must contain image bytes")
        if not self.media_type.startswith("image/"):
            raise ValueError("ImageContent.media_type must be an image MIME type")
