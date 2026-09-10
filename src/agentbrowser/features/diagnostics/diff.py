from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentbrowser.contracts.protocol import optional, path_value
from agentbrowser.execution.commands import AsyncExecutor, Command, Executor
from agentbrowser.features.evidence.changes import SnapshotDiff
from agentbrowser.features.evidence.codec import snapshot_diff_from_data


@dataclass(frozen=True, slots=True)
class Diff:
    """Snapshot diff helpers."""

    executor: Executor

    def snapshot(
        self,
        baseline: str | Path | None = None,
        *,
        selector: str | None = None,
        compact: bool = False,
        max_depth: int | None = None,
    ) -> SnapshotDiff:
        """Compare the current snapshot with a baseline."""
        return self.executor.execute(
            Command(
                "diff_snapshot",
                {
                    "baseline": optional(
                        path_value(baseline) if isinstance(baseline, Path) else baseline
                    ),
                    "selector": optional(selector),
                    "compact": compact,
                    "maxDepth": optional(max_depth),
                },
                decode=_snapshot_diff,
            )
        )


@dataclass(frozen=True, slots=True)
class AsyncDiff:
    """Async snapshot diff helpers."""

    executor: AsyncExecutor

    async def snapshot(
        self,
        baseline: str | Path | None = None,
        *,
        selector: str | None = None,
        compact: bool = False,
        max_depth: int | None = None,
    ) -> SnapshotDiff:
        """Compare the current snapshot with a baseline."""
        return await self.executor.execute(
            Command(
                "diff_snapshot",
                {
                    "baseline": optional(
                        path_value(baseline) if isinstance(baseline, Path) else baseline
                    ),
                    "selector": optional(selector),
                    "compact": compact,
                    "maxDepth": optional(max_depth),
                },
                decode=_snapshot_diff,
            )
        )


def _snapshot_diff(data: Mapping[str, Any]) -> SnapshotDiff:
    return snapshot_diff_from_data(data)
