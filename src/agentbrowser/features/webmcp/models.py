from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from agentbrowser.contracts.types import JSONValue

WebMCPInvocationStatus = Literal["pending", "completed", "canceled", "failed", "timed_out"]


@dataclass(frozen=True, slots=True)
class WebMCPTool:
    """Tool exposed by the active page through WebMCP."""

    name: str
    description: str
    input_schema: Mapping[str, Any]
    annotations: Mapping[str, Any]
    origin: str
    frame_id: str
    backend_node_id: int | None = None
    raw: Mapping[str, Any] = field(default_factory=dict, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class WebMCPInvocation:
    """Current result and lifecycle state for one WebMCP tool invocation."""

    invocation_id: str
    tool_name: str
    frame_id: str
    origin: str
    status: WebMCPInvocationStatus
    duration_ms: int
    raw_status: str | None = None
    output: JSONValue | None = None
    output_truncated: bool = False
    original_output_bytes: int | None = None
    error: str | None = None
    raw: Mapping[str, Any] = field(default_factory=dict, compare=False, repr=False)
