from __future__ import annotations

import atexit
from collections.abc import Mapping, Sequence
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Any, TypedDict, cast

from typing_extensions import Unpack

from pyagentbrowser.agent import Agent
from pyagentbrowser.browser import Browser
from pyagentbrowser.domains import (
    CDP,
    Capture,
    Clipboard,
    Cookies,
    Diagnostics,
    Dialogs,
    Diff,
    Downloads,
    Find,
    Frames,
    Keyboard,
    Mouse,
    Network,
    Page,
    Scripts,
    State,
    Storage,
    Tabs,
)
from pyagentbrowser.models import ColorScheme, DashboardOptions, ProxyConfig

if TYPE_CHECKING:
    from pyagentbrowser.session import NativeSession

_lock = RLock()
_default_options: dict[str, Any] = {}
_default_browser: Browser | None = None


class DefaultBrowserOptions(TypedDict, total=False):
    """Keyword options accepted by `pyagentbrowser.configure()`."""

    headless: bool
    executable_path: str | Path | None
    engine: str | None
    session: str | None
    session_name: str | None
    default_timeout_ms: int | None
    allowed_domains: str | None
    action_policy: str | Path | None
    confirm_actions: Sequence[str] | None
    profile: str | Path | None
    storage_state: str | Path | None
    extensions: Sequence[str | Path]
    proxy: str | ProxyConfig | Mapping[str, Any] | None
    provider: str | None
    cdp_url: str | None
    cdp_port: int | None
    auto_connect: bool
    color_scheme: ColorScheme | None
    hide_scrollbars: bool | None
    args: Sequence[str]
    no_auto_dialog: bool
    dashboard: bool | DashboardOptions | None
    native_session: NativeSession | None


def default_browser() -> Browser:
    """Return the process-local default browser, creating it on first use.

    Returns
    -------
    Browser
        The lazily created default `Browser` instance.
    """

    global _default_browser
    with _lock:
        if _default_browser is None:
            _default_browser = Browser(**_default_options)
        return _default_browser


def configure(
    *,
    force: bool = False,
    **options: Unpack[DefaultBrowserOptions],
) -> Browser:
    """Replace the process-local default browser configuration.

    The current default browser is closed before a new default `Browser` object
    is created. Browser launch remains lazy unless CDP attachment options are
    supplied. `cdp_port`, `cdp_url`, and `auto_connect=True` perform an
    immediate connection handshake so non-navigation namespaces such as `tabs`
    can be used right away.

    Parameters
    ----------
    force
        Best-effort close the current default browser and discard the reference
        even if the native close command fails. Use it when an interrupted
        notebook run leaves a stale default browser.
    **options
        `Browser` constructor options.

    Returns
    -------
    Browser
        Newly configured default browser.
    """

    global _default_browser, _default_options
    with _lock:
        current = _default_browser
        previous_options = _default_options
        _default_browser = None
        _default_options = {key: value for key, value in options.items()}

    if current is not None:
        try:
            current.close()
        except BaseException:
            if not force:
                with _lock:
                    if _default_browser is None:
                        _default_browser = current
                        _default_options = previous_options
                raise
    browser = default_browser()
    if _should_connect_on_configure(options):
        browser.connect()
    return browser


def _should_connect_on_configure(options: Mapping[str, Any]) -> bool:
    return (
        bool(options.get("cdp_url"))
        or options.get("cdp_port") is not None
        or bool(options.get("auto_connect"))
    )


def close(*, force: bool = False) -> None:
    """Close the process-local default browser if it exists, keeping defaults.

    Parameters
    ----------
    force
        Best-effort close the browser and discard the default reference even if
        the native close command fails.
    """

    global _default_browser
    with _lock:
        current = _default_browser

    if current is not None:
        try:
            current.close()
        except BaseException:
            if not force:
                raise
        with _lock:
            if _default_browser is current:
                _default_browser = None


def reset(*, force: bool = False) -> None:
    """Close the process-local default browser and clear its configuration.

    Parameters
    ----------
    force
        Best-effort close the browser and clear the default state even if the
        native close command fails.
    """

    global _default_options
    close(force=force)
    with _lock:
        _default_options = {}


class _DefaultNamespaceProxy:
    def __init__(self, name: str) -> None:
        self._name = name

    def _target(self) -> Any:
        return getattr(default_browser(), self._name)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._target(), name)

    def __dir__(self) -> list[str]:
        return sorted(set(dir(type(self)) + dir(self._target())))

    def __repr__(self) -> str:
        with _lock:
            target = repr(_default_browser) if _default_browser is not None else "uncreated"
        return f"<pyagentbrowser default namespace {self._name!r} for {target}>"


page = cast(Page, _DefaultNamespaceProxy("page"))
agent = cast(Agent, _DefaultNamespaceProxy("agent"))
capture = cast(Capture, _DefaultNamespaceProxy("capture"))
cdp = cast(CDP, _DefaultNamespaceProxy("cdp"))
clipboard = cast(Clipboard, _DefaultNamespaceProxy("clipboard"))
cookies = cast(Cookies, _DefaultNamespaceProxy("cookies"))
dialogs = cast(Dialogs, _DefaultNamespaceProxy("dialogs"))
diagnostics = cast(Diagnostics, _DefaultNamespaceProxy("diagnostics"))
diff = cast(Diff, _DefaultNamespaceProxy("diff"))
downloads = cast(Downloads, _DefaultNamespaceProxy("downloads"))
find = cast(Find, _DefaultNamespaceProxy("find"))
frames = cast(Frames, _DefaultNamespaceProxy("frames"))
keyboard = cast(Keyboard, _DefaultNamespaceProxy("keyboard"))
mouse = cast(Mouse, _DefaultNamespaceProxy("mouse"))
network = cast(Network, _DefaultNamespaceProxy("network"))
scripts = cast(Scripts, _DefaultNamespaceProxy("scripts"))
state = cast(State, _DefaultNamespaceProxy("state"))
storage = cast(Storage, _DefaultNamespaceProxy("storage"))
tabs = cast(Tabs, _DefaultNamespaceProxy("tabs"))


atexit.register(close)
