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
    configured = native_session or factory(
        session=session_config.session_id,
        restore=session_config.restore,
        namespace=session_config.namespace,
        default_timeout_ms=session_config._timeout_ms(),
        allowed_domains=session_config._allowed_domains(),
        engine=launch_configuration.engine,
        action_policy=session_config.action_policy,
        confirm_actions=session_config.confirm_actions,
        no_auto_dialog=not session_config.auto_dialogs,
        pin_tab=session_config.pin_tab,
        dashboard=session_config.dashboard,
    )
    if native_session is not None and session_config.allowed_domains:
        configured.set_allowed_domains(session_config._allowed_domains())
    default_session_config = SessionOptions()
    if native_session is not None and session_config.namespace is not None:
        raise ValueError("namespace must be set on NativeSession when native_session is supplied")
    if native_session is not None and session_config.session_id is not None:
        raise ValueError("session_id must be set on NativeSession when native_session is supplied")
    if native_session is not None and session_config.restore is not None:
        raise ValueError("restore must be set on NativeSession when native_session is supplied")
    if native_session is not None and session_config.timeout != default_session_config.timeout:
        raise ValueError(
            "default_timeout_ms must be set on NativeSession when native_session is supplied"
        )
    if native_session is not None and session_config.action_policy is not None:
        raise ValueError(
            "action_policy must be set on NativeSession when native_session is supplied"
        )
    if native_session is not None and session_config.confirm_actions:
        raise ValueError(
            "confirm_actions must be set on NativeSession when native_session is supplied"
        )
    if native_session is not None and session_config.pin_tab is not None:
        raise ValueError("pin_tab must be set on NativeSession when native_session is supplied")
    if (
        native_session is not None
        and session_config.auto_dialogs != default_session_config.auto_dialogs
    ):
        raise ValueError(
            "no_auto_dialog must be set on NativeSession when native_session is supplied"
        )
    if native_session is not None and session_config.dashboard is not None:
        raise ValueError("dashboard must be set on NativeSession when native_session is supplied")
    return configured
