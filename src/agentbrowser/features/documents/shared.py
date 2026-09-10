from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, TypeVar

from agentbrowser.contracts.errors import FrameLookupError, NativeParseError
from agentbrowser.features.documents.models import ScrollPosition

T = TypeVar("T")


class _FrameLike(Protocol):
    @property
    def frame_id(self) -> str | None: ...

    frame_name: str
    frame_url: str


def one_frame(matches: Sequence[T], criteria: str, candidates: Sequence[_FrameLike]) -> T:
    if not matches:
        raise FrameLookupError("not_found", criteria, frame_candidates(candidates))
    if len(matches) > 1:
        raise FrameLookupError("ambiguous", criteria, frame_candidates(candidates))
    return matches[0]


def frame_candidates(candidates: Sequence[_FrameLike]) -> tuple[str, ...]:
    return tuple(
        f"{frame.frame_id or ''} name={frame.frame_name!r} url={frame.frame_url!r}"
        for frame in candidates[:8]
    )


def collect_frame_records(
    tree: Any,
    parent_id: str | None,
    records: list[tuple[Mapping[str, Any], str | None]],
) -> None:
    if not isinstance(tree, Mapping):
        return
    raw = tree.get("frame")
    if not isinstance(raw, Mapping) or not isinstance(raw.get("id"), str):
        return
    frame_id = str(raw["id"])
    declared_parent = raw.get("parentId")
    records.append((raw, str(declared_parent) if isinstance(declared_parent, str) else parent_id))
    children = tree.get("childFrames")
    if isinstance(children, list):
        for child in children:
            collect_frame_records(child, frame_id, records)


def merge_frame_records(
    records: Sequence[tuple[Mapping[str, Any], str | None]],
) -> list[tuple[Mapping[str, Any], str | None]]:
    merged: dict[str, tuple[Mapping[str, Any], str | None]] = {}
    for raw, parent_id in records:
        frame_id = str(raw["id"])
        existing = merged.get(frame_id)
        if existing is None:
            merged[frame_id] = (raw, parent_id)
        else:
            merged[frame_id] = (raw, existing[1] or parent_id)
    return list(merged.values())


def scroll_position(value: Any) -> ScrollPosition:
    if not isinstance(value, Mapping):
        raise NativeParseError("scroll position must be an object")
    x = value.get("x")
    y = value.get("y")
    if not isinstance(x, int | float) or not isinstance(y, int | float):
        raise NativeParseError("scroll offsets must be numbers")
    return ScrollPosition(float(x), float(y))
