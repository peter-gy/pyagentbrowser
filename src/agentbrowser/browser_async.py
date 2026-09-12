from __future__ import annotations

from contextlib import suppress
from typing import Self, TypeVar

from agentbrowser.contracts.errors import ConfirmationRequired
from agentbrowser.execution.commands import AsyncBoundExecutor, AsyncExecutor, Command
from agentbrowser.execution.controller_async import AsyncController
from agentbrowser.execution.native import AsyncNative
from agentbrowser.features.cdp.api import AsyncCDP
from agentbrowser.features.dashboard.api import AsyncDashboard
from agentbrowser.features.diagnostics.api import AsyncDiagnostics
from agentbrowser.features.diagnostics.diff import AsyncDiff
from agentbrowser.features.documents.handles_async import AsyncPage
from agentbrowser.features.downloads.api import AsyncDownloads
from agentbrowser.features.emulation.api import AsyncEmulation
from agentbrowser.features.input.api import AsyncClipboard, AsyncDialogs, AsyncKeyboard, AsyncMouse
from agentbrowser.features.network.api import AsyncNetwork
from agentbrowser.features.scripts.api import AsyncScripts
from agentbrowser.features.session.api import AsyncSession
from agentbrowser.features.session.models import CloseResult
from agentbrowser.features.storage.api import AsyncCookies, AsyncState, AsyncStorage
from agentbrowser.features.tabs.async_ import AsyncTabs
from agentbrowser.features.webmcp.api import AsyncWebMCP
from agentbrowser.launch import (
    CDPTarget,
    LaunchConfiguration,
    LaunchOptions,
    SessionOptions,
    normalize_session,
)
from agentbrowser.transport.async_ import AsyncNativeSession

T = TypeVar("T")


class AsyncBrowser:
    """Async owner for one ordered native browser session.

    Native calls run on a dedicated owner thread so the event loop can keep
    scheduling unrelated work. Document operations live under `page`.
    Browser-wide operations live under `tabs`, `network`, `diagnostics`,
    `session`, `webmcp`, `cdp`, and `native`."""

    def __init__(
        self,
        *,
        session: SessionOptions | None = None,
        _native_session: AsyncNativeSession | None = None,
    ) -> None:
        base_options = normalize_session(session)
        launch_configuration = LaunchConfiguration.from_public_options(
            allowed_domains=base_options._allowed_domains()
        )
        self._controller = AsyncController(
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
        native_session: AsyncNativeSession | None = None,
    ) -> AsyncBrowser:
        browser = cls.__new__(cls)
        browser._controller = AsyncController(
            launch_configuration,
            session=session,
            native_session=native_session,
        )
        browser._page_target_id = None
        return browser

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: object, _exc: object, _tb: object) -> None:
        if exc_type is None:
            await self.close()
            return
        with suppress(BaseException):
            await self.close()

    def __repr__(self) -> str:
        return f"AsyncBrowser(launched={self.is_launched!r}, closed={self.closed!r})"

    @classmethod
    async def launch(
        cls,
        options: LaunchOptions | None = None,
        *,
        session: SessionOptions | None = None,
    ) -> AsyncBrowser:
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
            await browser._controller.start()
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map(lambda _value: browser)
            raise
        return browser

    @classmethod
    async def attach(
        cls,
        target: CDPTarget,
        *,
        launch: LaunchOptions | None = None,
        session: SessionOptions | None = None,
    ) -> AsyncBrowser:
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
            await browser._controller.start()
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map(lambda _value: browser)
            raise
        return browser

    @property
    def _executor(self) -> AsyncExecutor:
        return AsyncBoundExecutor(self._controller)

    @property
    def page(self) -> AsyncPage:
        """Return a main-document handle for the configured page target."""
        return AsyncPage(
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
    def native(self) -> AsyncNative:
        """Return the complete native command interface."""
        return AsyncNative(self._controller)

    @property
    def cdp(self) -> AsyncCDP:
        """Return the direct Chrome DevTools Protocol interface."""
        return AsyncCDP(self._controller._cdp)

    @property
    def clipboard(self) -> AsyncClipboard:
        return AsyncClipboard(self._executor)

    @property
    def cookies(self) -> AsyncCookies:
        return AsyncCookies(self._executor)

    @property
    def diagnostics(self) -> AsyncDiagnostics:
        return AsyncDiagnostics(self._executor)

    @property
    def dashboard(self) -> AsyncDashboard:
        return AsyncDashboard(self._executor)

    @property
    def dialogs(self) -> AsyncDialogs:
        return AsyncDialogs(self._executor)

    @property
    def diff(self) -> AsyncDiff:
        return AsyncDiff(self._executor)

    @property
    def downloads(self) -> AsyncDownloads:
        return AsyncDownloads(self._executor)

    @property
    def emulation(self) -> AsyncEmulation:
        return AsyncEmulation(self._executor)

    @property
    def keyboard(self) -> AsyncKeyboard:
        return AsyncKeyboard(self._executor)

    @property
    def mouse(self) -> AsyncMouse:
        return AsyncMouse(self._executor)

    @property
    def network(self) -> AsyncNetwork:
        return AsyncNetwork(self._executor)

    @property
    def scripts(self) -> AsyncScripts:
        return AsyncScripts(self._executor)

    @property
    def session(self) -> AsyncSession:
        return AsyncSession(self._executor)

    @property
    def state(self) -> AsyncState:
        return AsyncState(self._executor)

    @property
    def storage(self) -> AsyncStorage:
        return AsyncStorage(self._executor)

    @property
    def tabs(self) -> AsyncTabs:
        return AsyncTabs(self._executor)

    @property
    def webmcp(self) -> AsyncWebMCP:
        return AsyncWebMCP(self._executor)

    async def close(self, *, timeout: float | None = None) -> CloseResult:
        """Close the browser and return terminal restore-save state.

        ``timeout`` limits this caller's wait. Cleanup continues after a caller
        timeout, and a later ``close()`` retrieves its result. The default waits
        for cleanup to finish.
        """
        return await self._controller.close(timeout=timeout)

    async def activate(self) -> Self:
        """Bring the browser window to the foreground."""
        return await self._executor.execute(Command("bringtofront", decode=lambda _data: self))
