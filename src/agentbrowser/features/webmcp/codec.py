from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast, get_args

from agentbrowser.contracts.decode import (
    optional_mapping,
    optional_string,
    required_int,
    required_string,
)
from agentbrowser.contracts.errors import NativeParseError
from agentbrowser.features.webmcp.models import WebMCPInvocation, WebMCPInvocationStatus, WebMCPTool

_WEBMCP_INVOCATION_STATUSES = frozenset(get_args(WebMCPInvocationStatus))


def webmcp_tools_from_data(data: Mapping[str, Any]) -> tuple[WebMCPTool, ...]:
    """Decode the native `webmcp_list` result."""
    action = "webmcp_list"
    raw_tools = data.get("tools")
    if not isinstance(raw_tools, list):
        raise NativeParseError(f"{action} field 'tools' must be an array")
    tools: list[WebMCPTool] = []
    for raw_tool in raw_tools:
        if not isinstance(raw_tool, Mapping):
            raise NativeParseError(f"{action} field 'tools' must contain objects")
        backend_node_id = raw_tool.get("backendNodeId")
        if backend_node_id is not None and (
            isinstance(backend_node_id, bool) or not isinstance(backend_node_id, int)
        ):
            raise NativeParseError(f"{action} field 'backendNodeId' must be an integer or null")
        tools.append(
            WebMCPTool(
                name=required_string(raw_tool, "name", action=action),
                description=required_string(raw_tool, "description", action=action),
                input_schema=optional_mapping(raw_tool, "inputSchema", action=action),
                annotations=optional_mapping(raw_tool, "annotations", action=action),
                origin=required_string(raw_tool, "origin", action=action),
                frame_id=required_string(raw_tool, "frameId", action=action),
                backend_node_id=backend_node_id,
                raw=raw_tool,
            )
        )
    return tuple(tools)


def webmcp_invocation_from_data(data: Mapping[str, Any]) -> WebMCPInvocation:
    """Decode a native WebMCP invocation result."""
    action = "webmcp invocation"
    status = required_string(data, "status", action=action)
    if status not in _WEBMCP_INVOCATION_STATUSES:
        raise NativeParseError(f"{action} field 'status' has unknown value '{status}'")
    output_truncated = data.get("outputTruncated", False)
    if not isinstance(output_truncated, bool):
        raise NativeParseError(f"{action} field 'outputTruncated' must be a boolean")
    original_output_bytes = data.get("originalOutputBytes")
    if original_output_bytes is not None and (
        isinstance(original_output_bytes, bool) or not isinstance(original_output_bytes, int)
    ):
        raise NativeParseError(f"{action} field 'originalOutputBytes' must be an integer or null")
    return WebMCPInvocation(
        invocation_id=required_string(data, "invocationId", action=action),
        tool_name=required_string(data, "toolName", action=action),
        frame_id=required_string(data, "frameId", action=action),
        origin=required_string(data, "origin", action=action),
        status=cast(WebMCPInvocationStatus, status),
        duration_ms=required_int(data, "durationMs", action=action),
        raw_status=optional_string(data, "rawStatus", action=action),
        output=data.get("output"),
        output_truncated=output_truncated,
        original_output_bytes=original_output_bytes,
        error=optional_string(data, "error", action=action),
        raw=data,
    )
