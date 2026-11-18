from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, get_args

from agentbrowser.contracts.connection import ProxyConfig, proxy_value
from agentbrowser.contracts.protocol import optional, path_value, paths_value
from agentbrowser.features.emulation.models import ColorScheme
from agentbrowser.features.session.models import DashboardOptions, RestoreOptions

CaptureMode = Literal["flow"]

_ALLOWLIST_BLOCKED_CHROME_SWITCHES = {
    "app",
    "app-id",
    "app-launch-url-for-shortcuts-menu-item",
    "load-and-launch-app",
    "profile-directory",
    "restore-last-session",
    "restore-session",
    "user-data-dir",
}


def _chrome_switch_name(arg: str) -> str | None:
    value = arg.strip()
    for prefix in ("--", "/", "-"):
        if value.startswith(prefix):
            switch = value.removeprefix(prefix).split("=", 1)[0].split(" ", 1)[0]
            if switch and "/" not in switch and "\\" not in switch:
                return switch.lower()
            return None
    return None


def _allowlist_arg_conflict(args: Sequence[str]) -> str | None:
    for arg in args:
        value = arg.strip()
        lowered = value.lower()
        if lowered.startswith(("http://", "https://", "file://")):
            return "a startup URL"
        switch = _chrome_switch_name(arg)
        if value and switch is None:
            return "a startup URL or path"
        if switch in _ALLOWLIST_BLOCKED_CHROME_SWITCHES:
            return f"--{switch}"
    return None


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
    ca_cert: str | Path | None = None
    provider: str | None = None
    color_scheme: ColorScheme | None = None
    hide_scrollbars: bool | None = None
    webgpu: bool | None = None
    webmcp: bool | None = None
    no_xvfb: bool | None = None
    args: Sequence[str] = ()
    allow_file_access: bool = False
    ignore_https_errors: bool = False
    user_agent: str | None = None
    download_path: str | Path | None = None
    capture: Sequence[CaptureMode] = ()

    def __post_init__(self) -> None:
        if isinstance(self.extensions, str):
            raise TypeError("extensions must be a sequence, not a string")
        if isinstance(self.args, str):
            raise TypeError("args must be a sequence, not a string")
        if isinstance(self.capture, str):
            raise TypeError("capture must be a sequence, not a string")
        if self.ca_cert is not None and not str(self.ca_cert).strip():
            raise ValueError("ca_cert must not be empty")
        capture = tuple(self.capture)
        if unknown := [mode for mode in capture if mode not in get_args(CaptureMode)]:
            raise ValueError(f"unknown capture mode {unknown[0]!r}. Supported: flow")
        object.__setattr__(self, "extensions", tuple(self.extensions))
        object.__setattr__(self, "args", tuple(self.args))
        object.__setattr__(self, "capture", capture)


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
    pin_tab: bool | None = None
    dashboard: DashboardOptions | None = None

    def __post_init__(self) -> None:
        if self.timeout is not None and self.timeout < 0:
            raise ValueError("timeout must be non-negative")
        if isinstance(self.allowed_domains, str):
            raise TypeError("allowed_domains must be a sequence, not a string")
        if isinstance(self.confirm_actions, str):
            raise TypeError("confirm_actions must be a sequence, not a string")
        if self.pin_tab is not None and not isinstance(self.pin_tab, bool):
            raise TypeError("pin_tab must be a boolean or None")
        domains = tuple(self.allowed_domains)
        actions = tuple(self.confirm_actions)
        if any(not domain.strip() for domain in domains):
            raise ValueError("allowed_domains entries must not be empty")
        if any(not action.strip() for action in actions):
            raise ValueError("confirm_actions entries must not be empty")
        if domains and self.restore is not None:
            raise ValueError(
                "allowed_domains cannot be combined with restore because saved origins can "
                "replay before containment starts"
            )
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
    """Browser process options with the session's attach target and allowlist."""

    options: LaunchOptions = field(default_factory=LaunchOptions)
    attach: CDPTarget | None = None
    allowed_domains: str | None = None

    def __post_init__(self) -> None:
        options = self.options
        if self.allowed_domains and self.allowed_domains.strip():
            if options.storage_state is not None and str(options.storage_state).strip():
                raise ValueError(
                    "allowed_domains cannot be combined with storage_state because saved "
                    "origins can replay before containment starts"
                )
            if self.attach is not None:
                raise ValueError(
                    "allowed_domains cannot be combined with CDP attachment because containment "
                    "must start before page scripts"
                )
            if options.profile is not None:
                raise ValueError(
                    "allowed_domains cannot be combined with profile because Chrome can restore "
                    "pages before containment starts"
                )
            if options.provider is not None and options.provider.strip().lower() in {
                "ios",
                "safari",
            }:
                raise ValueError(
                    f"allowed_domains cannot be enforced by the {options.provider.strip()} provider"
                )
            if conflict := _allowlist_arg_conflict(options.args):
                raise ValueError(
                    "allowed_domains cannot be combined with browser args containing "
                    f"{conflict} because pages can open before containment starts"
                )

        external_browser = self.attach is not None or options.provider is not None
        if options.ca_cert is not None:
            if options.profile is not None:
                raise ValueError("ca_cert cannot be combined with profile")
            if options.ignore_https_errors:
                raise ValueError("ca_cert cannot be combined with ignore_https_errors")
            engine = options.engine or os.environ.get("AGENT_BROWSER_ENGINE")
            if engine is not None and engine.strip().lower() != "chrome":
                raise ValueError("ca_cert requires the Chrome engine on Linux")
            if external_browser:
                raise ValueError("ca_cert requires a local Chromium browser launch")
        if not external_browser:
            return
        webgpu_enabled = options.webgpu
        if webgpu_enabled is None:
            webgpu_enabled = os.environ.get("AGENT_BROWSER_WEBGPU") in {"1", "true"}
        if webgpu_enabled:
            raise ValueError(
                "webgpu requires a local browser launch. Pass webgpu=False to override "
                "AGENT_BROWSER_WEBGPU for CDP and provider connections"
            )
        if options.no_xvfb is True:
            raise ValueError("no_xvfb requires a local browser launch")

    @classmethod
    def from_options(
        cls,
        options: LaunchOptions | None = None,
        *,
        attach: CDPTarget | None = None,
        allowed_domains: str | None = None,
    ) -> LaunchConfiguration:
        """Build a launch configuration from the public option objects."""
        return cls(
            normalize_launch(options),
            attach=cdp_target(attach) if attach is not None else None,
            allowed_domains=allowed_domains,
        )

    def command_params(self) -> dict[str, Any]:
        """Return native `launch` parameters."""
        options, attach = self.options, self.attach
        return {
            "headless": options.headless,
            "executablePath": optional(path_value(options.executable_path)),
            "engine": optional(options.engine),
            "args": list(options.args),
            "profile": optional(path_value(options.profile)),
            "storageState": optional(path_value(options.storage_state)),
            "extensions": paths_value(options.extensions),
            "proxy": optional(proxy_value(options.proxy)),
            "caCert": optional(path_value(options.ca_cert)),
            "provider": optional(options.provider),
            "cdpUrl": optional(attach.url if attach is not None else None),
            "cdpPort": optional(attach.port if attach is not None else None),
            "autoConnect": attach.auto_connect if attach is not None else False,
            "allowFileAccess": options.allow_file_access,
            "ignoreHTTPSErrors": options.ignore_https_errors,
            "userAgent": optional(options.user_agent),
            "downloadPath": optional(path_value(options.download_path)),
            "colorScheme": optional(options.color_scheme),
            "hideScrollbars": optional(options.hide_scrollbars),
            "webgpu": optional(options.webgpu),
            "webmcp": optional(options.webmcp),
            "noXvfb": optional(options.no_xvfb),
            "capture": optional(list(options.capture) or None),
            "allowedDomains": optional(self.allowed_domains),
        }
