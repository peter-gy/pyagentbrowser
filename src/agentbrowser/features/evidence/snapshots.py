from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from agentbrowser.contracts.errors import ConfirmationRequired
from agentbrowser.features.evidence.changes import SnapshotDiff, diff_snapshot_data
from agentbrowser.features.evidence.models import SnapshotData, SnapshotSpec
from agentbrowser.features.evidence.ref import Ref
from agentbrowser.features.evidence.ref_async import AsyncRef

if TYPE_CHECKING:
    from agentbrowser.features.documents.base import _Document
    from agentbrowser.features.documents.base_async import _AsyncDocument


@dataclass(frozen=True, slots=True)
class Snapshot:
    """Immutable accessibility snapshot bound to its document."""

    document: _Document
    _data: SnapshotData

    @property
    def text(self) -> str:
        """Human-readable accessibility tree."""
        return self._data.text

    @property
    def origin(self) -> str:
        """Page URL reported by the native engine."""
        return self._data.origin

    @property
    def url(self) -> str:
        """Page URL reported by the native engine."""
        return self.origin

    @property
    def spec(self) -> SnapshotSpec:
        """Capture specification used for this snapshot."""
        return self._data.spec

    @property
    def generation(self) -> int:
        """Return the controller ref generation captured by this snapshot."""
        return self._data.generation

    @property
    def raw(self) -> Mapping[str, Any]:
        """Native snapshot response data."""
        return self._data.raw

    def __repr__(self) -> str:
        return (
            f"Snapshot(origin={self.origin!r}, refs={len(self._data.refs)!r}, spec={self.spec!r})"
        )

    @property
    def refs(self) -> Mapping[str, Ref]:
        """Bound refs keyed by ref id."""
        return {ref_id: self.ref(ref_id) for ref_id in self._data.refs}

    def ref(self, ref_id: str) -> Ref:
        """Bind one snapshot ref to this document."""
        return Ref(self, self._data.ref(ref_id))

    def one(
        self,
        *,
        role: str | None = None,
        name: str | None = None,
        contains: str | None = None,
        exact: bool = False,
    ) -> Ref:
        """Return one ref matching accessible metadata."""
        return Ref(
            self,
            self._data.one_ref(
                role=role,
                name=name,
                contains=contains,
                exact=exact,
            ),
        )

    def all(
        self,
        *,
        role: str | None = None,
        name: str | None = None,
        contains: str | None = None,
        exact: bool = False,
    ) -> tuple[Ref, ...]:
        """Return all refs matching accessible metadata."""
        return tuple(
            Ref(self, snapshot_ref)
            for snapshot_ref in self._data.find_refs(
                role=role,
                name=name,
                contains=contains,
                exact=exact,
            )
        )

    def refresh(self) -> Snapshot:
        """Capture the same snapshot specification again."""
        return self.document.observe(self.spec)

    def diff(self) -> SnapshotDiff:
        """Compare this snapshot with the current page state."""
        try:
            current = self.refresh()
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map(
                    lambda after: diff_snapshot_data(self._data, after._data)
                )
            raise
        return diff_snapshot_data(self._data, current._data)


@dataclass(frozen=True, slots=True)
class AsyncSnapshot:
    """Immutable accessibility snapshot bound to an async browser."""

    document: _AsyncDocument
    _data: SnapshotData

    @property
    def text(self) -> str:
        """Human-readable accessibility tree."""
        return self._data.text

    @property
    def origin(self) -> str:
        """Page URL reported by the native engine."""
        return self._data.origin

    @property
    def url(self) -> str:
        """Page URL reported by the native engine."""
        return self.origin

    @property
    def spec(self) -> SnapshotSpec:
        """Capture specification used for this snapshot."""
        return self._data.spec

    @property
    def generation(self) -> int:
        """Return the controller ref generation captured by this snapshot."""
        return self._data.generation

    @property
    def raw(self) -> Mapping[str, Any]:
        """Native snapshot response data."""
        return self._data.raw

    def __repr__(self) -> str:
        return (
            f"AsyncSnapshot(origin={self.origin!r}, refs={len(self._data.refs)!r}, "
            f"spec={self.spec!r})"
        )

    @property
    def refs(self) -> Mapping[str, AsyncRef]:
        """Bound refs keyed by ref id."""
        return {ref_id: self.ref(ref_id) for ref_id in self._data.refs}

    def ref(self, ref_id: str) -> AsyncRef:
        """Bind one snapshot ref to this document."""
        return AsyncRef(self, self._data.ref(ref_id))

    def one(
        self,
        *,
        role: str | None = None,
        name: str | None = None,
        contains: str | None = None,
        exact: bool = False,
    ) -> AsyncRef:
        """Return one ref matching accessible metadata."""
        return AsyncRef(
            self,
            self._data.one_ref(
                role=role,
                name=name,
                contains=contains,
                exact=exact,
            ),
        )

    def all(
        self,
        *,
        role: str | None = None,
        name: str | None = None,
        contains: str | None = None,
        exact: bool = False,
    ) -> tuple[AsyncRef, ...]:
        """Return all refs matching accessible metadata."""
        return tuple(
            AsyncRef(self, snapshot_ref)
            for snapshot_ref in self._data.find_refs(
                role=role,
                name=name,
                contains=contains,
                exact=exact,
            )
        )

    async def refresh(self) -> AsyncSnapshot:
        """Capture the same snapshot specification again."""
        return await self.document.observe(self.spec)

    async def diff(self) -> SnapshotDiff:
        """Compare this snapshot with the current page state."""
        try:
            current = await self.refresh()
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map(
                    lambda after: diff_snapshot_data(self._data, after._data)
                )
            raise
        return diff_snapshot_data(self._data, current._data)
