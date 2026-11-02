from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from agentbrowser.contracts.decode import (
    nullable_string,
    optional_flag,
    optional_string,
    required_bool,
    required_string,
)
from agentbrowser.contracts.errors import NativeParseError
from agentbrowser.features.tabs.models import TabCloseResult, TabInfo, TabSwitchResult


def tabs_from_data(data: Mapping[str, Any]) -> tuple[TabInfo, ...]:
    raw_tabs = data.get("tabs")
    if not isinstance(raw_tabs, list):
        raise NativeParseError("TabInfo collection field 'tabs' must be an array")
    if any(not isinstance(item, Mapping) for item in raw_tabs):
        raise NativeParseError("TabInfo collection entries must be objects")
    return tuple(_tab_info(cast(Mapping[str, Any], item)) for item in raw_tabs)


def tab_from_data(data: Mapping[str, Any]) -> TabInfo:
    """Decode `tab_new`, which activates the new tab and reports its title after navigation."""
    action = "tab_new"
    return TabInfo(
        id=required_string(data, "tabId", action=action),
        url=required_string(data, "url", action=action),
        title=optional_string(data, "title", action=action) or "",
        label=nullable_string(data, "label", action=action),
        active=True,
        target_id=required_string(data, "targetId", action=action),
        raw=data,
    )


def tab_switch_from_data(data: Mapping[str, Any]) -> TabSwitchResult:
    action = "tab_switch"
    return TabSwitchResult(
        id=required_string(data, "tabId", action=action),
        url=required_string(data, "url", action=action),
        title=required_string(data, "title", action=action),
        label=nullable_string(data, "label", action="tab_switch"),
        revived=optional_flag(data, "revived", model="TabSwitchResult"),
        dialog_blocked=optional_flag(
            data,
            "dialogBlocked",
            model="TabSwitchResult",
        ),
        target_id=required_string(data, "targetId", action=action),
        raw=data,
    )


def tab_close_result_from_data(data: Mapping[str, Any]) -> TabCloseResult:
    closed = required_bool(data, "closed", action="tab_close")
    if not closed:
        raise NativeParseError("tab_close field 'closed' must be true")
    return TabCloseResult(
        id=required_string(data, "tabId", action="tab_close"),
        label=optional_string(data, "label", action="tab_close"),
        closed=closed,
        active_tab_revived=optional_flag(
            data,
            "activeTabRevived",
            model="TabCloseResult",
        ),
        target_id=optional_string(data, "targetId", action="tab_close"),
        raw=data,
    )


def _tab_info(raw: Mapping[str, Any]) -> TabInfo:
    action = "tab_list"
    return TabInfo(
        id=required_string(raw, "tabId", action=action),
        url=required_string(raw, "url", action=action),
        title=required_string(raw, "title", action=action),
        label=nullable_string(raw, "label", action=action),
        active=required_bool(raw, "active", action=action),
        target_id=required_string(raw, "targetId", action=action),
        raw=raw,
    )
