from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pyagentbrowser.command_params import optional
from pyagentbrowser.models import ColorScheme, ProxyConfig, path_value, paths_value, proxy_value


@dataclass(frozen=True, slots=True)
class LaunchConfiguration:
    """Normalized launch options shared by sync and async browser sessions.

    Instances store constructor-level launch defaults. `Browser.launch()` and
    `AsyncBrowser.launch()` can override these values for one launch command.
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
        )

    def command_params(
        self,
        *,
        headless: bool | None = None,
        executable_path: str | Path | None = None,
        engine: str | None = None,
        args: Sequence[str] | None = None,
        allow_file_access: bool = False,
        ignore_https_errors: bool = False,
        user_agent: str | None = None,
        download_path: str | Path | None = None,
        profile: str | Path | None = None,
        storage_state: str | Path | None = None,
        extensions: Sequence[str | Path] | None = None,
        proxy: str | ProxyConfig | Mapping[str, Any] | None = None,
        provider: str | None = None,
        cdp_url: str | None = None,
        cdp_port: int | None = None,
        auto_connect: bool | None = None,
        color_scheme: ColorScheme | None = None,
        hide_scrollbars: bool | None = None,
    ) -> dict[str, Any]:
        """Return native command parameters for `launch`."""
        resolved_hide_scrollbars = (
            self.hide_scrollbars if hide_scrollbars is None else hide_scrollbars
        )
        return {
            "headless": self.headless if headless is None else headless,
            "executablePath": optional(path_value(executable_path) or self.executable_path),
            "engine": optional(engine or self.engine),
            "args": list(self.args if args is None else args),
            "profile": optional(path_value(profile) or self.profile),
            "storageState": optional(path_value(storage_state) or self.storage_state),
            "extensions": list(self.extensions) if extensions is None else paths_value(extensions),
            "proxy": optional(proxy_value(self.proxy if proxy is None else proxy)),
            "provider": optional(provider or self.provider),
            "cdpUrl": optional(cdp_url or self.cdp_url),
            "cdpPort": optional(self.cdp_port if cdp_port is None else cdp_port),
            "autoConnect": self.auto_connect if auto_connect is None else auto_connect,
            "allowFileAccess": allow_file_access,
            "ignoreHTTPSErrors": ignore_https_errors,
            "userAgent": optional(user_agent),
            "downloadPath": optional(path_value(download_path)),
            "colorScheme": optional(color_scheme or self.color_scheme),
            "hideScrollbars": optional(resolved_hide_scrollbars),
            "allowedDomains": optional(self.allowed_domains),
        }
