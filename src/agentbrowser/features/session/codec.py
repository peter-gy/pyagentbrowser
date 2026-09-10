from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast, get_args

from agentbrowser.contracts.decode import (
    nullable_int,
    nullable_string,
    optional_string,
    required_bool,
    required_int,
    required_string,
)
from agentbrowser.contracts.errors import NativeParseError
from agentbrowser.features.session.models import (
    CloseResult,
    RestoreSave,
    RestoreSaveStatus,
    RestoreStatus,
    SessionStatus,
)

_RESTORE_STATUSES = frozenset(get_args(RestoreStatus))


_RESTORE_SAVE_STATUSES = frozenset(get_args(RestoreSaveStatus))


def _restore_status(data: Mapping[str, Any], *, action: str) -> RestoreStatus:
    value = required_string(data, "restoreStatus", action=action)
    if value not in _RESTORE_STATUSES:
        raise NativeParseError(f"{action} field 'restoreStatus' has unknown value '{value}'")
    return cast(RestoreStatus, value)


def _save_status(data: Mapping[str, Any], *, action: str) -> RestoreSaveStatus:
    value = required_string(data, "saveStatus", action=action)
    if value not in _RESTORE_SAVE_STATUSES:
        raise NativeParseError(f"{action} field 'saveStatus' has unknown value '{value}'")
    return cast(RestoreSaveStatus, value)


def session_status_from_data(data: Mapping[str, Any]) -> SessionStatus:
    """Decode the native `session_info` result."""
    action = "session_info"
    restore_save = required_string(data, "restoreSave", action=action)
    if restore_save not in {"auto", "always", "never"}:
        raise NativeParseError(
            "session_info field 'restoreSave' must be 'auto', 'always', or 'never'"
        )
    restore_loaded_path = nullable_string(data, "restoreLoadedPath", action=action)
    restore_saved_path = nullable_string(data, "restoreSavedPath", action=action)
    return SessionStatus(
        session_id=required_string(data, "session", action=action),
        namespace=nullable_string(data, "namespace", action=action),
        socket_dir=Path(required_string(data, "socketDir", action=action)),
        background_pid=required_int(data, "backgroundPid", action=action),
        browser_launched=required_bool(data, "browserLaunched", action=action),
        page_count=required_int(data, "pageCount", action=action),
        engine=required_string(data, "engine", action=action),
        launch_hash=nullable_int(data, "launchHash", action=action),
        compatibility_status=required_string(data, "compatibilityStatus", action=action),
        restore_key=nullable_string(data, "restoreKey", action=action),
        restore_status=_restore_status(data, action=action),
        restore_status_detail=nullable_string(data, "restoreStatusDetail", action=action),
        restore_loaded_path=(
            Path(restore_loaded_path) if restore_loaded_path is not None else None
        ),
        restore_validation_pending=required_bool(data, "restoreValidationPending", action=action),
        restore_save=cast(RestoreSave, restore_save),
        save_status=_save_status(data, action=action),
        restore_saved_path=(Path(restore_saved_path) if restore_saved_path is not None else None),
        restore_check_url=nullable_string(data, "restoreCheckUrl", action=action),
        restore_check_text=nullable_string(data, "restoreCheckText", action=action),
        restore_check_fn=nullable_string(data, "restoreCheckFn", action=action),
        raw=data,
    )


def close_result_from_data(data: Mapping[str, Any]) -> CloseResult:
    """Decode the native close result."""
    action = "close"
    closed = required_bool(data, "closed", action=action)
    if not closed:
        raise NativeParseError("close field 'closed' must be true")
    state_path = optional_string(data, "statePath", action=action)
    return CloseResult(
        closed=closed,
        restore_status=_restore_status(data, action=action),
        save_status=_save_status(data, action=action),
        state_path=Path(state_path) if state_path is not None else None,
        save_error=optional_string(data, "saveError", action=action),
        raw=data,
    )
