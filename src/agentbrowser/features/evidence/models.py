from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class SnapshotSpec:
    """Options that define a reproducible accessibility snapshot."""

    selector: str | None = None
    interactive: bool = True
    compact: bool = False
    max_depth: int | None = None
    urls: bool = False

    def __post_init__(self) -> None:
        if self.max_depth is not None and self.max_depth < 0:
            raise ValueError("max_depth must be non-negative")


@dataclass(frozen=True, slots=True)
class SnapshotData:
    """Parsed native accessibility snapshot data.

    Attributes
    ----------
    text
        Human-readable snapshot text.
    origin
        Page URL or origin reported by the native engine.
    refs
        Mapping of snapshot ref ids to accessible metadata.
    raw
        Complete native response mapping.
    hints
        Mapping of snapshot ref ids to the hint printed beside the ref.
    """

    text: str
    origin: str
    refs: Mapping[str, Mapping[str, Any]]
    raw: Mapping[str, Any]
    spec: SnapshotSpec = field(default_factory=SnapshotSpec)
    generation: int = 0
    hints: Mapping[str, str] = field(default_factory=dict)

    def ref(self, ref_id: str) -> SnapshotRef:
        """Return one snapshot ref by id.

        Parameters
        ----------
        ref_id
            Ref id with or without the leading `@`.

        Returns
        -------
        SnapshotRef
            Parsed ref metadata.
        """
        normalized = normalize_ref(ref_id)
        metadata = self.refs.get(normalized)
        if metadata is None:
            raise KeyError(f"snapshot has no ref {ref_selector(ref_id)}")
        return SnapshotRef(
            id=normalized,
            role=str(metadata.get("role", "")),
            name=str(metadata.get("name", "")),
            raw=metadata,
            hint=self.hints.get(normalized),
        )

    def find_refs(
        self,
        *,
        role: str | None = None,
        name: str | None = None,
        contains: str | None = None,
        hint: str | None = None,
        exact: bool = False,
    ) -> list[SnapshotRef]:
        """Return refs matching role, name, and hint criteria."""
        refs = [self.ref(ref_id) for ref_id in self.refs]
        return [
            ref
            for ref in refs
            if _matches_ref(ref, role=role, name=name, contains=contains, hint=hint, exact=exact)
        ]

    def one_ref(
        self,
        *,
        role: str | None = None,
        name: str | None = None,
        contains: str | None = None,
        hint: str | None = None,
        exact: bool = False,
    ) -> SnapshotRef:
        """Return one matching ref or raise with bounded recovery context."""
        matches = self.find_refs(
            role=role,
            name=name,
            contains=contains,
            hint=hint,
            exact=exact,
        )
        criteria = _ref_criteria(
            role=role,
            name=name,
            contains=contains,
            hint=hint,
            exact=exact,
        )
        if not matches:
            available = ", ".join(
                _describe(ref) for ref in (self.ref(ref_id) for ref_id in tuple(self.refs)[:8])
            )
            suffix = f". Available refs: {available}" if available else ". Snapshot has no refs"
            raise LookupError(f"snapshot contains no matching ref for {criteria}{suffix}")
        if len(matches) > 1:
            candidates = ", ".join(
                match.selector if match.hint is None else f"{match.selector} hint={match.hint!r}"
                for match in matches[:8]
            )
            raise LookupError(
                f"snapshot criteria matched multiple refs for {criteria}: {candidates}"
            )
        return matches[0]


@dataclass(frozen=True, slots=True)
class SnapshotRef:
    """A deterministic element ref produced by an agent-browser snapshot.

    `hint` is the engine's disambiguation text for a control whose accessible
    name is empty or shared with another ref in the same snapshot. It lists the
    control's icon, image file, `data-testid`, `name` or `id`, and the text of
    its nearest row or list item, such as `icon:lucide-trash; in:Invoice 42`.
    """

    id: str
    role: str
    name: str
    raw: Mapping[str, Any]
    hint: str | None = None

    @property
    def selector(self) -> str:
        """Selector form accepted by native commands, for example `@r1`."""
        return ref_selector(self.id)


def ref_selector(ref_id: str) -> str:
    return f"@{normalize_ref(ref_id)}"


def normalize_ref(ref_id: str) -> str:
    return ref_id[1:] if ref_id.startswith("@") else ref_id


def _describe(ref: SnapshotRef) -> str:
    described = f"{ref.selector} {ref.role} {ref.name!r}"
    return described if ref.hint is None else f"{described} hint={ref.hint!r}"


def _ref_criteria(
    *,
    role: str | None,
    name: str | None,
    contains: str | None,
    hint: str | None,
    exact: bool,
) -> str:
    values = {
        "role": role,
        "name": name,
        "contains": contains,
        "hint": hint,
        "exact": exact,
    }
    return (
        ", ".join(
            f"{key}={value!r}"
            for key, value in values.items()
            if value is not None and (key != "exact" or value)
        )
        or "any ref"
    )


def _matches_ref(
    ref: SnapshotRef,
    *,
    role: str | None,
    name: str | None,
    contains: str | None,
    hint: str | None,
    exact: bool,
) -> bool:
    if role is not None and ref.role != role:
        return False
    if hint is not None and (ref.hint is None or hint not in ref.hint):
        return False
    if name is not None:
        matches_name = ref.name == name if exact else name in ref.name
        if not matches_name:
            return False
    if contains is None:
        return True
    return ref.name == contains if exact else contains in ref.name
