from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from agentbrowser.contracts.errors import NativeParseError
from agentbrowser.features.evidence.changes import SnapshotDiff
from agentbrowser.features.evidence.models import SnapshotData, SnapshotSpec


def snapshot_from_data(
    data: Mapping[str, Any],
    *,
    spec: SnapshotSpec | None = None,
) -> SnapshotData:
    text = data.get("snapshot")
    origin = data.get("origin")
    raw_refs = data.get("refs")
    if not isinstance(text, str):
        raise NativeParseError("Snapshot field 'snapshot' must be a string")
    if not isinstance(origin, str):
        raise NativeParseError("Snapshot field 'origin' must be a string")
    if not isinstance(raw_refs, Mapping):
        raise NativeParseError("Snapshot field 'refs' must be an object")
    refs: dict[str, dict[str, Any]] = {}
    for key, value in raw_refs.items():
        if not isinstance(value, Mapping):
            raise NativeParseError("Snapshot ref metadata must be objects")
        if not isinstance(value.get("role"), str) or not isinstance(value.get("name"), str):
            raise NativeParseError("Snapshot refs require string 'role' and 'name' fields")
        refs[str(key)] = {str(ref_key): ref_value for ref_key, ref_value in value.items()}
    return SnapshotData(
        text=text,
        origin=origin,
        refs=refs,
        raw=data,
        spec=spec or SnapshotSpec(),
    )


def snapshot_diff_from_data(data: Mapping[str, Any]) -> SnapshotDiff:
    text = data.get("diff")
    additions = data.get("additions")
    removals = data.get("removals")
    unchanged = data.get("unchanged")
    changed = data.get("changed")
    if not isinstance(text, str):
        raise NativeParseError("diff_snapshot field 'diff' must be a string")
    if any(
        not isinstance(value, int) or isinstance(value, bool)
        for value in (additions, removals, unchanged)
    ):
        raise NativeParseError("diff_snapshot counts must be integers")
    if not isinstance(changed, bool):
        raise NativeParseError("diff_snapshot field 'changed' must be a boolean")
    return SnapshotDiff(
        text=text,
        additions=cast(int, additions),
        removals=cast(int, removals),
        unchanged=cast(int, unchanged),
        changed=changed,
        raw=data,
    )
