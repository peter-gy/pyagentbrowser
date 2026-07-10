from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from itertools import count
from pathlib import Path
from typing import Any, Protocol, cast

from agentbrowser._allowlist import DomainAllowlist
from agentbrowser._native import NativeBrowser
from agentbrowser.models import (
    OMIT,
    BrowserError,
    BrowserResponse,
    ConfirmationRequired,
    DashboardOptions,
    JSONMapping,
    JSONObject,
    JSONValue,
    RestoreOptions,
)

DEFAULT_TIMEOUT_MS = 15_000


@dataclass(frozen=True, slots=True)
class PendingConfirmation:
    command: JSONObject
    policy: DomainAllowlist
    cleanup_paths: tuple[Path, ...] = ()

    def cleanup(self) -> None:
        for path in self.cleanup_paths:
            path.unlink(missing_ok=True)


class NativeEngine(Protocol):
    """Protocol implemented by the PyO3 native browser wrapper."""

    def execute_json(self, command_json: str) -> str: ...


def _native_options_json(**options: Any) -> str:
    return json.dumps(
        {key: _jsonable(value) for key, value in options.items() if value is not None}
    )


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


class NativeSession:
    """Stable Python boundary around the native agent-browser JSON protocol."""

    def __init__(
        self,
        *,
        session: str | None = None,
        restore: RestoreOptions | None = None,
        namespace: str | None = None,
        default_timeout_ms: int | None = DEFAULT_TIMEOUT_MS,
        allowed_domains: str | None = None,
        engine: str | None = None,
        action_policy: str | Path | None = None,
        confirm_actions: Sequence[str] | None = None,
        no_auto_dialog: bool = False,
        dashboard: bool | DashboardOptions | None = False,
        native: NativeEngine | None = None,
    ) -> None:
        self._restore = restore
        self._native = native
        self._native_started = native is not None
        self._native_options: dict[str, Any] = {
            "session": session,
            "restore_key": restore.key if restore is not None else None,
            "restore_save": restore.save if restore is not None else None,
            "autosave_interval_ms": (restore.autosave_interval_ms if restore is not None else None),
            "restore_check_url": restore.check_url if restore is not None else None,
            "restore_check_text": restore.check_text if restore is not None else None,
            "restore_check_fn": restore.check_fn if restore is not None else None,
            "namespace": namespace,
            "default_timeout_ms": default_timeout_ms,
            "allowed_domains": allowed_domains,
            "engine": engine,
            "action_policy": str(action_policy) if action_policy is not None else None,
            "confirm_actions": list(confirm_actions) if confirm_actions is not None else None,
            "no_auto_dialog": no_auto_dialog,
            "dashboard": _dashboard_options(dashboard),
        }
        self._ids = count(1)
        self._allowlist = DomainAllowlist(allowed_domains)
        self._pending_confirmations: dict[str, PendingConfirmation] = {}

    @property
    def started(self) -> bool:
        """Whether the native engine has been constructed."""
        return self._native_started

    def set_allowed_domains(self, allowed_domains: str | None) -> None:
        """Replace the Python-side domain allowlist for this session."""
        self._allowlist = DomainAllowlist(allowed_domains)
        if not self._native_started:
            self._native_options["allowed_domains"] = allowed_domains

    def discard_pending_confirmations(self) -> None:
        """Release resources retained by pending confirmations."""
        pending = tuple(self._pending_confirmations.values())
        self._pending_confirmations.clear()
        for confirmation in pending:
            confirmation.cleanup()

    def command(self, action: str, **params: Any) -> JSONValue:
        """Run a native command and return checked response data."""
        response = self.execute(action, **params)
        return _checked_response(action, response).data

    def execute(self, action: str, **params: Any) -> BrowserResponse:
        """Run a native command and return the full response envelope."""
        command = self.build_command(action, **params)
        prepared = self._allowlist.prepare(command)
        pending_confirmation = self._consume_pending_confirmation(prepared.command)
        retain_prepared = False
        try:
            raw_json = self._ensure_native().execute_json(json.dumps(prepared.command))
            try:
                raw = json.loads(raw_json)
            except json.JSONDecodeError as err:
                raise BrowserError(
                    action,
                    f"native response was not valid JSON: {err}",
                    {"response": raw_json},
                ) from err

            if not isinstance(raw, dict):
                raise BrowserError(action, "native response was not an object", {"response": raw})

            response = _response_from_mapping(
                action=action,
                command_id=prepared.command["id"],
                raw=raw,
            )
            if response.success:
                response = _filter_confirmed_response(
                    response,
                    prepared.policy,
                    pending_confirmation,
                )
                filtered_data = prepared.policy.filter_successful_response(
                    prepared.command,
                    response.data,
                )
                if filtered_data is not response.data:
                    response = replace(
                        response,
                        data=filtered_data,
                        raw=cast(JSONMapping, {**response.raw, "data": filtered_data}),
                    )
                self._allowlist = prepared.policy.finish(prepared.command)
                retain_prepared = self._record_pending_confirmation(
                    response,
                    prepared.command,
                    prepared.policy,
                    prepared.cleanup_paths,
                )
            return response
        finally:
            if pending_confirmation is not None:
                pending_confirmation.cleanup()
            if not retain_prepared:
                prepared.cleanup()

    def _ensure_native(self) -> NativeEngine:
        if self._native is None:
            self._native = NativeBrowser(_native_options_json(**self._native_options))
            self._native_started = True
        return self._native

    def build_command(self, action: str, **params: Any) -> JSONObject:
        """Build the JSON command object sent to the native engine."""
        command: JSONObject = {"id": f"py{next(self._ids)}", "action": action}
        command.update(_restore_command_fields(self._restore))
        command.update(
            {key: _jsonable(value) for key, value in params.items() if value is not OMIT}
        )
        return command

    def _consume_pending_confirmation(
        self,
        command: Mapping[str, Any],
    ) -> PendingConfirmation | None:
        action = command.get("action")
        if action not in {"confirm", "deny"}:
            return None
        confirmation_id = command.get("confirmation_id")
        if confirmation_id is None:
            return None
        return self._pending_confirmations.pop(str(confirmation_id), None)

    def _record_pending_confirmation(
        self,
        response: BrowserResponse,
        command: JSONObject,
        policy: DomainAllowlist,
        cleanup_paths: tuple[Path, ...] = (),
    ) -> bool:
        data = _response_data_mapping(response)
        if data is None or not bool(data.get("confirmation_required")):
            return False
        confirmation_id = data.get("confirmation_id") or response.raw.get("id") or response.id
        previous = self._pending_confirmations.pop(str(confirmation_id), None)
        if previous is not None:
            previous.cleanup()
        self._pending_confirmations[str(confirmation_id)] = PendingConfirmation(
            command=dict(command),
            policy=policy,
            cleanup_paths=cleanup_paths,
        )
        return True


def _jsonable(value: Any) -> JSONValue:
    if value is OMIT:
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items() if item is not OMIT}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_jsonable(item) for item in value if item is not OMIT]
    return value


def _dashboard_options(value: bool | DashboardOptions | None) -> JSONValue:
    if value is None or value is False:
        return None
    if value is True:
        return True
    if isinstance(value, DashboardOptions):
        return {"enabled": True, "port": value.port, "cli_version": value.cli_version}
    raise TypeError("dashboard must be a bool or DashboardOptions")


def _restore_command_fields(restore: RestoreOptions | None) -> dict[str, str]:
    if restore is None:
        return {}
    fields: dict[str, str] = {"restoreKey": restore.key}
    if restore.save is not None:
        fields["restoreSave"] = restore.save
    if restore.check_url is not None:
        fields["restoreCheckUrl"] = restore.check_url
    if restore.check_text is not None:
        fields["restoreCheckText"] = restore.check_text
    if restore.check_fn is not None:
        fields["restoreCheckFn"] = restore.check_fn
    return fields


def _checked_response(action: str, response: BrowserResponse) -> BrowserResponse:
    if not response.success:
        message = str(response.raw.get("error", "unknown native error"))
        raise BrowserError(action, message, response.raw)
    data = _response_data_mapping(response)
    if data is not None and bool(data.get("confirmation_required")):
        raise ConfirmationRequired(action, data, response.raw)
    if action == "confirm":
        return _unwrap_confirmed_response(response)
    return response


def _response_data_mapping(response: BrowserResponse) -> JSONMapping | None:
    if isinstance(response.data, Mapping):
        return cast(JSONMapping, response.data)
    return None


def _filter_confirmed_response(
    response: BrowserResponse,
    policy: DomainAllowlist,
    pending_confirmation: PendingConfirmation | None = None,
) -> BrowserResponse:
    data = _response_data_mapping(response)
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
    if pending_confirmation is not None and pending_confirmation.command.get("action") == action:
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
    data = _response_data_mapping(response)
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
    unwrapped_data = _response_data_mapping(unwrapped)
    if unwrapped_data is not None and bool(unwrapped_data.get("confirmation_required")):
        raise ConfirmationRequired(confirmed_action, unwrapped_data, result)
    return unwrapped


def _try_unwrap_confirmed_response(response: BrowserResponse) -> BrowserResponse:
    data = _response_data_mapping(response)
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
