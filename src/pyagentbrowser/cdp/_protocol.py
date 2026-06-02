from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import Any, cast

from pyagentbrowser.cdp.errors import CDPEvaluationError, CDPProtocolError


def _decode_message(raw: str | bytes) -> Mapping[str, Any]:
    text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    try:
        message = json.loads(text)
    except json.JSONDecodeError as err:
        raise CDPProtocolError("CDP receive", f"invalid JSON: {err}") from err
    if not isinstance(message, Mapping):
        raise CDPProtocolError("CDP receive", "message was not an object")
    return cast(Mapping[str, Any], message)


def _response_result(method: str, response: Mapping[str, Any]) -> Mapping[str, Any]:
    error = response.get("error")
    if error is not None:
        raise CDPProtocolError(method, error)
    result = response.get("result")
    if result is None:
        return {}
    if not isinstance(result, Mapping):
        raise CDPProtocolError(method, "response result was not an object")
    return cast(Mapping[str, Any], result)


def _runtime_evaluate_value(data: Mapping[str, Any]) -> Any:
    exception_details = data.get("exceptionDetails")
    if isinstance(exception_details, Mapping):
        raise CDPEvaluationError(cast(Mapping[str, Any], exception_details))
    result = data.get("result")
    if not isinstance(result, Mapping):
        return None
    if "value" in result:
        return result["value"]
    unserializable = result.get("unserializableValue")
    if isinstance(unserializable, str):
        return _unserializable_value(unserializable)
    if result.get("type") == "undefined":
        return None
    return result.get("description")


def _unserializable_value(value: str) -> Any:
    if value == "NaN":
        return math.nan
    if value == "Infinity":
        return math.inf
    if value == "-Infinity":
        return -math.inf
    if value == "-0":
        return -0.0
    return value


def _is_stale_context_error(err: CDPProtocolError) -> bool:
    return "context" in str(err.error).lower() and (
        "not found" in str(err.error).lower() or "cannot find" in str(err.error).lower()
    )
