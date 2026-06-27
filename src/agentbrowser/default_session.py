from __future__ import annotations

import atexit
from threading import RLock
from typing import TYPE_CHECKING, Any, TypedDict, cast

from typing_extensions import Unpack

from agentbrowser.agent import Agent
from agentbrowser.browser import Browser, Dashboard
from agentbrowser.domains import (
    CDP,
    ActiveFrame,
    Capture,
    Clipboard,
    Cookies,
    Diagnostics,
    Dialogs,
    Diff,
    Downloads,
    Find,
    Keyboard,
    Mouse,
    Network,
    Page,
    Restore,
    Runtime,
    Scripts,
    State,
    Storage,
    Tabs,
)
from agentbrowser.launch import (
    BrowserSessionOptions,
    CDPAttach,
    LaunchConfiguration,
    LaunchOptions,
)

if TYPE_CHECKING:
    from agentbrowser.session import NativeSession

_lock = RLock()
_default_options: dict[str, Any] = {}
_default_browser: Browser | None = None


class DefaultBrowserOptions(TypedDict, total=False):
    """Keyword options accepted by `agentbrowser.notebook.configure()`."""

    launch_options: LaunchOptions | None
    attach: CDPAttach | None
    session_options: BrowserSessionOptions | None
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
            _default_browser = _new_browser(_default_options)
        return _default_browser


def _new_browser(options: dict[str, Any]) -> Browser:
    session_options = cast(
        BrowserSessionOptions,
        options.get("session_options") or BrowserSessionOptions(),
    )
    launch_options = cast(LaunchOptions | None, options.get("launch_options"))
    attach = cast(CDPAttach | None, options.get("attach"))
    native_session = cast("NativeSession | None", options.get("native_session"))
    launch_configuration = LaunchConfiguration.from_public_options(
        launch_options,
        attach=attach,
        allowed_domains=session_options.allowed_domains,
    )
    return Browser._from_configuration(
        launch_configuration,
        session_options=session_options,
        native_session=native_session,
    )


def configure(
    *,
    force: bool = False,
    **options: Unpack[DefaultBrowserOptions],
) -> Browser:
    """Replace the process-local default browser configuration.

    The current default browser is closed before a new default `Browser` object
    is created. Browser launch and CDP attachment remain lazy until code calls
    `browser.connect()` or a namespace method that needs a page.

    Parameters
    ----------
    force
        Best-effort close the current default browser and discard the reference
        even if the native close command fails. Use it when an interrupted
        notebook run leaves a stale default browser.
    **options
        Named lifecycle option objects: `launch_options`, `attach`,
        `session_options`, and `native_session`.

    Returns
    -------
    Browser
        Newly configured default browser.
    """

    global _default_browser, _default_options
    next_options = {key: value for key, value in options.items()}
    replacement = _new_browser(next_options)
    with _lock:
        current = _default_browser
        if current is not None:
            try:
                current.close()
            except BaseException:
                if not force:
                    raise
        _default_browser = replacement
        _default_options = next_options
        return replacement


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
        return f"<agentbrowser default namespace {self._name!r} for {target}>"


active_frame = cast(ActiveFrame, _DefaultNamespaceProxy("active_frame"))
page = cast(Page, _DefaultNamespaceProxy("page"))
agent = cast(Agent, _DefaultNamespaceProxy("agent"))
capture = cast(Capture, _DefaultNamespaceProxy("capture"))
cdp = cast(CDP, _DefaultNamespaceProxy("cdp"))
clipboard = cast(Clipboard, _DefaultNamespaceProxy("clipboard"))
cookies = cast(Cookies, _DefaultNamespaceProxy("cookies"))
dashboard = cast(Dashboard, _DefaultNamespaceProxy("dashboard"))
dialogs = cast(Dialogs, _DefaultNamespaceProxy("dialogs"))
diagnostics = cast(Diagnostics, _DefaultNamespaceProxy("diagnostics"))
diff = cast(Diff, _DefaultNamespaceProxy("diff"))
downloads = cast(Downloads, _DefaultNamespaceProxy("downloads"))
find = cast(Find, _DefaultNamespaceProxy("find"))
keyboard = cast(Keyboard, _DefaultNamespaceProxy("keyboard"))
mouse = cast(Mouse, _DefaultNamespaceProxy("mouse"))
network = cast(Network, _DefaultNamespaceProxy("network"))
scripts = cast(Scripts, _DefaultNamespaceProxy("scripts"))
restore = cast(Restore, _DefaultNamespaceProxy("restore"))
runtime = cast(Runtime, _DefaultNamespaceProxy("runtime"))
state = cast(State, _DefaultNamespaceProxy("state"))
storage = cast(Storage, _DefaultNamespaceProxy("storage"))
tabs = cast(Tabs, _DefaultNamespaceProxy("tabs"))


atexit.register(close)
