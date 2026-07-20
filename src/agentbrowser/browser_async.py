from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generic, Literal, Self, TypeVar, cast, overload
from weakref import proxy as weak_proxy

from agentbrowser._browser_common import (
    action_clears_pending_confirmation,
    action_closes_browser,
    action_invalidates_cdp,
    action_resets_cdp,
    action_sets_launched,
    confirmation_id,
    response_browser_launched,
    response_confirmation_id,
    response_data_mapping,
    snapshot_diff_from_data,
)
from agentbrowser.agent_async import AsyncSnapshot
from agentbrowser.browser import _SKIP_AUTO_INSTALL_ACTIONS, _uses_local_chrome
from agentbrowser.command_params import (
    geolocation_params,
    media_params,
    optional,
    permissions_params,
    viewport_params,
)
from agentbrowser.domains_async import (
    AsyncActiveFrame,
    AsyncCapture,
    AsyncCDP,
    AsyncClipboard,
    AsyncCommandTarget,
    AsyncCookies,
    AsyncDiagnostics,
    AsyncDialogs,
    AsyncDiff,
    AsyncDownloads,
    AsyncKeyboard,
    AsyncMouse,
    AsyncNetwork,
    AsyncPage,
    AsyncScripts,
    AsyncSession,
    AsyncState,
    AsyncStorage,
    AsyncTabs,
)
from agentbrowser.install import ensure_installed
from agentbrowser.launch import (
    CDPTarget,
    LaunchConfiguration,
    LaunchOptions,
    SessionOptions,
    normalize_session,
)
from agentbrowser.models import (
    BrowserResponse,
    CloseResult,
    ConfirmationRequired,
    JSONMapping,
    JSONValue,
    LoadState,
    ReadMode,
    ReadResult,
    RestoreSaveError,
    SnapshotData,
    SnapshotDiff,
    SnapshotSpec,
    close_result_from_data,
    path_value,
    snapshot_from_data,
)
from agentbrowser.query_async import AsyncQueries
from agentbrowser.session import (
    _checked_response,
    _require_response_data_mapping,
    _try_unwrap_confirmed_response,
)
from agentbrowser.session_async import AsyncNativeSession

if TYPE_CHECKING:
    from agentbrowser.cdp import AsyncCDPController

T = TypeVar("T")
U = TypeVar("U")


@dataclass(frozen=True, slots=True)
class AsyncNative:
    """Raw native command boundary for an `AsyncBrowser`."""

    _browser: AsyncBrowser

    async def execute(self, action: str, **params: Any) -> BrowserResponse:
        """Run a native command and return the response envelope."""
        return await self._browser._native_execute(action, **params)

    @overload
    async def data(self, action: str, **params: Any) -> JSONMapping: ...

    @overload
    async def data(
        self,
        action: str,
        *,
        expect: Literal["object"],
        **params: Any,
    ) -> JSONMapping: ...

    @overload
    async def data(
        self,
        action: str,
        *,
        expect: Literal["any"],
        **params: Any,
    ) -> JSONValue: ...

    async def data(
        self,
        action: str,
        *,
        expect: str = "object",
        **params: Any,
    ) -> JSONMapping | JSONValue:
        """Run a native command and return checked response data.

        `expect="object"` requires object-shaped response data. Use
        `expect="any"` for native actions whose `data` is a scalar, array, or
        `null`.
        """
        return await self._browser._native_data(action, expect=expect, **params)


@dataclass(frozen=True, slots=True)
class AsyncDashboard:
    """Dashboard observability lifecycle for an `AsyncBrowser`."""

    _browser: AsyncBrowser

    async def status(self) -> Mapping[str, Any]:
        """Return the configured dashboard stream status."""
        return await self._browser._command("stream_status")

    async def stop(self) -> None:
        """Stop dashboard streaming for this browser."""
        await self._browser._command("stream_disable", _decode=lambda _data: None)


@dataclass(frozen=True, slots=True)
class AsyncEmulation:
    """Async browser environment and device emulation."""

    _browser: AsyncBrowser

    async def viewport(
        self,
        width: int,
        height: int,
        *,
        device_scale_factor: float = 1.0,
        mobile: bool = False,
    ) -> None:
        """Set viewport dimensions in CSS pixels."""
        await self._browser._command(
            "viewport",
            _decode=lambda _data: None,
            **viewport_params(
                width,
                height,
                device_scale_factor=device_scale_factor,
                mobile=mobile,
            ),
        )

    async def device(self, name: str) -> None:
        """Apply a named device preset."""
        await self._browser._command("device", _decode=lambda _data: None, name=name)

    async def headers(self, headers: Mapping[str, str]) -> None:
        """Set extra HTTP headers."""
        await self._browser._command(
            "headers",
            _decode=lambda _data: None,
            headers=dict(headers),
        )

    async def offline(self, enabled: bool = True) -> None:
        """Set network offline emulation."""
        await self._browser._command(
            "offline",
            _decode=lambda _data: None,
            offline=enabled,
        )

    async def user_agent(self, value: str) -> None:
        """Set the browser user agent."""
        await self._browser._command(
            "useragent",
            _decode=lambda _data: None,
            userAgent=value,
        )

    async def media(
        self,
        *,
        media: str | None = None,
        color_scheme: str | None = None,
        reduced_motion: str | None = None,
        features: Mapping[str, str] | None = None,
    ) -> None:
        """Set CSS media emulation."""
        await self._browser._command(
            "set_media",
            _decode=lambda _data: None,
            **media_params(
                media=media,
                color_scheme=color_scheme,
                reduced_motion=reduced_motion,
                features=features,
            ),
        )

    async def timezone(self, timezone_id: str) -> None:
        """Set the emulated timezone."""
        await self._browser._command(
            "timezone",
            _decode=lambda _data: None,
            timezoneId=timezone_id,
        )

    async def locale(self, locale: str) -> None:
        """Set the emulated locale."""
        await self._browser._command("locale", _decode=lambda _data: None, locale=locale)

    async def geolocation(
        self,
        latitude: float,
        longitude: float,
        *,
        accuracy: float | None = None,
    ) -> None:
        """Set emulated coordinates."""
        await self._browser._command(
            "geolocation",
            _decode=lambda _data: None,
            **geolocation_params(latitude, longitude, accuracy=accuracy),
        )

    async def permissions(
        self,
        permissions: Sequence[str],
        *,
        origin: str | None = None,
    ) -> None:
        """Grant permissions for an optional origin."""
        await self._browser._command(
            "permissions",
            _decode=lambda _data: None,
            **permissions_params(permissions, origin=origin),
        )


@dataclass(frozen=True, slots=True)
class AsyncPendingAction(Generic[T]):
    """Native action awaiting explicit async confirmation or denial."""

    _browser: AsyncBrowser
    confirmation_id: str
    action: str
    details: Mapping[str, Any]
    _decode: Callable[[JSONMapping], T] | None = None
    _expect: Literal["object", "any"] = "object"
    _complete: Callable[[Any], Any] | None = None

    async def confirm(self) -> T:
        """Confirm this pending action and decode its original return type."""
        try:
            result: Any = await self._browser._native_data(
                "confirm",
                expect=self._expect,
                confirmation_id=self.confirmation_id,
            )
        except ConfirmationRequired as error:
            if isinstance(error.pending, AsyncPendingAction):
                error.pending = replace(
                    error.pending,
                    _decode=self._decode,
                    _expect=self._expect,
                    _complete=self._complete,
                )
            raise
        if self._decode is not None:
            result = self._decode(cast(JSONMapping, result))
        if self._complete is None:
            return cast(T, result)
        completed = self._complete(result)
        return cast(T, await completed if inspect.isawaitable(completed) else completed)

    async def deny(self) -> None:
        """Deny this pending action."""
        await self._browser._command("deny", confirmation_id=self.confirmation_id)

    def map(self, complete: Callable[[T], U]) -> AsyncPendingAction[U]:
        """Complete a higher-level operation after native confirmation."""
        previous = self._complete
        if previous is None:
            composed: Callable[[Any], Any] = complete
        else:

            async def composed(value: Any) -> Any:
                try:
                    intermediate = previous(value)
                    if inspect.isawaitable(intermediate):
                        intermediate = await intermediate
                except ConfirmationRequired as error:
                    if error.pending is not None:
                        error.pending = error.pending.map(complete)
                    raise
                completed = complete(intermediate)
                return await completed if inspect.isawaitable(completed) else completed

        return cast(AsyncPendingAction[U], replace(self, _complete=composed))


class AsyncBrowser:
    """Async owner for one ordered native browser session.

    Native calls run on a dedicated owner thread so the event loop can keep
    scheduling unrelated work.
    """

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
        self._init(
            launch_configuration,
            session=base_options,
            native_session=_native_session,
        )

    @classmethod
    def _from_configuration(
        cls,
        launch_configuration: LaunchConfiguration,
        *,
        session: SessionOptions | None = None,
        native_session: AsyncNativeSession | None = None,
    ) -> AsyncBrowser:
        browser = cls.__new__(cls)
        browser._init(
            launch_configuration,
            session=session,
            native_session=native_session,
        )
        return browser

    def _init(
        self,
        launch_configuration: LaunchConfiguration,
        *,
        session: SessionOptions | None = None,
        native_session: AsyncNativeSession | None = None,
    ) -> None:
        session_config = normalize_session(session)
        self._session = native_session or AsyncNativeSession(
            session=session_config.session_id,
            restore=session_config.restore,
            namespace=session_config.namespace,
            default_timeout_ms=session_config._timeout_ms(),
            allowed_domains=session_config._allowed_domains(),
            engine=launch_configuration.engine,
            action_policy=session_config.action_policy,
            confirm_actions=session_config.confirm_actions,
            no_auto_dialog=not session_config.auto_dialogs,
            dashboard=session_config.dashboard,
        )
        if native_session is not None and session_config.allowed_domains:
            self._session.set_allowed_domains(session_config._allowed_domains())
        default_session_config = SessionOptions()
        if native_session is not None and session_config.namespace is not None:
            raise ValueError(
                "namespace must be set on AsyncNativeSession when native_session is supplied"
            )
        if native_session is not None and session_config.session_id is not None:
            raise ValueError(
                "session_id must be set on AsyncNativeSession when native_session is supplied"
            )
        if native_session is not None and session_config.restore is not None:
            raise ValueError(
                "restore must be set on AsyncNativeSession when native_session is supplied"
            )
        if native_session is not None and session_config.timeout != default_session_config.timeout:
            raise ValueError(
                "default_timeout_ms must be set on AsyncNativeSession "
                "when native_session is supplied"
            )
        if native_session is not None and session_config.action_policy is not None:
            raise ValueError(
                "action_policy must be set on AsyncNativeSession when native_session is supplied"
            )
        if native_session is not None and session_config.confirm_actions:
            raise ValueError(
                "confirm_actions must be set on AsyncNativeSession when native_session is supplied"
            )
        if (
            native_session is not None
            and session_config.auto_dialogs != default_session_config.auto_dialogs
        ):
            raise ValueError(
                "no_auto_dialog must be set on AsyncNativeSession when native_session is supplied"
            )
        if native_session is not None and session_config.dashboard is not None:
            raise ValueError(
                "dashboard must be set on AsyncNativeSession when native_session is supplied"
            )
        self._launch_configuration = launch_configuration
        self._auto_install = native_session is None
        self._install_prepared = False
        self._launched = False
        self._close_task: asyncio.Task[CloseResult] | None = None
        self._cdp_controller: AsyncCDPController | None = None

        command_target = cast(AsyncCommandTarget, weak_proxy(self))
        browser_proxy = cast(AsyncBrowser, weak_proxy(self))
        self.active_frame = AsyncActiveFrame(command_target)
        self.capture = AsyncCapture(command_target)
        self.cdp = AsyncCDP(browser_proxy)
        self.clipboard = AsyncClipboard(command_target)
        self.cookies = AsyncCookies(command_target)
        self.diagnostics = AsyncDiagnostics(command_target)
        self.dashboard = AsyncDashboard(browser_proxy)
        self.dialogs = AsyncDialogs(command_target)
        self.diff = AsyncDiff(command_target)
        self.downloads = AsyncDownloads(command_target)
        self.emulation = AsyncEmulation(browser_proxy)
        self.find = AsyncQueries(browser_proxy)
        self.keyboard = AsyncKeyboard(command_target)
        self.mouse = AsyncMouse(command_target)
        self.native = AsyncNative(browser_proxy)
        self.network = AsyncNetwork(command_target)
        self.page = AsyncPage(browser_proxy)
        self.scripts = AsyncScripts(command_target)
        self.session = AsyncSession(command_target)
        self.state = AsyncState(command_target)
        self.storage = AsyncStorage(command_target)
        self.tabs = AsyncTabs(command_target)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: object, _exc: object, _tb: object) -> None:
        if exc_type is None:
            await self.close()
            return
        with suppress(BaseException):
            await self.close()

    @property
    def is_launched(self) -> bool:
        """Whether the native browser has been launched in this session."""
        return self._launched

    @property
    def closed(self) -> bool:
        """Whether this browser has been closed."""
        return self._session.closed

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
            await browser._launch_process()
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
            await browser._connect()
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map(lambda _value: browser)
            raise
        return browser

    async def observe(
        self,
        spec: SnapshotSpec | None = None,
    ) -> AsyncSnapshot:
        """Capture an accessibility snapshot bound to this browser."""
        try:
            data = await self._snapshot_data(spec or SnapshotSpec())
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map(lambda result: AsyncSnapshot(self, result))
            raise
        return AsyncSnapshot(self, data)

    async def open(self, url: str, *, wait_until: LoadState = "load") -> Self:
        """Navigate the active tab and return this browser."""
        try:
            await self.page.open(url, wait_until=wait_until)
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map(lambda _value: self)
            raise
        return self

    async def title(self) -> str:
        """Return the active page title."""
        return await self.page.title()

    async def url(self) -> str:
        """Return the active page URL."""
        return await self.page.url()

    async def content(self) -> str:
        """Return the active page HTML."""
        return await self.page.content()

    async def evaluate(self, script: str) -> Any:
        """Evaluate JavaScript in the active page."""
        return await self.page.evaluate(script)

    async def read(
        self,
        url: str | None = None,
        *,
        mode: ReadMode | None = None,
        filter: str | None = None,
        timeout_ms: int | None = None,
        headers: Mapping[str, str] | None = None,
        allowed_domains: Sequence[str] | None = None,
    ) -> ReadResult:
        """Return agent-readable content for a URL or the active page."""
        return await self.page.read(
            url,
            mode=mode,
            filter=filter,
            timeout_ms=timeout_ms,
            headers=headers,
            allowed_domains=allowed_domains,
        )

    async def wait_for_text(self, text: str, *, timeout_ms: int | None = None) -> None:
        """Wait until text appears in the active page."""
        await self.page.wait_for_text(text, timeout_ms=timeout_ms)

    async def wait_for_url(self, url: str, *, timeout_ms: int | None = None) -> None:
        """Wait until the active URL matches a pattern."""
        await self.page.wait_for_url(url, timeout_ms=timeout_ms)

    async def wait_for_load(self, state: LoadState = "load") -> None:
        """Wait for a page load state."""
        await self.page.wait_for_load_state(state)

    @overload
    async def _command(
        self,
        action: str,
        *,
        _decode: Callable[[JSONMapping], T],
        **params: Any,
    ) -> T: ...

    @overload
    async def _command(
        self,
        action: str,
        *,
        _decode: None = None,
        **params: Any,
    ) -> JSONMapping: ...

    async def _command(
        self,
        action: str,
        *,
        _decode: Callable[[JSONMapping], T] | None = None,
        **params: Any,
    ) -> T | JSONMapping:
        """Run a native command and require object-shaped response data.

        Parameters
        ----------
        action
            Native agent-browser command action.
        **params
            JSON-compatible command parameters.

        Returns
        -------
        Mapping[str, object]
            Response `data` object returned by the native engine.
        """
        try:
            data = await self._native_data(action, expect="object", **params)
        except ConfirmationRequired as err:
            if err.confirmation_id is not None:
                err.pending = self._pending_action(err, decoder=_decode)
            raise
        mapping = cast(JSONMapping, data)
        return _decode(mapping) if _decode is not None else mapping

    async def _native_data(
        self,
        action: str,
        *,
        expect: str = "object",
        **params: Any,
    ) -> JSONMapping | JSONValue:
        if expect not in {"object", "any"}:
            raise ValueError('expect must be "object" or "any"')
        await self._prepare_install_for_action(action, params)
        try:
            response = _checked_response(action, await self._session.execute(action, **params))
        except ConfirmationRequired as err:
            if err.confirmation_id is not None:
                err.pending = self._pending_action(
                    err,
                    expect=cast(Literal["object", "any"], expect),
                )
            raise
        await self._record_successful_action(response)
        if expect == "any":
            return response.data
        return _require_response_data_mapping(response)

    async def _native_execute(self, action: str, **params: Any) -> BrowserResponse:
        await self._prepare_install_for_action(action, params)
        response = await self._session.execute(action, **params)
        confirmation_consumed = action == "confirm" and response.success
        if confirmation_consumed:
            response = _try_unwrap_confirmed_response(response)
        data = response_data_mapping(response)
        if data is not None and bool(data.get("confirmation_required")):
            return response
        if confirmation_consumed:
            if response.success:
                await self._record_successful_action(response)
            return response
        if response.success:
            await self._record_successful_action(response)
        return response

    def _pending_action(
        self,
        confirmation: ConfirmationRequired[Any] | BrowserResponse | str,
        *,
        decoder: Callable[[JSONMapping], T] | None = None,
        expect: Literal["object", "any"] = "object",
    ) -> AsyncPendingAction[T]:
        """Return a named pending action for a confirmation exception, response, or id."""
        if isinstance(confirmation, BrowserResponse):
            pending_id = response_confirmation_id(confirmation)
            action = confirmation.action
            data = response_data_mapping(confirmation) or {}
        else:
            pending_id = confirmation_id(confirmation)
            if isinstance(confirmation, ConfirmationRequired):
                action = confirmation.action
                data = confirmation.data
            else:
                action = "confirm"
                data = {}
        if pending_id is None:
            raise ValueError("pending action requires a confirmation id")
        return AsyncPendingAction(
            _browser=self,
            confirmation_id=pending_id,
            action=action,
            details=dict(data),
            _decode=decoder,
            _expect=expect,
        )

    async def _record_successful_action(self, response: BrowserResponse) -> None:
        action = response.action
        browser_launched = response_browser_launched(response)
        if browser_launched is not None:
            self._launched = browser_launched
        elif action_sets_launched(action):
            self._launched = True
        elif action_clears_pending_confirmation(action) and action_closes_browser(action):
            self._launched = False
        if action_resets_cdp(action):
            await self._reset_cdp()
        elif action_invalidates_cdp(action):
            self._invalidate_cdp()

    def _cdp(self) -> AsyncCDPController:
        if self._cdp_controller is None:
            from agentbrowser.cdp import AsyncCDPController

            self._cdp_controller = AsyncCDPController(self)
        return self._cdp_controller

    def _invalidate_cdp(self) -> None:
        if self._cdp_controller is not None:
            self._cdp_controller.invalidate()

    async def _reset_cdp(self) -> None:
        if self._cdp_controller is not None:
            await self._cdp_controller.close()
            self._cdp_controller = None

    async def _connect(self) -> Mapping[str, Any]:
        """Attach to the configured CDP target without navigating.

        This internal handshake is valid for browsers created through
        `AsyncBrowser.attach(CDPTarget(...))`.

        Returns
        -------
        Mapping[str, object]
            Native attach response data.
        """
        if (
            self._launch_configuration.cdp_url is None
            and self._launch_configuration.cdp_port is None
        ):
            raise RuntimeError("CDP connection requires AsyncBrowser.attach(CDPTarget(...))")
        return await self._launch_native()

    async def _launch_process(
        self,
        *,
        options: LaunchOptions | None = None,
    ) -> Mapping[str, Any]:
        """Launch a native browser process using explicit process options.

        Parameters
        ----------
        options
            Optional full replacement `LaunchOptions` for this launch command.

        Returns
        -------
        Mapping[str, object]
            Native launch response data.
        """
        if (
            self._launch_configuration.cdp_url is not None
            or self._launch_configuration.cdp_port is not None
        ):
            raise RuntimeError("local launch cannot use CDPTarget")
        return await self._launch_native(options=options)

    async def _launch_native(
        self,
        *,
        options: LaunchOptions | None = None,
    ) -> Mapping[str, Any]:
        launch_params = self._launch_configuration.command_params(options=options)
        await self._prepare_install_for_launch(launch_params)
        data = await self._command("launch", **launch_params)
        self._launched = True
        return data

    async def _prepare_install_for_action(self, action: str, params: dict[str, Any]) -> None:
        if not self._auto_install or self._install_prepared or self._launched:
            return
        if action == "launch":
            await self._prepare_install_for_launch(params)
            return
        if action in _SKIP_AUTO_INSTALL_ACTIONS:
            return
        if not _uses_local_chrome(self._launch_configuration.command_params()):
            return
        await asyncio.to_thread(ensure_installed)
        self._install_prepared = True

    async def _prepare_install_for_launch(self, launch_params: dict[str, Any]) -> None:
        if not self._auto_install or self._install_prepared:
            return
        if not _uses_local_chrome(launch_params):
            return
        result = await asyncio.to_thread(ensure_installed)
        launch_params["executablePath"] = str(result.executable_path)
        self._install_prepared = True

    async def _close_browser(self) -> CloseResult:
        if self._cdp_controller is not None:
            with suppress(Exception):
                await self._cdp_controller.close()
            self._cdp_controller = None
        response = await self._session.shutdown_native()
        if response is None:
            return CloseResult(closed=True)
        checked = _checked_response("close", replace(response, action="close"))
        await self._record_successful_action(checked)
        return close_result_from_data(_require_response_data_mapping(checked, action="close"))

    async def _close_once(self, *, timeout: float) -> CloseResult:
        result = CloseResult(closed=True)
        try:
            result = await asyncio.wait_for(self._close_browser(), timeout=timeout)
        finally:
            await self._session.aclose(timeout=timeout)
        if result.save_error is not None:
            raise RestoreSaveError(result)
        return result

    async def close(self, *, timeout: float = 5.0) -> CloseResult:
        """Close the browser and return terminal restore-save state."""
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._close_once(timeout=timeout))
        return await asyncio.shield(self._close_task)

    async def _snapshot_data(
        self,
        spec: SnapshotSpec | None = None,
    ) -> SnapshotData:
        spec = spec or SnapshotSpec(interactive=False)
        return await self._command(
            "snapshot",
            _decode=lambda data: snapshot_from_data(data, spec=spec),
            selector=optional(spec.selector),
            interactive=spec.interactive,
            compact=spec.compact,
            maxDepth=optional(spec.max_depth),
            urls=spec.urls,
        )

    async def _diff_snapshot(
        self,
        baseline: str | Path | SnapshotData | None = None,
        *,
        selector: str | None = None,
        compact: bool = False,
        max_depth: int | None = None,
    ) -> SnapshotDiff:
        """Compare the current snapshot with a baseline snapshot.

        Parameters
        ----------
        baseline
            Baseline snapshot text, path, `Snapshot`, or `None` to let the native
            engine choose its baseline behavior.
        selector
            Optional selector that scopes the snapshot.
        compact
            Request compact snapshot text.
        max_depth
            Maximum accessibility tree depth.

        Returns
        -------
        SnapshotDiff
            Parsed diff counts and raw response data.
        """
        baseline_value: str | Path | None
        if isinstance(baseline, SnapshotData):
            selector = baseline.spec.selector if selector is None else selector
            compact = baseline.spec.compact
            max_depth = baseline.spec.max_depth if max_depth is None else max_depth
        baseline_value = baseline.text if isinstance(baseline, SnapshotData) else baseline
        return await self._command(
            "diff_snapshot",
            _decode=snapshot_diff_from_data,
            baseline=optional(
                path_value(baseline_value) if isinstance(baseline_value, Path) else baseline_value
            ),
            selector=optional(selector),
            compact=compact,
            maxDepth=optional(max_depth),
        )

    async def activate(self) -> Self:
        """Bring the browser window to the foreground."""
        await self._command("bringtofront", _decode=lambda _data: self)
        return self
