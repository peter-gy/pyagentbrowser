from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from agentbrowser.contracts.protocol import optional
from agentbrowser.features.tabs.models import TabInfo


def _tab_selector(
    *,
    id: str | None = None,
    index: int | None = None,
    required: bool = False,
) -> str | Any:
    selected = [value is not None for value in (id, index)]
    if sum(selected) == 0:
        if required:
            raise ValueError("pass one of id or index")
        return optional(None)
    if sum(selected) > 1:
        raise ValueError("pass exactly one of id or index")
    if index is not None:
        if index < 0:
            raise ValueError("index must be non-negative")
        return f"t{index}"
    return cast(str, id)


def _tab_with_label(tabs: Sequence[TabInfo], label: str) -> TabInfo | None:
    return next((tab for tab in tabs if tab.label == label), None)
