from __future__ import annotations

from dataclasses import replace
from time import monotonic
from typing import cast

from agentbrowser.contracts.errors import ConfirmationRequired
from agentbrowser.execution.commands import Command
from agentbrowser.features.documents.base import _Document
from agentbrowser.features.documents.base_async import _AsyncDocument
from agentbrowser.features.documents.models import LoadState
from agentbrowser.features.documents.params import wait_params
from agentbrowser.features.evidence.waits import Wait


def _apply_wait(browser: _Document, wait: Wait | None) -> None:
    if wait is None:
        return
    if wait.kind == "all":
        _apply_waits(browser, wait.conditions, timeout_ms=wait.timeout_ms)
        return
    browser._execute(
        Command(
            "wait",
            {
                **wait_params(
                    None,
                    text=wait.value if wait.kind == "text" else None,
                    url=wait.value if wait.kind == "url" else None,
                    load_state=cast(LoadState, wait.value) if wait.kind == "load" else None,
                    timeout_ms=wait.timeout_ms,
                )
            },
            decode=lambda _data: None,
        )
    )


def _apply_waits(
    browser: _Document,
    conditions: tuple[Wait, ...],
    *,
    timeout_ms: int | None = None,
) -> None:
    deadline = None if timeout_ms is None else monotonic() + timeout_ms / 1000
    for index, condition in enumerate(conditions):
        if deadline is not None:
            remaining_ms = max(0, int((deadline - monotonic()) * 1000))
            condition = replace(
                condition,
                timeout_ms=(
                    remaining_ms
                    if condition.timeout_ms is None
                    else min(condition.timeout_ms, remaining_ms)
                ),
            )
        try:
            _apply_wait(browser, condition)
        except ConfirmationRequired as error:
            remaining = conditions[index + 1 :]
            if remaining and error.pending is not None:
                error.pending = error.pending.map(
                    lambda _value, remaining=remaining: _apply_waits(
                        browser,
                        remaining,
                        timeout_ms=(
                            None
                            if deadline is None
                            else max(0, int((deadline - monotonic()) * 1000))
                        ),
                    )
                )
            raise


async def _apply_async_wait(browser: _AsyncDocument, wait: Wait | None) -> None:
    if wait is None:
        return
    if wait.kind == "all":
        await _apply_async_waits(browser, wait.conditions, timeout_ms=wait.timeout_ms)
        return
    await browser._execute(
        Command(
            "wait",
            {
                **wait_params(
                    None,
                    text=wait.value if wait.kind == "text" else None,
                    url=wait.value if wait.kind == "url" else None,
                    load_state=cast(LoadState, wait.value) if wait.kind == "load" else None,
                    timeout_ms=wait.timeout_ms,
                )
            },
            decode=lambda _data: None,
        )
    )


async def _apply_async_waits(
    browser: _AsyncDocument,
    conditions: tuple[Wait, ...],
    *,
    timeout_ms: int | None = None,
) -> None:
    deadline = None if timeout_ms is None else monotonic() + timeout_ms / 1000
    for index, condition in enumerate(conditions):
        if deadline is not None:
            remaining_ms = max(0, int((deadline - monotonic()) * 1000))
            condition = replace(
                condition,
                timeout_ms=(
                    remaining_ms
                    if condition.timeout_ms is None
                    else min(condition.timeout_ms, remaining_ms)
                ),
            )
        try:
            await _apply_async_wait(browser, condition)
        except ConfirmationRequired as error:
            remaining = conditions[index + 1 :]
            if remaining and error.pending is not None:
                error.pending = error.pending.map(
                    lambda _value, remaining=remaining: _apply_async_waits(
                        browser,
                        remaining,
                        timeout_ms=(
                            None
                            if deadline is None
                            else max(0, int((deadline - monotonic()) * 1000))
                        ),
                    )
                )
            raise
