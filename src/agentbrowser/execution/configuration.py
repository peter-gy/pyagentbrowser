from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeVar

from agentbrowser.launch import LaunchConfiguration, SessionOptions, normalize_session


class ConfigurableSession(Protocol):
    def set_allowed_domains(self, allowed_domains: str | None) -> None: ...


S = TypeVar("S", bound=ConfigurableSession)


def configure_session(
    launch_configuration: LaunchConfiguration,
    session: SessionOptions | None,
    native_session: S | None,
    factory: Callable[..., S],
) -> S:
    session_config = normalize_session(session)
    if native_session is None:
        return factory(
            session=session_config.session_id,
            restore=session_config.restore,
            namespace=session_config.namespace,
            default_timeout_ms=session_config._timeout_ms(),
            allowed_domains=session_config._allowed_domains(),
            engine=launch_configuration.options.engine,
            action_policy=session_config.action_policy,
            confirm_actions=session_config.confirm_actions,
            no_auto_dialog=not session_config.auto_dialogs,
            pin_tab=session_config.pin_tab,
            dashboard=session_config.dashboard,
        )
    if session_config.allowed_domains:
        native_session.set_allowed_domains(session_config._allowed_domains())
    defaults = SessionOptions()
    # A supplied native session already fixed these at construction.
    session_owned = {
        "namespace": session_config.namespace is not None,
        "session_id": session_config.session_id is not None,
        "restore": session_config.restore is not None,
        "default_timeout_ms": session_config.timeout != defaults.timeout,
        "action_policy": session_config.action_policy is not None,
        "confirm_actions": bool(session_config.confirm_actions),
        "pin_tab": session_config.pin_tab is not None,
        "no_auto_dialog": session_config.auto_dialogs != defaults.auto_dialogs,
        "dashboard": session_config.dashboard is not None,
    }
    for option, requested in session_owned.items():
        if requested:
            raise ValueError(
                f"{option} must be set on NativeSession when native_session is supplied"
            )
    return native_session
