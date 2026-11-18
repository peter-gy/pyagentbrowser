from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast, get_args

from agentbrowser.contracts.decode import (
    nullable_string,
    optional_flag,
    optional_int_field,
    optional_mapping,
    optional_string,
    required_bool,
    required_int,
    required_objects,
    required_string,
    string_mapping,
    string_tuple,
)
from agentbrowser.contracts.errors import BrowserError, ConfirmationRequired, NativeParseError
from agentbrowser.features.flows.models import (
    FlowDrift,
    FlowFallback,
    FlowGap,
    FlowRecording,
    FlowRequest,
    FlowRun,
    FlowRunError,
    FlowRunStep,
    FlowStatus,
    FlowStep,
    FlowSummary,
    FlowTier,
    FlowWrite,
    FlowWriteKind,
    SavedFlow,
)

_FLOW_TIERS = frozenset(get_args(FlowTier))


_FLOW_WRITE_KINDS = frozenset(get_args(FlowWriteKind))


_FLOW_STATUSES = frozenset(get_args(FlowStatus))


def _choice(data: Mapping[str, Any], field: str, choices: frozenset[str], *, action: str) -> str:
    value = required_string(data, field, action=action)
    if value not in choices:
        raise NativeParseError(f"{action} field '{field}' has unknown value '{value}'")
    return value


def _tier(data: Mapping[str, Any], *, action: str) -> FlowTier:
    return cast(FlowTier, _choice(data, "tier", _FLOW_TIERS, action=action))


def _required_mapping(data: Mapping[str, Any], field: str, *, action: str) -> Mapping[str, Any]:
    if field not in data:
        raise NativeParseError(f"{action} field '{field}' is required")
    return optional_mapping(data, field, action=action)


def flow_recording_from_data(data: Mapping[str, Any]) -> FlowRecording:
    """Decode the native `flow_steps` result."""
    action = "flow_steps"
    return FlowRecording(
        steps=tuple(
            FlowStep(
                seq=required_int(step, "seq", action=action),
                command=required_string(step, "command", action=action),
                url=nullable_string(step, "url", action=action),
                requests=required_int(step, "requests", action=action),
                ok=required_bool(step, "ok", action=action),
                saved=required_bool(step, "saved", action=action),
                raw=step,
            )
            for step in required_objects(data, "steps", action=action)
        ),
        last_save=required_int(data, "lastSave", action=action),
        unsaved=required_int(data, "unsaved", action=action),
        raw=data,
    )


def saved_flow_from_data(data: Mapping[str, Any]) -> SavedFlow:
    """Decode the native `flow_save` result."""
    action = "flow_save"
    return SavedFlow(
        name=required_string(data, "name", action=action),
        origin=required_string(data, "origin", action=action),
        step_count=required_int(data, "steps", action=action),
        requests=tuple(
            FlowRequest(
                id=required_string(request, "id", action=action),
                method=required_string(request, "method", action=action),
                url=required_string(request, "url", action=action),
                bytes=required_int(request, "bytes", action=action),
                raw=request,
            )
            for request in required_objects(data, "requests", action=action)
        ),
        output=required_string(data, "output", action=action),
        params=string_tuple(data, "params", action=action),
        detected_params=required_objects(data, "detectedParams", action=action),
        references=required_objects(data, "references", action=action),
        writes=tuple(
            FlowWrite(
                id=required_string(write, "id", action=action),
                method=required_string(write, "method", action=action),
                url=required_string(write, "url", action=action),
                kind=cast(FlowWriteKind, _choice(write, "kind", _FLOW_WRITE_KINDS, action=action)),
                step=required_int(write, "step", action=action),
                raw=write,
            )
            for write in required_objects(data, "writes", action=action)
        ),
        gaps=tuple(
            FlowGap(
                step=required_int(gap, "step", action=action),
                command=required_string(gap, "command", action=action),
                reason=required_string(gap, "reason", action=action),
                raw=gap,
            )
            for gap in required_objects(data, "gaps", action=action)
        ),
        dropped_headers=string_tuple(data, "droppedHeaders", action=action),
        verified=required_bool(data, "verified", action=action),
        path=Path(required_string(data, "path", action=action)),
        from_step=required_int(data, "from", action=action),
        to_step=required_int(data, "to", action=action),
        reach_note=optional_string(data, "reachNote", action=action),
        raw=data,
    )


def _flow_run_step(step: Mapping[str, Any], *, action: str) -> FlowRunStep:
    fell_back = required_objects(step, "fellBack", action=action) if "fellBack" in step else ()
    return FlowRunStep(
        id=required_string(step, "id", action=action),
        step=required_int(step, "step", action=action),
        tier=_tier(step, action=action),
        status=required_int(step, "status", action=action),
        duration_ms=required_int(step, "ms", action=action),
        fell_back=tuple(
            FlowFallback(
                tier=_tier(attempt, action=action),
                error=required_string(attempt, "error", action=action),
                raw=attempt,
            )
            for attempt in fell_back
        ),
        raw=step,
    )


def flow_run_from_data(data: Mapping[str, Any]) -> FlowRun:
    """Decode the native `flow_run` result."""
    action = "flow_run"
    if "data" not in data:
        raise NativeParseError(f"{action} field 'data' is required")
    drift = data.get("drift")
    if drift is not None and not isinstance(drift, Mapping):
        raise NativeParseError(f"{action} field 'drift' must be an object")
    return FlowRun(
        name=required_string(data, "name", action=action),
        origin=required_string(data, "origin", action=action),
        verified=required_bool(data, "verified", action=action),
        duration_ms=required_int(data, "ms", action=action),
        steps=tuple(
            _flow_run_step(step, action=action)
            for step in required_objects(data, "steps", action=action)
        ),
        data=data["data"],
        empty=optional_flag(data, "empty", model=action),
        drift=(
            FlowDrift(
                tier=_tier(drift, action=action),
                step=required_int(drift, "step", action=action),
                reason=required_string(drift, "reason", action=action),
                raw=drift,
            )
            if drift is not None
            else None
        ),
        save_error=optional_string(data, "saveError", action=action),
        raw=data,
    )


def flow_summaries_from_data(data: Mapping[str, Any]) -> tuple[FlowSummary, ...]:
    """Decode the native `flow_list` result."""
    action = "flow_list"
    return tuple(
        FlowSummary(
            name=required_string(flow, "name", action=action),
            origin=required_string(flow, "origin", action=action),
            valid=required_bool(flow, "valid", action=action),
            params=string_tuple(flow, "params", action=action),
            examples=string_mapping(flow, "examples", action=action),
            description=required_string(flow, "description", action=action),
            input_schema=_required_mapping(flow, "inputSchema", action=action),
            param_sources=string_mapping(flow, "paramSources", action=action),
            item_fields=string_tuple(flow, "itemFields", action=action),
            recorded_on=required_string(flow, "recordedOn", action=action),
            provenance=required_string(flow, "provenance", action=action),
            verified_at=nullable_string(flow, "verifiedAt", action=action),
            raw=flow,
        )
        for flow in required_objects(data, "flows", action=action)
    )


def flow_run_error(error: BaseException) -> BaseException:
    """Return `FlowRunError` for a failed run whose response carries the engine's stop data."""
    if not isinstance(error, BrowserError) or isinstance(
        error, ConfirmationRequired | FlowRunError
    ):
        return error
    data = error.response.get("data")
    if not isinstance(data, Mapping) or not isinstance(data.get("status"), str):
        return error
    action = "flow_run stop"
    try:
        return FlowRunError(
            str(error.response.get("error", "unknown native error")),
            error.response,
            status=cast(FlowStatus, _choice(data, "status", _FLOW_STATUSES, action=action)),
            flow=required_string(data, "flow", action=action),
            step=required_int(data, "step", action=action),
            http_status=optional_int_field(data, "httpStatus", action=action),
            retry_after=optional_string(data, "retryAfter", action=action),
            save_error=optional_string(data, "saveError", action=action),
        )
    except NativeParseError as parse_error:
        raise parse_error from error
