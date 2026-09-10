from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


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
