from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from agentbrowser.command_params import optional
from agentbrowser.models import (
    ColorScheme,
    DashboardOptions,
    ProxyConfig,
    RestoreOptions,
    path_value,
    paths_value,
    proxy_value,
)


@dataclass(frozen=True, slots=True)
class LaunchOptions:
    """Browser process options used by `Browser.launch(...)`."""

    headless: bool = True
    executable_path: str | Path | None = None
    engine: str | None = None
    profile: str | Path | None = None
    storage_state: str | Path | None = None
    extensions: Sequence[str | Path] = ()
    proxy: str | ProxyConfig | Mapping[str, Any] | None = None
    provider: str | None = None
    color_scheme: ColorScheme | None = None
    hide_scrollbars: bool | None = None
    args: Sequence[str] = ()
    allow_file_access: bool = False
    ignore_https_errors: bool = False
    user_agent: str | None = None
    download_path: str | Path | None = None

    def __post_init__(self) -> None:
        if isinstance(self.extensions, str):
            raise TypeError("extensions must be a sequence, not a string")
        if isinstance(self.args, str):
            raise TypeError("args must be a sequence, not a string")
        object.__setattr__(self, "extensions", tuple(self.extensions))
        object.__setattr__(self, "args", tuple(self.args))


@dataclass(frozen=True, slots=True)
class CDPTarget:
    """CDP attachment target used by `Browser.attach(...)`."""

    url: str | None = None
    port: int | None = None
    auto_connect: bool = True

    def __post_init__(self) -> None:
        if (self.url is None) == (self.port is None):
            raise ValueError("pass exactly one of url or port")
        if self.url is not None and not self.url.strip():
            raise ValueError("url must not be empty")
        if self.port is not None and not 1 <= self.port <= 65535:
            raise ValueError("port must be between 1 and 65535")


@dataclass(frozen=True, slots=True)
class SessionOptions:
    """Native session, restore, allowlist, and policy options for a browser."""

    session_id: str | None = None
    restore: RestoreOptions | None = None
    namespace: str | None = None
    timeout: float | None = 15.0
    allowed_domains: Sequence[str] = ()
    action_policy: str | Path | None = None
    confirm_actions: Sequence[str] = ()
    auto_dialogs: bool = True
    dashboard: DashboardOptions | None = None

    def __post_init__(self) -> None:
        if self.timeout is not None and self.timeout < 0:
            raise ValueError("timeout must be non-negative")
        if isinstance(self.allowed_domains, str):
            raise TypeError("allowed_domains must be a sequence, not a string")
        if isinstance(self.confirm_actions, str):
            raise TypeError("confirm_actions must be a sequence, not a string")
        domains = tuple(self.allowed_domains)
        actions = tuple(self.confirm_actions)
        if any(not domain.strip() for domain in domains):
            raise ValueError("allowed_domains entries must not be empty")
        if any(not action.strip() for action in actions):
            raise ValueError("confirm_actions entries must not be empty")
        if self.dashboard is not None and not isinstance(self.dashboard, DashboardOptions):
            raise TypeError("dashboard must be DashboardOptions")
        object.__setattr__(self, "allowed_domains", domains)
        object.__setattr__(self, "confirm_actions", actions)

    def _timeout_ms(self) -> int | None:
        return None if self.timeout is None else round(self.timeout * 1000)

    def _allowed_domains(self) -> str | None:
        return ",".join(self.allowed_domains) or None


def normalize_launch(options: LaunchOptions | None = None) -> LaunchOptions:
    """Return normalized browser process options."""
    if options is None:
        return LaunchOptions()
    if isinstance(options, LaunchOptions):
        return options
    raise TypeError("launch options must be LaunchOptions")


def cdp_target(target: CDPTarget) -> CDPTarget:
    """Return a normalized CDP attachment target."""
    if isinstance(target, CDPTarget):
        return target
    raise TypeError("attach target must be CDPTarget")


def normalize_session(
    options: SessionOptions | None = None,
) -> SessionOptions:
    """Return normalized browser session options."""
    if options is None:
        return SessionOptions()
    if isinstance(options, SessionOptions):
        return options
    raise TypeError("session options must be SessionOptions")


@dataclass(frozen=True, slots=True)
class LaunchConfiguration:
    """Normalized launch options shared by sync and async browser sessions.

    Instances store explicit process-launch or CDP-attach defaults.
    """

    headless: bool = True
    executable_path: str | None = None
    engine: str | None = None
    allowed_domains: str | None = None
    profile: str | None = None
    storage_state: str | None = None
    extensions: tuple[str, ...] = ()
    proxy: str | ProxyConfig | Mapping[str, Any] | None = None
    provider: str | None = None
    cdp_url: str | None = None
    cdp_port: int | None = None
    auto_connect: bool = False
    color_scheme: ColorScheme | None = None
    hide_scrollbars: bool | None = None
    args: tuple[str, ...] = ()
    allow_file_access: bool = False
    ignore_https_errors: bool = False
    user_agent: str | None = None
    download_path: str | None = None

    @classmethod
    def from_options(
        cls,
        *,
        headless: bool = True,
        executable_path: str | Path | None = None,
        engine: str | None = None,
        allowed_domains: str | None = None,
        profile: str | Path | None = None,
        storage_state: str | Path | None = None,
        extensions: Sequence[str | Path] = (),
        proxy: str | ProxyConfig | Mapping[str, Any] | None = None,
        provider: str | None = None,
        cdp_url: str | None = None,
        cdp_port: int | None = None,
        auto_connect: bool = False,
        color_scheme: ColorScheme | None = None,
        hide_scrollbars: bool | None = None,
        args: Sequence[str] = (),
        allow_file_access: bool = False,
        ignore_https_errors: bool = False,
        user_agent: str | None = None,
        download_path: str | Path | None = None,
    ) -> LaunchConfiguration:
        """Build a normalized launch configuration from public constructor options."""
        return cls(
            headless=headless,
            executable_path=path_value(executable_path),
            engine=engine,
            allowed_domains=allowed_domains,
            profile=path_value(profile),
            storage_state=path_value(storage_state),
            extensions=tuple(paths_value(extensions)),
            proxy=proxy,
            provider=provider,
            cdp_url=cdp_url,
            cdp_port=cdp_port,
            auto_connect=auto_connect,
            color_scheme=color_scheme,
            hide_scrollbars=hide_scrollbars,
            args=tuple(args),
            allow_file_access=allow_file_access,
            ignore_https_errors=ignore_https_errors,
            user_agent=user_agent,
            download_path=path_value(download_path),
        )

    @classmethod
    def from_public_options(
        cls,
        options: LaunchOptions | None = None,
        *,
        attach: CDPTarget | None = None,
        allowed_domains: str | None = None,
    ) -> LaunchConfiguration:
        """Build a launch configuration from named public option objects."""
        options = normalize_launch(options)
        target = cdp_target(attach) if attach is not None else None
        return cls.from_options(
            headless=options.headless,
            executable_path=options.executable_path,
            engine=options.engine,
            allowed_domains=allowed_domains,
            profile=options.profile,
            storage_state=options.storage_state,
            extensions=options.extensions,
            proxy=options.proxy,
            provider=options.provider,
            cdp_url=target.url if target is not None else None,
            cdp_port=target.port if target is not None else None,
            auto_connect=target.auto_connect if target is not None else False,
            color_scheme=options.color_scheme,
            hide_scrollbars=options.hide_scrollbars,
            args=options.args,
            allow_file_access=options.allow_file_access,
            ignore_https_errors=options.ignore_https_errors,
            user_agent=options.user_agent,
            download_path=options.download_path,
        )

    def replace_launch(self, options: LaunchOptions) -> LaunchConfiguration:
        """Return this configuration with browser process options replaced."""
        options = normalize_launch(options)
        return replace(
            self,
            headless=options.headless,
            executable_path=path_value(options.executable_path),
            engine=options.engine,
            profile=path_value(options.profile),
            storage_state=path_value(options.storage_state),
            extensions=tuple(paths_value(options.extensions)),
            proxy=options.proxy,
            provider=options.provider,
            color_scheme=options.color_scheme,
            hide_scrollbars=options.hide_scrollbars,
            args=tuple(options.args),
            allow_file_access=options.allow_file_access,
            ignore_https_errors=options.ignore_https_errors,
            user_agent=options.user_agent,
            download_path=path_value(options.download_path),
        )

    def command_params(
        self,
        *,
        options: LaunchOptions | None = None,
    ) -> dict[str, Any]:
        """Return native command parameters for `launch`."""
        config = self.replace_launch(options) if options is not None else self
        resolved_hide_scrollbars = config.hide_scrollbars
        return {
            "headless": config.headless,
            "executablePath": optional(config.executable_path),
            "engine": optional(config.engine),
            "args": list(config.args),
            "profile": optional(config.profile),
            "storageState": optional(config.storage_state),
            "extensions": list(config.extensions),
            "proxy": optional(proxy_value(config.proxy)),
            "provider": optional(config.provider),
            "cdpUrl": optional(config.cdp_url),
            "cdpPort": optional(config.cdp_port),
            "autoConnect": config.auto_connect,
            "allowFileAccess": config.allow_file_access,
            "ignoreHTTPSErrors": config.ignore_https_errors,
            "userAgent": optional(config.user_agent),
            "downloadPath": optional(config.download_path),
            "colorScheme": optional(config.color_scheme),
            "hideScrollbars": optional(resolved_hide_scrollbars),
            "allowedDomains": optional(config.allowed_domains),
        }
