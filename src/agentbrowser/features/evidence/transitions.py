from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from agentbrowser.contracts.errors import ConfirmationRequired
from agentbrowser.features.evidence.changes import (
    ActionResult,
    ActionTransitionError,
    diff_snapshot_data,
)
from agentbrowser.features.evidence.waiting import _apply_wait
from agentbrowser.features.evidence.waits import Wait

if TYPE_CHECKING:
    from agentbrowser.features.evidence.ref import Ref
    from agentbrowser.features.evidence.snapshots import Snapshot


def transition(
    ref: Ref, action: str, run: Callable[[], object], *, wait: Wait | None
) -> ActionResult[Ref, Snapshot]:
    try:
        run()
    except ConfirmationRequired as error:
        if error.pending is not None:
            error.pending = error.pending.map(lambda _value: _result(ref, action, wait=wait))
        raise
    return _result(ref, action, wait=wait)


def _result(ref: Ref, action: str, *, wait: Wait | None) -> ActionResult[Ref, Snapshot]:
    try:
        _apply_wait(ref.document, wait)
    except ConfirmationRequired as error:
        if error.pending is not None:
            error.pending = error.pending.map(lambda _value: _capture_result(ref, action))
        raise
    except Exception as cause:
        raise ActionTransitionError(
            action=action, target=ref, stage="wait", before=ref.snapshot, after=None, cause=cause
        ) from cause
    return _capture_result(ref, action)


def _capture_result(ref: Ref, action: str) -> ActionResult[Ref, Snapshot]:
    try:
        after = ref.snapshot.refresh()
    except ConfirmationRequired as error:
        if error.pending is not None:
            error.pending = error.pending.map(
                lambda captured: _finish_result(ref, action, captured)
            )
        raise
    except Exception as cause:
        raise ActionTransitionError(
            action=action,
            target=ref,
            stage="snapshot",
            before=ref.snapshot,
            after=None,
            cause=cause,
        ) from cause
    return _finish_result(ref, action, after)


def _finish_result(ref: Ref, action: str, after: Snapshot) -> ActionResult[Ref, Snapshot]:
    try:
        diff = diff_snapshot_data(ref.snapshot._data, after._data)
    except Exception as cause:
        raise ActionTransitionError(
            action=action, target=ref, stage="diff", before=ref.snapshot, after=after, cause=cause
        ) from cause
    return ActionResult(action=action, target=ref, before=ref.snapshot, after=after, diff=diff)
