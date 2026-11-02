from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

SameSite = Literal["Strict", "Lax", "None"]


StorageArea = Literal["local", "session"]


@dataclass(frozen=True, slots=True)
class Cookie:
    """One browser cookie.

    `expires` is seconds since the Unix epoch, or `-1` for a session cookie.
    """

    name: str
    value: str
    domain: str
    path: str
    expires: float
    http_only: bool
    secure: bool
    session: bool
    same_site: SameSite | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StateLoadResult:
    """Outcome of `browser.state.load()`.

    The engine writes Web Storage only while the page is on the saved origin.
    `skipped_origins` lists saved origins whose storage was not restored.
    """

    path: Path
    skipped_origins: tuple[str, ...]
