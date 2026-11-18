from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from agentbrowser.contracts.errors import BrowserError
from agentbrowser.contracts.types import JSONValue

FlowWriteKind = Literal["explicit", "suspected"]


FlowTier = Literal["http", "page", "replay"]


FlowStatus = Literal[
    "auth_expired",
    "credential_not_sendable",
    "request_signed",
    "rate_limited",
    "blocked",
    "outcome_unknown",
    "write_applied",
    "address_refused",
    "drifted",
]


@dataclass(frozen=True, slots=True)
class FlowStep:
    """One command recorded by the session's flow capture."""

    seq: int
    command: str
    url: str | None
    requests: int
    ok: bool
    saved: bool
    raw: Mapping[str, Any] = field(default_factory=dict, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class FlowRecording:
    """Commands recorded since capture started and how many a save has covered."""

    steps: tuple[FlowStep, ...]
    last_save: int
    unsaved: int
    raw: Mapping[str, Any] = field(default_factory=dict, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class FlowRequest:
    """One request a saved flow sends, with its `{{param}}` slots in the URL."""

    id: str
    method: str
    url: str
    bytes: int
    raw: Mapping[str, Any] = field(default_factory=dict, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class FlowWrite:
    """Request of a saved flow that changes state on the site."""

    id: str
    method: str
    url: str
    kind: FlowWriteKind
    step: int
    raw: Mapping[str, Any] = field(default_factory=dict, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class FlowGap:
    """Recorded command a saved flow cannot reproduce over HTTP, with the reason."""

    step: int
    command: str
    reason: str
    raw: Mapping[str, Any] = field(default_factory=dict, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class SavedFlow:
    """Report for a flow written to disk by `flows.save()`."""

    name: str
    origin: str
    step_count: int
    requests: tuple[FlowRequest, ...]
    output: str
    params: tuple[str, ...]
    detected_params: tuple[Mapping[str, Any], ...]
    references: tuple[Mapping[str, Any], ...]
    writes: tuple[FlowWrite, ...]
    gaps: tuple[FlowGap, ...]
    dropped_headers: tuple[str, ...]
    verified: bool
    path: Path
    from_step: int
    to_step: int
    reach_note: str | None = None
    raw: Mapping[str, Any] = field(default_factory=dict, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class FlowFallback:
    """Earlier tier that failed for a request before another tier answered."""

    tier: FlowTier
    error: str
    raw: Mapping[str, Any] = field(default_factory=dict, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class FlowRunStep:
    """One request a flow run sent and the tier that answered it."""

    id: str
    step: int
    tier: FlowTier
    status: int
    duration_ms: int
    fell_back: tuple[FlowFallback, ...] = ()
    raw: Mapping[str, Any] = field(default_factory=dict, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class FlowDrift:
    """Tier that saw a response shape differ from the recording during a run."""

    tier: FlowTier
    step: int
    reason: str
    raw: Mapping[str, Any] = field(default_factory=dict, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class FlowRun:
    """Result of a flow run, with the output request's JSON body in `data`."""

    name: str
    origin: str
    verified: bool
    duration_ms: int
    steps: tuple[FlowRunStep, ...]
    data: JSONValue
    empty: bool = False
    drift: FlowDrift | None = None
    save_error: str | None = None
    raw: Mapping[str, Any] = field(default_factory=dict, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class FlowSummary:
    """Saved flow as `flows.list()` describes it, in the shape of a tool definition."""

    name: str
    origin: str
    valid: bool
    params: tuple[str, ...]
    examples: Mapping[str, str]
    description: str
    input_schema: Mapping[str, Any]
    param_sources: Mapping[str, str]
    item_fields: tuple[str, ...]
    recorded_on: str
    provenance: str
    verified_at: str | None
    raw: Mapping[str, Any] = field(default_factory=dict, compare=False, repr=False)


class FlowRunError(BrowserError):
    """Raised when a flow run stops on a site condition the engine reports as a status."""

    def __init__(
        self,
        message: str,
        response: Mapping[str, Any],
        *,
        status: FlowStatus,
        flow: str,
        step: int,
        http_status: int | None = None,
        retry_after: str | None = None,
        save_error: str | None = None,
    ) -> None:
        super().__init__("flow_run", message, response, code=status)
        self.status: FlowStatus = status
        self.flow = flow
        self.step = step
        self.http_status = http_status
        self.retry_after = retry_after
        self.save_error = save_error
