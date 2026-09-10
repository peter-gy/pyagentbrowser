from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from typing import TYPE_CHECKING, Self, TypeVar

from agentbrowser.contracts.errors import ConfirmationRequired
from agentbrowser.execution.commands import BoundExecutor, Command, Executor
from agentbrowser.execution.controller import Controller
from agentbrowser.execution.native import Native
from agentbrowser.features.cdp.api import CDP
from agentbrowser.features.dashboard.api import Dashboard
from agentbrowser.features.diagnostics.api import Diagnostics
from agentbrowser.features.diagnostics.diff import Diff
from agentbrowser.features.documents.handles import Page
from agentbrowser.features.downloads.api import Downloads
from agentbrowser.features.emulation.api import Emulation
from agentbrowser.features.input.api import Clipboard, Dialogs, Keyboard, Mouse
from agentbrowser.features.network.api import Network
from agentbrowser.features.scripts.api import Scripts
from agentbrowser.features.session.api import Session
from agentbrowser.features.session.models import CloseResult
from agentbrowser.features.storage.api import Cookies, State, Storage
from agentbrowser.features.tabs.sync import Tabs
from agentbrowser.features.webmcp.api import WebMCP
from agentbrowser.launch import (
    CDPTarget,
    LaunchConfiguration,
    LaunchOptions,
    SessionOptions,
    normalize_session,
)
from agentbrowser.transport.sync import NativeSession

if TYPE_CHECKING:
    from agentbrowser.health import BrowserCapabilities, HealthCheck

T = TypeVar("T")


class Browser:
    """Synchronous owner for one native browser session.

    Use `launch()` for a local process and `attach()` for an existing CDP
    target. Document operations live under `page`. Browser-wide operations live
    under `tabs`, `network`, `diagnostics`, `session`, `webmcp`, `cdp`, and
    `native`.
    """

    def __init__(
        self,
        *,
        session: SessionOptions | None = None,
        _native_session: NativeSession | None = None,
    ) -> None:
        base_options = normalize_session(session)
        launch_configuration = LaunchConfiguration.from_public_options(
            allowed_domains=base_options._allowed_domains()
        )
        self._controller = Controller(
            launch_configuration,
            session=base_options,
            native_session=_native_session,
        )
        self._page_target_id: str | None = None

    @classmethod
    def _from_configuration(
        cls,
        launch_configuration: LaunchConfiguration,
        *,
        session: SessionOptions | None = None,
        native_session: NativeSession | None = None,
    ) -> Browser:
        browser = cls.__new__(cls)
        browser._controller = Controller(
            launch_configuration,
            session=session,
            native_session=native_session,
        )
        browser._page_target_id = None
        return browser

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, _exc: object, _tb: object) -> None:
        if exc_type is None:
            self.close()
            return
        with suppress(BaseException):
            self.close()

    def __repr__(self) -> str:
        return f"Browser(launched={self.is_launched!r}, closed={self.closed!r})"

    def capabilities(self, *, host: object | None = None) -> BrowserCapabilities:
        """Return configured browser and host-integration features."""
        from agentbrowser.health import capabilities

        return capabilities(host=host)

    def healthcheck(self) -> HealthCheck:
        """Probe optional browser dependencies without launching Chrome."""
        from agentbrowser.health import healthcheck

        return healthcheck()

    @classmethod
    def launch(
        cls,
        options: LaunchOptions | None = None,
        *,
        session: SessionOptions | None = None,
    ) -> Browser:
        """Create a browser and start the native browser process."""
        session_config = normalize_session(session)
        browser = cls._from_configuration(
            LaunchConfiguration.from_public_options(
                options,
                allowed_domains=session_config._allowed_domains(),
            ),
            session=session_config,
        )
        try:
            browser._controller.start()
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map(lambda _value: browser)
            raise
        return browser

    @classmethod
    def attach(
        cls,
        target: CDPTarget,
        *,
        launch: LaunchOptions | None = None,
        session: SessionOptions | None = None,
    ) -> Browser:
        """Create a browser and attach to a running CDP target."""
        session_config = normalize_session(session)
        browser = cls._from_configuration(
            LaunchConfiguration.from_public_options(
                launch,
                attach=target,
                allowed_domains=session_config._allowed_domains(),
            ),
            session=session_config,
        )
        try:
            browser._controller.start()
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map(lambda _value: browser)
            raise
        return browser

    @property
    def _executor(self) -> Executor:
        return BoundExecutor(self._controller)

    def extension(self, factory: Callable[[Executor], T]) -> T:
        """Construct a capability using this browser's checked command executor."""
        return factory(self._executor)

    @property
    def page(self) -> Page:
        """Return a main-document handle for the configured page target."""
        return Page(
            self._executor, target_id=self._page_target_id or self._controller._active_target_id
        )

    @property
    def is_launched(self) -> bool:
        """Whether the native browser has been launched in this session."""
        return self._controller._launched

    @property
    def closed(self) -> bool:
        """Whether this browser has been closed."""
        return self._controller.closed

    @property
    def native(self) -> Native:
        """Return the complete native command interface."""
        return Native(self._controller)

    @property
    def cdp(self) -> CDP:
        """Return the direct Chrome DevTools Protocol interface."""
        return CDP(self._controller._cdp)

    @property
    def clipboard(self) -> Clipboard:
        return Clipboard(self._executor)

    @property
    def cookies(self) -> Cookies:
        return Cookies(self._executor)

    @property
    def diagnostics(self) -> Diagnostics:
        return Diagnostics(self._executor)

    @property
    def dashboard(self) -> Dashboard:
        return Dashboard(self._executor)

    @property
    def dialogs(self) -> Dialogs:
        return Dialogs(self._executor)

    @property
    def diff(self) -> Diff:
        return Diff(self._executor)

    @property
    def downloads(self) -> Downloads:
        return Downloads(self._executor)

    @property
    def emulation(self) -> Emulation:
        return Emulation(self._executor)

    @property
    def keyboard(self) -> Keyboard:
        return Keyboard(self._executor)

    @property
    def mouse(self) -> Mouse:
        return Mouse(self._executor)

    @property
    def network(self) -> Network:
        return Network(self._executor)

    @property
    def scripts(self) -> Scripts:
        return Scripts(self._executor)

    @property
    def session(self) -> Session:
        return Session(self._executor)

    @property
    def state(self) -> State:
        return State(self._executor)

    @property
    def storage(self) -> Storage:
        return Storage(self._executor)

    @property
    def tabs(self) -> Tabs:
        return Tabs(self._executor)

    @property
    def webmcp(self) -> WebMCP:
        return WebMCP(self._executor)

    def close(self) -> CloseResult:
        """Close the browser and return terminal restore-save state."""
        return self._controller.close()

    def activate(self) -> Self:
        """Bring the browser window to the foreground."""
        return self._executor.execute(Command("bringtofront", decode=lambda _data: self))
