from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from agentbrowser.command_params import optional
from agentbrowser.models import (
    ColorScheme,
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


@dataclass(frozen=True, slots=True)
class CDPAttach:
    """CDP attachment target used by `Browser.attach(...)`."""

    url: str | None = None
    port: int | None = None
    auto_connect: bool = True

    def __post_init__(self) -> None:
        if (self.url is None) == (self.port is None):
            raise ValueError("pass exactly one of url or port")


@dataclass(frozen=True, slots=True)
class BrowserSessionOptions:
    """Native session, restore, allowlist, and policy options for a browser."""

    session_id: str | None = None
    restore: RestoreOptions | None = None
    namespace: str | None = None
    default_timeout_ms: int | None = 15_000
    allowed_domains: str | None = None
    action_policy: str | Path | None = None
    confirm_actions: Sequence[str] | None = None
    no_auto_dialog: bool = False


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
        attach: CDPAttach | None = None,
        allowed_domains: str | None = None,
    ) -> LaunchConfiguration:
        """Build a launch configuration from named public option objects."""
        options = options or LaunchOptions()
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
            cdp_url=attach.url if attach is not None else None,
            cdp_port=attach.port if attach is not None else None,
            auto_connect=attach.auto_connect if attach is not None else False,
            color_scheme=options.color_scheme,
            hide_scrollbars=options.hide_scrollbars,
            args=options.args,
            allow_file_access=options.allow_file_access,
            ignore_https_errors=options.ignore_https_errors,
            user_agent=options.user_agent,
            download_path=options.download_path,
        )

    def replace_launch_options(self, options: LaunchOptions) -> LaunchConfiguration:
        """Return this configuration with browser process options replaced."""
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
        config = self.replace_launch_options(options) if options is not None else self
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
