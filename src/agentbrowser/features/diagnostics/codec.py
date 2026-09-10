from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from agentbrowser.contracts.decode import (
    first_present,
    nullable_string,
    optional_int,
    required_int,
    required_string,
)
from agentbrowser.contracts.errors import NativeParseError
from agentbrowser.features.diagnostics.models import (
    AccessibilityAudit,
    AccessibilityCounts,
    AccessibilityIssue,
    AccessibilityNode,
    AccessibilityTargetPart,
    ConsoleMessage,
)


def accessibility_audit_from_data(data: Mapping[str, Any]) -> AccessibilityAudit:
    action = "a11y"
    raw_counts = data.get("counts")
    if not isinstance(raw_counts, Mapping):
        raise NativeParseError("a11y field 'counts' must be an object")
    return AccessibilityAudit(
        url=required_string(data, "url", action=action),
        axe_version=nullable_string(data, "axeVersion", action=action),
        counts=AccessibilityCounts(
            violations=required_int(raw_counts, "violations", action=action),
            incomplete=required_int(raw_counts, "incomplete", action=action),
            passes=required_int(raw_counts, "passes", action=action),
            inapplicable=required_int(raw_counts, "inapplicable", action=action),
        ),
        violations=_accessibility_issues(data, "violations"),
        incomplete=_accessibility_issues(data, "incomplete"),
        raw=data,
    )


def console_messages_from_data(data: Mapping[str, Any]) -> tuple[ConsoleMessage, ...]:
    raw_messages = next(
        (data[field] for field in ("messages", "logs", "entries") if field in data),
        None,
    )
    if not isinstance(raw_messages, list):
        raise NativeParseError("ConsoleMessage collection must be an array")
    if any(not isinstance(item, Mapping) for item in raw_messages):
        raise NativeParseError("ConsoleMessage collection entries must be objects")
    return tuple(_console_message(cast(Mapping[str, Any], item)) for item in raw_messages)


def _console_message(raw: Mapping[str, Any]) -> ConsoleMessage:
    type_value = first_present(raw, "type", "kind", "level", model="ConsoleMessage", field="type")
    text_value = first_present(raw, "text", "message", model="ConsoleMessage", field="text")
    return ConsoleMessage(
        type=str(type_value),
        text=str(text_value),
        level=str(raw["level"]) if raw.get("level") is not None else None,
        url=str(raw["url"]) if raw.get("url") is not None else None,
        line=optional_int(raw.get("line") or raw.get("lineNumber")),
        column=optional_int(raw.get("column") or raw.get("columnNumber")),
        raw=raw,
    )


def _accessibility_issues(
    data: Mapping[str, Any],
    field: str,
) -> tuple[AccessibilityIssue, ...]:
    value = data.get(field)
    if not isinstance(value, list) or any(not isinstance(item, Mapping) for item in value):
        raise NativeParseError(f"a11y field '{field}' must be an array of objects")
    return tuple(_accessibility_issue(cast(Mapping[str, Any], item)) for item in value)


def _accessibility_issue(raw: Mapping[str, Any]) -> AccessibilityIssue:
    action = "a11y"
    raw_tags = raw.get("tags")
    if not isinstance(raw_tags, list) or any(not isinstance(tag, str) for tag in raw_tags):
        raise NativeParseError("a11y issue field 'tags' must be an array of strings")
    raw_nodes = raw.get("nodes")
    if not isinstance(raw_nodes, list) or any(not isinstance(node, Mapping) for node in raw_nodes):
        raise NativeParseError("a11y issue field 'nodes' must be an array of objects")
    return AccessibilityIssue(
        id=required_string(raw, "id", action=action),
        impact=required_string(raw, "impact", action=action),
        help=required_string(raw, "help", action=action),
        help_url=required_string(raw, "helpUrl", action=action),
        tags=tuple(cast(list[str], raw_tags)),
        node_count=required_int(raw, "nodeCount", action=action),
        nodes=tuple(_accessibility_node(cast(Mapping[str, Any], node)) for node in raw_nodes),
        raw=raw,
    )


def _accessibility_node(raw: Mapping[str, Any]) -> AccessibilityNode:
    target = raw.get("target")
    if not isinstance(target, list):
        raise NativeParseError("a11y node field 'target' must be an array")
    return AccessibilityNode(
        target=tuple(_accessibility_target_part(part) for part in target),
        html=required_string(raw, "html", action="a11y"),
        failure_summary=required_string(raw, "failureSummary", action="a11y"),
        raw=raw,
    )


def _accessibility_target_part(value: Any) -> AccessibilityTargetPart:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return tuple(_accessibility_target_part(part) for part in value)
    raise NativeParseError("a11y node target entries must be strings or arrays")
