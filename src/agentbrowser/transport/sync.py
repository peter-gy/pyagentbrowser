from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import replace
from itertools import count
from pathlib import Path
from typing import Any, Protocol, cast

import agentbrowser._native as _native
from agentbrowser._native import NativeBrowser, NativeCancellation
from agentbrowser.contracts.actions import INTERNAL_SHUTDOWN_ACTION
from agentbrowser.contracts.errors import BrowserError
from agentbrowser.contracts.execution import command_parameters
from agentbrowser.contracts.protocol import OMIT, BrowserResponse, response_data_mapping
from agentbrowser.contracts.types import JSONMapping, JSONObject, JSONValue
from agentbrowser.features.session.models import DashboardOptions, RestoreOptions
from agentbrowser.transport.policy import DomainAllowlist
from agentbrowser.transport.responses import (
    PendingConfirmation,
    _checked_response,
    _filter_confirmed_response,
    _response_from_mapping,
    _try_unwrap_confirmed_response,
)

DEFAULT_TIMEOUT_MS = 15_000


def _validate_restore_allowlist(
    restore: RestoreOptions | None,
    allowed_domains: str | None,
) -> None:
    if restore is not None and not DomainAllowlist(allowed_domains).is_empty:
        raise ValueError(
            "allowed_domains cannot be combined with restore because saved origins can replay "
            "before containment starts"
        )


class NativeEngine(Protocol):
    """Protocol implemented by the PyO3 native browser wrapper."""

    def execute_json(self, command_json: str) -> str: ...


def _native_options_json(**options: Any) -> str:
    return json.dumps(
        {key: _jsonable(value) for key, value in options.items() if value is not None}
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
        pin_tab: bool | None = None,
        dashboard: bool | DashboardOptions | None = False,
        native: NativeEngine | None = None,
    ) -> None:
        _validate_restore_allowlist(restore, allowed_domains)
        self._restore = restore
        self._native = native
        self._native_started = native is not None
        self._pin_tab = pin_tab
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
        """Discard pending confirmation context."""
        self._pending_confirmations.clear()

    def command(self, action: str, **params: Any) -> JSONValue:
        """Run a native command and return checked response data."""
        response = self.execute(action, **params)
        return _checked_response(action, response).data

    def execute(
        self, action: str, *, _cancellation: NativeCancellation | None = None, **params: Any
    ) -> BrowserResponse:
        """Run a native command and return the full response envelope."""
        if action not in {"close", INTERNAL_SHUTDOWN_ACTION}:
            params = command_parameters(params)
        params.pop("_executionDeadline", None)
        command = self.build_command(action, **params)
        prepared = self._allowlist.prepare(command)
        pending_confirmation = self._consume_pending_confirmation(prepared.command)
        try:
            native = self._ensure_native()
            if _cancellation is not None and isinstance(native, _native.NativeBrowser):
                raw_json = native.execute_json(json.dumps(prepared.command), _cancellation)
            else:
                raw_json = native.execute_json(json.dumps(prepared.command))
        except Exception:
            self._restore_pending_confirmation(prepared.command, pending_confirmation)
            raise

        try:
            raw = json.loads(raw_json)
            if not isinstance(raw, dict):
                raise BrowserError(action, "native response was not an object", {"response": raw})
            response = _response_from_mapping(
                action=action,
                command_id=prepared.command["id"],
                raw=raw,
            )
        except json.JSONDecodeError as err:
            self._restore_pending_confirmation(prepared.command, pending_confirmation)
            raise BrowserError(
                action,
                f"native response was not valid JSON: {err}",
                {"response": raw_json},
            ) from err
        except Exception:
            self._restore_pending_confirmation(prepared.command, pending_confirmation)
            raise

        if not response.success:
            self._restore_pending_confirmation(prepared.command, pending_confirmation)
            return response

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

        confirmation_pending = self._record_pending_confirmation(
            response,
            prepared.command,
            prepared.policy,
            inherited=pending_confirmation,
        )
        if not confirmation_pending:
            next_policy = prepared.policy.finish(prepared.command)
            if action == "confirm" and pending_confirmation is not None:
                confirmed = _try_unwrap_confirmed_response(response)
                if confirmed.success:
                    next_policy = pending_confirmation.policy.finish(pending_confirmation.command)
            self._allowlist = next_policy

        return response

    def _ensure_native(self) -> NativeEngine:
        if self._native is None:
            self._native = NativeBrowser(_native_options_json(**self._native_options))
            self._native_started = True
        return self._native

    def build_command(self, action: str, **params: Any) -> JSONObject:
        """Build the JSON command object sent to the native engine."""
        command: JSONObject = {"id": f"py{next(self._ids)}", "action": action}
        command.update(_restore_command_fields(self._restore))
        if self._pin_tab is not None:
            command["pinTab"] = self._pin_tab
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

    def _restore_pending_confirmation(
        self,
        command: Mapping[str, Any],
        pending: PendingConfirmation | None,
    ) -> None:
        confirmation_id = command.get("confirmation_id")
        if pending is not None and confirmation_id is not None:
            self._pending_confirmations[str(confirmation_id)] = pending

    def _record_pending_confirmation(
        self,
        response: BrowserResponse,
        command: JSONObject,
        policy: DomainAllowlist,
        *,
        inherited: PendingConfirmation | None = None,
    ) -> bool:
        data = response_data_mapping(response)
        raw = response.raw
        if data is None:
            return False
        if not bool(data.get("confirmation_required")):
            if command.get("action") != "confirm":
                return False
            result = data.get("result")
            action = data.get("action")
            if not isinstance(result, Mapping) or not isinstance(action, str):
                return False
            nested = _response_from_mapping(
                action=action,
                command_id=response.id,
                raw=cast(Mapping[str, Any], result),
            )
            nested_data = response_data_mapping(nested)
            if (
                not nested.success
                or nested_data is None
                or not bool(nested_data.get("confirmation_required"))
            ):
                return False
            data = nested_data
            raw = nested.raw

        confirmation_id = data.get("confirmation_id") or raw.get("id") or response.id
        self._pending_confirmations[str(confirmation_id)] = inherited or PendingConfirmation(
            command=dict(command),
            policy=policy,
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
