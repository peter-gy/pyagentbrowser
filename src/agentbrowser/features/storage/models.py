from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

SameSite = Literal["Strict", "Lax", "None"]


StorageArea = Literal["local", "session"]


@dataclass(frozen=True, slots=True)
class Cookie:
    """Browser cookie metadata."""

    name: str
    value: str
    domain: str | None = None
    path: str | None = None
    expires: float | None = None
    http_only: bool | None = None
    secure: bool | None = None
    same_site: str | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)
