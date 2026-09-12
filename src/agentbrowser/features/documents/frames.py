from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from agentbrowser.contracts.decode import required_string
from agentbrowser.contracts.errors import ConfirmationRequired, FrameLookupError
from agentbrowser.execution.commands import Command
from agentbrowser.features.documents.base import _Document
from agentbrowser.features.documents.handles import Frame
from agentbrowser.features.documents.shared import (
    collect_frame_records,
    frame_candidates,
    merge_frame_records,
    one_frame,
)


@dataclass(frozen=True, slots=True)
class Frames:
    """Discover child browsing contexts from one page or frame."""

    page: _Document

    def tree(self) -> tuple[Frame, ...]:
        """Return descendant frames with stable identities and parent links."""
        return self.page._execute(Command("frame", {"list": True}, decode=self._tree_result))

    def _tree_result(self, data: Mapping[str, Any]) -> tuple[Frame, ...]:
        root = data.get("frameTree")
        records: list[tuple[Mapping[str, Any], str | None]] = []
        collect_frame_records(root, None, records)
        parent_scope = self.page.frame_id
        root_frame = root.get("frame") if isinstance(root, Mapping) else None
        root_id = root_frame.get("id") if isinstance(root_frame, Mapping) else None
        expected_parent = parent_scope or (str(root_id) if isinstance(root_id, str) else None)
        oopif_trees = data.get("oopifFrameTrees")
        if isinstance(oopif_trees, list):
            known_parents = {str(raw["id"]): parent_id for raw, parent_id in records}
            for item in oopif_trees:
                if not isinstance(item, Mapping):
                    continue
                root_frame_id = item.get("rootFrameId")
                parent_id = (
                    known_parents.get(str(root_frame_id))
                    if isinstance(root_frame_id, str)
                    else None
                )
                collect_frame_records(item.get("frameTree"), parent_id, records)
        records = merge_frame_records(records)
        parents = {str(raw["id"]): parent_id for raw, parent_id in records}

        def descendant(frame_id: str) -> bool:
            visited: set[str] = set()
            parent = parents.get(frame_id)
            while parent is not None and parent not in visited:
                if parent == expected_parent:
                    return True
                visited.add(parent)
                parent = parents.get(parent)
            return False

        return tuple(
            Frame(
                self.page._executor,
                target_id=data.get("targetId") or self.page.target_id,
                frame_id=str(raw["id"]),
                frame_name=str(raw.get("name", "")),
                frame_url=str(raw.get("url", "")),
                parent_frame_id=parent_id,
            )
            for raw, parent_id in records
            if descendant(str(raw["id"]))
        )

    def get(
        self,
        *,
        id: str | None = None,
        selector: str | None = None,
        name: str | None = None,
        url: str | None = None,
    ) -> Frame:
        """Resolve one child frame by ID, owning element, name, or URL."""
        if sum(value is not None for value in (id, selector, name, url)) != 1:
            raise ValueError("pass exactly one of id, selector, name, or url")
        try:
            candidates = self.tree()
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map(
                    lambda frames: self._get_from_candidates(frames, id, selector, name, url)
                )
            raise
        return self._get_from_candidates(candidates, id, selector, name, url)

    def _get_from_candidates(
        self,
        candidates: tuple[Frame, ...],
        id: str | None,
        selector: str | None,
        name: str | None,
        url: str | None,
    ) -> Frame:
        if selector is None:
            matches = [
                frame
                for frame in candidates
                if (
                    frame.frame_id == id
                    if id is not None
                    else frame.frame_name == name
                    if name is not None
                    else frame.frame_url == url
                )
            ]
            return one_frame(matches, repr(id or name or url), candidates)
        target_id = self.page.target_id or self.page._executor.scope.target_id
        parent = type(self.page)(
            self.page._executor,
            target_id=target_id,
            frame_id=self.page.frame_id,
        )
        if selector.startswith("@"):
            return self._resolve_element(parent, selector, candidates)
        try:
            count = parent.evaluate(f"document.querySelectorAll({json.dumps(selector)}).length")
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map(
                    lambda count: self._resolve_count(parent, selector, candidates, count)
                )
            raise
        return self._resolve_count(parent, selector, candidates, count)

    def _resolve_count(
        self, parent: _Document, selector: str, candidates: tuple[Frame, ...], count: Any
    ) -> Frame:
        if count != 1:
            raise FrameLookupError(
                "not_found" if count == 0 else "ambiguous",
                repr(selector),
                frame_candidates(candidates),
            )
        return self._resolve_element(parent, selector, candidates)

    def _resolve_element(
        self, parent: _Document, selector: str, candidates: tuple[Frame, ...]
    ) -> Frame:
        def decode(data: Mapping[str, Any]) -> Frame:
            frame_id = required_string(data, "frameId", action="frame")
            for frame in candidates:
                if frame.frame_id == frame_id:
                    return frame
            return Frame(
                parent._executor,
                target_id=data.get("targetId") or parent.target_id,
                frame_id=frame_id,
                parent_frame_id=parent.frame_id,
            )

        return parent._execute(Command("frame", {"selector": selector}, decode=decode))
