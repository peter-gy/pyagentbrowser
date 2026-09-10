from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from agentbrowser.contracts.protocol import optional


def accessibility_audit_params(
    url: str | None = None,
    *,
    tags: Sequence[str] = (),
    selector: str | None = None,
) -> dict[str, Any]:
    if isinstance(tags, (str, bytes)):
        raise TypeError("tags must be a sequence of strings")
    normalized_tags: list[str] = []
    for tag in tags:
        if not isinstance(tag, str):
            raise TypeError("tags must contain strings")
        normalized = tag.strip()
        if not normalized or "," in normalized:
            raise ValueError("tags must contain non-empty axe tag names")
        normalized_tags.append(normalized)
    return {
        "url": optional(url),
        "tags": optional(",".join(normalized_tags) or None),
        "selector": optional(selector),
    }
