from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, TypeAlias

AccessibilityTargetPart: TypeAlias = str | tuple["AccessibilityTargetPart", ...]


@dataclass(frozen=True, slots=True)
class AccessibilityCounts:
    """Rule counts returned by an accessibility audit."""

    violations: int
    incomplete: int
    passes: int
    inapplicable: int


@dataclass(frozen=True, slots=True)
class AccessibilityNode:
    """One DOM target reported by an accessibility rule."""

    target: tuple[AccessibilityTargetPart, ...]
    html: str
    failure_summary: str
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AccessibilityIssue:
    """One failed or incomplete accessibility rule."""

    id: str
    impact: str
    help: str
    help_url: str
    tags: tuple[str, ...]
    node_count: int
    nodes: tuple[AccessibilityNode, ...]
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AccessibilityAudit:
    """Structured axe-core accessibility audit for one page."""

    url: str
    axe_version: str | None
    counts: AccessibilityCounts
    violations: tuple[AccessibilityIssue, ...]
    incomplete: tuple[AccessibilityIssue, ...]
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ConsoleMessage:
    """Captured browser console message."""

    type: str
    text: str
    level: str | None = None
    url: str | None = None
    line: int | None = None
    column: int | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)
