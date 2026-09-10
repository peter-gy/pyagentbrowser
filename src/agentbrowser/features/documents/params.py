from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from agentbrowser.contracts.protocol import OMIT, optional
from agentbrowser.features.documents.models import WaitSelectorState
from agentbrowser.features.documents.read import ReadMode


def scroll_params(
    direction: str | None = None,
    amount: float | None = None,
    *,
    selector: str | None = None,
    x: float | None = None,
    y: float | None = None,
) -> dict[str, Any]:
    return {
        "direction": optional(direction),
        "amount": optional(amount),
        "selector": optional(selector),
        "x": optional(x),
        "y": optional(y),
    }


def wait_params(
    milliseconds: int | None = None,
    *,
    selector: str | None = None,
    text: str | None = None,
    url: str | None = None,
    predicate: str | None = None,
    load_state: str | None = None,
    state: WaitSelectorState = "visible",
    timeout_ms: int | None = None,
) -> dict[str, Any]:
    return {
        "selector": optional(selector),
        "text": optional(text),
        "url": optional(url),
        "function": optional(predicate),
        "loadState": optional(load_state),
        "state": state,
        "timeout": optional(milliseconds if milliseconds is not None else timeout_ms),
    }


def read_params(
    url: str | None = None,
    *,
    mode: ReadMode | None = None,
    filter: str | None = None,
    timeout_ms: int | None = None,
    headers: Mapping[str, str] | None = None,
    allowed_domains: Sequence[str] | None = None,
) -> dict[str, Any]:
    mode = mode or ReadMode()
    if timeout_ms is not None and timeout_ms <= 0:
        raise ValueError("timeout_ms must be greater than 0")
    return {
        "url": optional(url),
        "raw": mode.raw,
        "requireMd": mode.require_markdown,
        "llms": optional(mode.llms),
        "outline": mode.outline,
        "filter": optional(filter),
        "timeout": optional(timeout_ms),
        "headers": dict(headers) if headers is not None else OMIT,
        "allowedDomains": list(allowed_domains) if allowed_domains is not None else OMIT,
    }
