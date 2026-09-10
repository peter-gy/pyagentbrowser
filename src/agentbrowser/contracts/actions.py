from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, TypeAlias, cast

from agentbrowser.contracts.errors import ConfirmationRequired
from agentbrowser.contracts.protocol import BrowserResponse, response_data_mapping

CDP_URL_ACTIONS = frozenset({"a11y", "recording_start", "recording_restart"})


CDP_INVALIDATING_ACTIONS = frozenset(
    {
        "navigate",
        "setcontent",
        "back",
        "forward",
        "reload",
        "tab_new",
        "tab_switch",
        "tab_close",
        "window_new",
    }
)


STALE_REF_ERROR_CODES = frozenset({"stale_ref", "unknown_ref"})


INTERNAL_SHUTDOWN_ACTION = "__agent_browser_internal_shutdown"


class PendingActionHandle(Protocol):
    """Confirmation handle accepted by sync and async confirmation APIs."""

    confirmation_id: str


ConfirmationTarget: TypeAlias = ConfirmationRequired[Any] | PendingActionHandle | str


def confirmation_id(confirmation: ConfirmationTarget | None) -> str | None:
    if isinstance(confirmation, ConfirmationRequired):
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


def response_browser_launched(response: BrowserResponse) -> bool | None:
    data = response_data_mapping(response)
    lifecycle = data.get("lifecycle") if data is not None else None
    if not isinstance(lifecycle, Mapping):
        return None
    effective_launch = lifecycle.get("effectiveLaunch")
    if not isinstance(effective_launch, Mapping):
        return None
    browser_launched = effective_launch.get("browserLaunched")
    return browser_launched if isinstance(browser_launched, bool) else None


def action_sets_launched(action: str) -> bool:
    return action in {"launch", "navigate"}


def action_closes_browser(action: str) -> bool:
    return action in {"close", INTERNAL_SHUTDOWN_ACTION}


def action_clears_pending_confirmation(action: str) -> bool:
    return action in {"close", "confirm", "deny", INTERNAL_SHUTDOWN_ACTION}


def action_invalidates_cdp(
    action: str,
    params: Mapping[str, Any] | None = None,
) -> bool:
    if action in CDP_URL_ACTIONS:
        url = params.get("url") if params is not None else None
        return isinstance(url, str) and (action == "a11y" or bool(url))
    return action in CDP_INVALIDATING_ACTIONS


def action_resets_cdp(action: str) -> bool:
    return action in {"launch", "close", INTERNAL_SHUTDOWN_ACTION}


def is_stale_ref_error_code(code: str | None) -> bool:
    return code in STALE_REF_ERROR_CODES
