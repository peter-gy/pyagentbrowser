from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from agentbrowser.contracts.errors import ConfirmationRequired
from agentbrowser.features.evidence.changes import (
    ActionResult,
    ActionTransitionError,
    diff_snapshot_data,
)
from agentbrowser.features.evidence.waiting import _apply_async_wait as _apply_wait
from agentbrowser.features.evidence.waits import Wait

if TYPE_CHECKING:
    from agentbrowser.features.evidence.ref_async import AsyncRef
    from agentbrowser.features.evidence.snapshots import AsyncSnapshot


async def transition(
    ref: AsyncRef, action: str, run: Callable[[], Awaitable[object]], *, wait: Wait | None
) -> ActionResult[AsyncRef, AsyncSnapshot]:
    try:
        await run()
    except ConfirmationRequired as error:
        if error.pending is not None:
            error.pending = error.pending.map(lambda _value: _result(ref, action, wait=wait))
        raise
    return await _result(ref, action, wait=wait)


async def _result(
    ref: AsyncRef, action: str, *, wait: Wait | None
) -> ActionResult[AsyncRef, AsyncSnapshot]:
    try:
        await _apply_wait(ref.document, wait)
    except ConfirmationRequired as error:
        if error.pending is not None:
            error.pending = error.pending.map(lambda _value: _capture_result(ref, action))
        raise
    except Exception as cause:
        raise ActionTransitionError(
            action=action, target=ref, stage="wait", before=ref.snapshot, after=None, cause=cause
        ) from cause
    return await _capture_result(ref, action)


async def _capture_result(ref: AsyncRef, action: str) -> ActionResult[AsyncRef, AsyncSnapshot]:
    try:
        after = await ref.snapshot.refresh()
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


def _finish_result(
    ref: AsyncRef, action: str, after: AsyncSnapshot
) -> ActionResult[AsyncRef, AsyncSnapshot]:
    try:
        diff = diff_snapshot_data(ref.snapshot._data, after._data)
    except Exception as cause:
        raise ActionTransitionError(
            action=action, target=ref, stage="diff", before=ref.snapshot, after=after, cause=cause
        ) from cause
    return ActionResult(action=action, target=ref, before=ref.snapshot, after=after, diff=diff)
