from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from agentbrowser.contracts.decode import (
    first_mapping,
    first_present,
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
    raw = first_mapping(data, "tab", "page") or data
    return _tab_info(raw)


def tab_switch_from_data(data: Mapping[str, Any]) -> TabSwitchResult:
    tab = _tab_info(data)
    return TabSwitchResult(
        id=tab.id,
        url=tab.url,
        title=required_string(data, "title", action="tab_switch"),
        label=nullable_string(data, "label", action="tab_switch"),
        revived=optional_flag(data, "revived", model="TabSwitchResult"),
        dialog_blocked=optional_flag(
            data,
            "dialogBlocked",
            model="TabSwitchResult",
        ),
        target_id=tab.target_id,
        raw=tab.raw,
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
    id_value = first_present(raw, "id", "tabId", "targetId", model="TabInfo", field="id")
    url_value = first_present(raw, "url", model="TabInfo", field="url")
    if not isinstance(id_value, str):
        raise NativeParseError("TabInfo field 'id' must be a string")
    if not isinstance(url_value, str):
        raise NativeParseError("TabInfo field 'url' must be a string")
    title = raw.get("title", "")
    if not isinstance(title, str):
        raise NativeParseError("TabInfo field 'title' must be a string")
    active = False
    for field_name in ("active", "selected", "current"):
        if field_name not in raw:
            continue
        value = raw[field_name]
        if not isinstance(value, bool):
            raise NativeParseError(f"TabInfo field '{field_name}' must be a boolean")
        active = active or value
    return TabInfo(
        id=id_value,
        url=url_value,
        title=title,
        label=optional_string(raw, "label", action="TabInfo"),
        active=active,
        target_id=optional_string(raw, "targetId", action="TabInfo"),
        raw=raw,
    )
