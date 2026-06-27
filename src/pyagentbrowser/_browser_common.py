from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol, TypeAlias, cast

from pyagentbrowser.models import ActionConfirmationRequired, BrowserResponse, SnapshotDiff

CDP_INVALIDATING_ACTIONS = frozenset(
    {
        "navigate",
        "setcontent",
        "back",
        "forward",
        "reload",
        "tab_switch",
        "tab_close",
    }
)
STALE_REF_ERROR_CODES = frozenset({"stale_ref", "unknown_ref"})
INTERNAL_SHUTDOWN_ACTION = "__agent_browser_internal_shutdown"


class PendingActionHandle(Protocol):
    """Confirmation handle accepted by sync and async confirmation APIs."""

    confirmation_id: str


ConfirmationTarget: TypeAlias = ActionConfirmationRequired | PendingActionHandle | str


def normalize_url(url: str) -> str:
    lowered = url.lower()
    if lowered.startswith(
        (
            "http://",
            "https://",
            "about:",
            "data:",
            "file:",
            "chrome-extension://",
            "chrome://",
        )
    ):
        return url
    return f"https://{url}"


def confirmation_id(confirmation: ConfirmationTarget | None) -> str | None:
    if isinstance(confirmation, ActionConfirmationRequired):
        return confirmation.confirmation_id
    if confirmation is None or isinstance(confirmation, str):
        return confirmation
    return confirmation.confirmation_id


def response_confirmation_id(response: BrowserResponse) -> str | None:
    confirmation = None
    if isinstance(response.data, Mapping):
        data = cast(Mapping[str, Any], response.data)
        confirmation = data.get("confirmation_id")
    confirmation = confirmation or response.raw.get("id")
    return str(confirmation) if confirmation is not None else None


def response_data_mapping(response: BrowserResponse) -> Mapping[str, Any] | None:
    if isinstance(response.data, Mapping):
        return cast(Mapping[str, Any], response.data)
    return None


def action_sets_launched(action: str) -> bool:
    return action in {"launch", "navigate"}


def action_closes_browser(action: str) -> bool:
    return action in {"close", INTERNAL_SHUTDOWN_ACTION}


def action_clears_pending_confirmation(action: str) -> bool:
    return action in {"close", "confirm", "deny", INTERNAL_SHUTDOWN_ACTION}


def action_invalidates_cdp(action: str) -> bool:
    return action in CDP_INVALIDATING_ACTIONS


def snapshot_diff_from_data(data: Mapping[str, Any]) -> SnapshotDiff:
    return SnapshotDiff(
        text=str(data.get("diff", "")),
        additions=int(data.get("additions", 0)),
        removals=int(data.get("removals", 0)),
        unchanged=int(data.get("unchanged", 0)),
        changed=bool(data.get("changed", False)),
        raw=data,
    )


def validate_screenshot_wait_ms(wait_ms: int) -> None:
    if wait_ms < 0:
        raise ValueError("wait_ms must be greater than or equal to 0")


def is_stale_ref_error_code(code: str | None) -> bool:
    return code in STALE_REF_ERROR_CODES


def exclusive_source(
    label: str,
    *,
    inline: str | None,
    path: str | Path | None,
) -> str:
    if inline is None and path is None:
        raise ValueError(f"{label} requires either script=... or path=...")
    if inline is not None and path is not None:
        raise ValueError(f"{label} accepts script=... or path=..., not both")
    if path is not None:
        return Path(path).read_text()
    return str(inline)
