from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from agentbrowser.contracts.errors import AgentBrowserError

RestoreSave = Literal["auto", "always", "never"]


RestoreStatus = Literal[
    "load_failed",
    "loaded",
    "loaded_but_invalid",
    "missing",
    "not_configured",
    "pending",
]


RestoreSaveStatus = Literal[
    "disabled",
    "error",
    "invalid_policy",
    "no_browser",
    "not_attempted",
    "not_configured",
    "saved",
    "skipped_restore_failed",
]


SessionIdScope = Literal["worktree", "cwd", "git-root"]


_MAX_U64 = (1 << 64) - 1


@dataclass(frozen=True, slots=True)
class RestoreOptions:
    """State restore policy for a native browser session."""

    key: str
    save: RestoreSave | None = None
    autosave_interval_ms: int | None = None
    check_url: str | None = None
    check_text: str | None = None
    check_fn: str | None = None

    def __post_init__(self) -> None:
        if not _is_valid_session_component(self.key):
            raise ValueError(
                f"Invalid restore key '{self.key}'. Only alphanumeric characters, "
                "hyphens, and underscores are allowed."
            )
        if self.save is not None and self.save not in {"auto", "always", "never"}:
            raise ValueError("save must be 'auto', 'always', or 'never'")
        if self.autosave_interval_ms is not None:
            if isinstance(self.autosave_interval_ms, bool) or not isinstance(
                self.autosave_interval_ms, int
            ):
                raise TypeError("autosave_interval_ms must be an integer")
            if not 0 <= self.autosave_interval_ms <= _MAX_U64:
                raise ValueError(f"autosave_interval_ms must be between 0 and {_MAX_U64}")


@dataclass(frozen=True, slots=True)
class SessionStatus:
    """Current native session, browser, and restore lifecycle state."""

    session_id: str
    namespace: str | None
    socket_dir: Path
    background_pid: int
    browser_launched: bool
    page_count: int
    engine: str
    launch_hash: int | None
    compatibility_status: str
    restore_key: str | None
    restore_status: RestoreStatus
    restore_status_detail: str | None
    restore_loaded_path: Path | None
    restore_validation_pending: bool
    restore_save: RestoreSave
    save_status: RestoreSaveStatus
    restore_saved_path: Path | None
    restore_check_url: str | None
    restore_check_text: str | None
    restore_check_fn: str | None
    raw: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class CloseResult:
    """Terminal browser state returned by `Browser.close()`."""

    closed: bool
    restore_status: RestoreStatus | None = None
    save_status: RestoreSaveStatus | None = None
    state_path: Path | None = None
    save_error: str | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return (
            f"CloseResult(closed={self.closed!r}, restore_status={self.restore_status!r}, "
            f"save_status={self.save_status!r}, state_path={self.state_path!r}, "
            f"save_error={self.save_error!r})"
        )


class RestoreSaveError(AgentBrowserError):
    """Raised after browser cleanup when restore-state persistence fails."""

    def __init__(self, result: CloseResult) -> None:
        self.result = result
        detail = result.save_error or "unknown restore-state save failure"
        super().__init__(f"browser closed with a restore-state save error: {detail}")


def _is_valid_session_component(value: str) -> bool:
    return bool(value) and all(char.isalnum() or char in {"-", "_"} for char in value)


@dataclass(frozen=True, slots=True)
class DashboardOptions:
    """Options for opt-in upstream dashboard observability.

    Parameters
    ----------
    port
        Dashboard port, or `0` to request an ephemeral port.
    cli_version
        Expected upstream CLI version for dashboard compatibility checks.
    """

    port: int | None = None
    cli_version: str | None = None

    def __post_init__(self) -> None:
        if self.port is not None and not 0 <= self.port <= 65535:
            raise ValueError("dashboard port must be between 0 and 65535")
        if self.cli_version is not None and not self.cli_version.strip():
            raise ValueError("dashboard cli_version must not be empty")


@dataclass(frozen=True, slots=True)
class SessionId:
    """Stable session id derived from a filesystem scope."""

    session: str
    scope: SessionIdScope
    path: str
    hash: str

    def __str__(self) -> str:
        return self.session
