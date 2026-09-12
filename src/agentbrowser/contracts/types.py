from __future__ import annotations

from collections.abc import Mapping
from typing import TypeAlias, TypeVar

JSONPrimitive: TypeAlias = str | int | float | bool | None


JSONValue: TypeAlias = object


JSONObject: TypeAlias = dict[str, JSONValue]


JSONMapping: TypeAlias = Mapping[str, JSONValue]


T = TypeVar("T")


RefT = TypeVar("RefT")


SnapshotT = TypeVar("SnapshotT")
