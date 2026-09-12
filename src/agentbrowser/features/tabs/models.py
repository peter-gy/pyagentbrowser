from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class TabInfo:
    """Metadata for one browser tab or target."""

    id: str
    url: str
    title: str = ""
    label: str | None = None
    active: bool = False
    target_id: str | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TabSwitchResult:
    """Metadata and renderer state observed while switching tabs."""

    id: str
    url: str
    title: str
    label: str | None
    revived: bool
    dialog_blocked: bool
    target_id: str | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TabCloseResult:
    """Result of closing one browser tab."""

    id: str
    label: str | None
    closed: bool
    active_tab_revived: bool
    target_id: str | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)
