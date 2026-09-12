from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any, cast

from agentbrowser.contracts.errors import BrowserError, ConfirmationRequired
from agentbrowser.contracts.protocol import BrowserResponse, response_data_mapping
from agentbrowser.contracts.types import JSONMapping, JSONObject, JSONValue
from agentbrowser.transport.policy import DomainAllowlist


@dataclass(frozen=True, slots=True)
class PendingConfirmation:
    command: JSONObject
    policy: DomainAllowlist


def _response_from_mapping(
    *,
    action: str,
    command_id: object,
    raw: Mapping[str, Any],
) -> BrowserResponse:
    success = raw.get("success")
    if not isinstance(success, bool):
        raise BrowserError(action, "native response success was not a boolean", raw)
    data: JSONValue = raw.get("data", {})
    warning = raw.get("warning")
    return BrowserResponse(
        id=str(raw.get("id", command_id)),
        action=action,
        success=success,
        data=data,
        raw=cast(JSONMapping, raw),
        warning=str(warning) if warning is not None else None,
    )


def _checked_response(action: str, response: BrowserResponse) -> BrowserResponse:
    if not response.success:
        message = str(response.raw.get("error", "unknown native error"))
        raise BrowserError(action, message, response.raw)
    data = response_data_mapping(response)
    if data is not None and bool(data.get("confirmation_required")):
        raise ConfirmationRequired(action, data, response.raw)
    if action == "confirm":
        return _unwrap_confirmed_response(response)
    return response


def _filter_confirmed_response(
    response: BrowserResponse,
    policy: DomainAllowlist,
    pending_confirmation: PendingConfirmation | None = None,
) -> BrowserResponse:
    data = response_data_mapping(response)
    if data is None:
        return response

    action = data.get("action")
    result = data.get("result")
    if not isinstance(action, str) or not isinstance(result, Mapping):
        return response

    nested = _response_from_mapping(
        action=action,
        command_id=response.id,
        raw=cast(Mapping[str, Any], result),
    )
    if not nested.success:
        return response

    filter_policy = pending_confirmation.policy if pending_confirmation is not None else policy
    filter_command = cast(JSONObject, {"id": response.id, "action": action})
    if pending_confirmation is not None:
        filter_command = pending_confirmation.command

    filtered_data = filter_policy.filter_successful_response(
        filter_command,
        nested.data,
    )
    if filtered_data is nested.data:
        return response

    filtered_result = {**cast(Mapping[str, Any], result), "data": filtered_data}
    filtered_outer_data = {**data, "result": filtered_result}
    return replace(
        response,
        data=filtered_outer_data,
        raw=cast(JSONMapping, {**response.raw, "data": filtered_outer_data}),
    )


def _require_response_data_mapping(
    response: BrowserResponse,
    *,
    action: str | None = None,
) -> JSONMapping:
    data = response_data_mapping(response)
    if data is None:
        raise BrowserError(
            action or response.action,
            "native response data was not an object. Use "
            'native.data(..., expect="any") for arbitrary JSON data',
            response.raw,
        )
    return data


def _unwrap_confirmed_response(response: BrowserResponse) -> BrowserResponse:
    data = _require_response_data_mapping(response, action="confirm")
    result = data.get("result")
    if not isinstance(result, Mapping):
        raise BrowserError(
            "confirm",
            "native confirm response did not include a nested result",
            response.raw,
        )

    result = cast(Mapping[str, Any], result)
    confirmed_action = str(data.get("action", "confirm"))
    unwrapped = _response_from_mapping(
        action=confirmed_action,
        command_id=response.id,
        raw=result,
    )
    if not unwrapped.success:
        message = str(result.get("error", "confirmed action failed"))
        raise BrowserError(confirmed_action, message, result)
    unwrapped_data = response_data_mapping(unwrapped)
    if unwrapped_data is not None and bool(unwrapped_data.get("confirmation_required")):
        raise ConfirmationRequired(confirmed_action, unwrapped_data, result)
    return unwrapped


def _try_unwrap_confirmed_response(response: BrowserResponse) -> BrowserResponse:
    data = response_data_mapping(response)
    result = data.get("result") if data is not None else None
    if not isinstance(result, Mapping):
        return BrowserResponse(
            id=response.id,
            action="confirm",
            success=False,
            data={},
            raw={
                "id": response.id,
                "success": False,
                "error": "native confirm response did not include a nested result",
                "response": response.raw,
            },
        )

    return _response_from_mapping(
        action=str(data.get("action", "confirm") if data is not None else "confirm"),
        command_id=response.id,
        raw=cast(Mapping[str, Any], result),
    )
