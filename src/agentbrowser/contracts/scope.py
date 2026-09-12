from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DocumentScope:
    """Browser target and frame identity for one document operation."""

    target_id: str | None = None
    frame_id: str | None = None
    url: str | None = None
    generation: int = 0
