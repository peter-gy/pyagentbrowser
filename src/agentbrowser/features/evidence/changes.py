from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from difflib import SequenceMatcher, unified_diff
from typing import Any, Generic, Literal

from agentbrowser.contracts.errors import AgentBrowserError
from agentbrowser.contracts.types import RefT, SnapshotT
from agentbrowser.features.evidence.models import SnapshotData


@dataclass(frozen=True, slots=True)
class SnapshotDiff:
    """Parsed snapshot diff result."""

    text: str
    additions: int
    removals: int
    unchanged: int
    changed: bool
    raw: Mapping[str, Any]

    def __str__(self) -> str:
        return self.text

    def __repr__(self) -> str:
        return (
            f"SnapshotDiff(changed={self.changed!r}, additions={self.additions!r}, "
            f"removals={self.removals!r}, unchanged={self.unchanged!r})"
        )


@dataclass(frozen=True, slots=True)
class ActionResult(Generic[RefT, SnapshotT]):
    """Before/after evidence for an agent action."""

    action: str
    target: RefT
    before: SnapshotT
    after: SnapshotT
    diff: SnapshotDiff

    def __repr__(self) -> str:
        return (
            f"ActionResult(action={self.action!r}, target={self.target!r}, "
            f"before={self.before!r}, after={self.after!r}, diff={self.diff!r})"
        )


class ActionTransitionError(AgentBrowserError, Generic[RefT, SnapshotT]):
    """Raised after an action succeeds but transition evidence cannot complete."""

    def __init__(
        self,
        *,
        action: str,
        target: RefT,
        stage: Literal["wait", "snapshot", "diff"],
        before: SnapshotT,
        after: SnapshotT | None,
        cause: BaseException,
    ) -> None:
        super().__init__(f"{action} completed, then {stage} failed: {cause}")
        self.action = action
        self.target = target
        self.stage = stage
        self.before = before
        self.after = after
        self.cause = cause


def diff_snapshot_data(before: SnapshotData, after: SnapshotData) -> SnapshotDiff:
    """Compare two captured snapshots without reading live browser state again."""
    before_lines = [f"origin: {before.origin}", *before.text.splitlines()]
    after_lines = [f"origin: {after.origin}", *after.text.splitlines()]
    additions = 0
    removals = 0
    unchanged = 0
    for tag, before_start, before_end, after_start, after_end in SequenceMatcher(
        None,
        before_lines,
        after_lines,
        autojunk=False,
    ).get_opcodes():
        if tag == "equal":
            unchanged += before_end - before_start
        elif tag == "insert":
            additions += after_end - after_start
        elif tag == "delete":
            removals += before_end - before_start
        else:
            removals += before_end - before_start
            additions += after_end - after_start
    text = "\n".join(
        unified_diff(
            before_lines,
            after_lines,
            fromfile="before",
            tofile="after",
            lineterm="",
        )
    )
    return SnapshotDiff(
        text=text,
        additions=additions,
        removals=removals,
        unchanged=unchanged,
        changed=before_lines != after_lines,
        raw={
            "before": before.text,
            "after": after.text,
            "beforeOrigin": before.origin,
            "afterOrigin": after.origin,
        },
    )
