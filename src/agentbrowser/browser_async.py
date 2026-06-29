from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Self, cast, overload
from weakref import proxy as weak_proxy

from agentbrowser._browser_common import (
    ConfirmationTarget,
    action_clears_pending_confirmation,
    action_closes_browser,
    action_invalidates_cdp,
    action_sets_launched,
    confirmation_id,
    response_confirmation_id,
    response_data_mapping,
)
from agentbrowser.agent_async import AsyncAgent, AsyncAgentSnapshot
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
    AsyncFind,
    AsyncKeyboard,
    AsyncMouse,
    AsyncNetwork,
    AsyncPage,
    AsyncRestore,
    AsyncRuntime,
    AsyncScripts,
    AsyncState,
    AsyncStorage,
    AsyncTabs,
)
from agentbrowser.install import ensure_installed
from agentbrowser.launch import (
    BrowserSessionOptions,
    BrowserSessionOptionsInput,
    CDPAttachInput,
    LaunchConfiguration,
    LaunchOptionsInput,
    normalize_session,
)
from agentbrowser.models import (
    ActionConfirmationRequired,
    BrowserResponse,
    DashboardOptions,
    JSONMapping,
    JSONValue,
    RestoreOptions,
    Snapshot,
    SnapshotDiff,
    snapshot_from_data,
)
from agentbrowser.session import (
    _checked_response,
    _require_response_data_mapping,
    _try_unwrap_confirmed_response,
)
from agentbrowser.session_async import AsyncNativeSession

if TYPE_CHECKING:
    from agentbrowser.cdp import AsyncCDPController


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

    async def start(self, options: DashboardOptions | None = None) -> Mapping[str, Any]:
        """Start dashboard observability and return the stream status."""
        self._browser._session.set_dashboard(True if options is None else options)
        return await self._browser._command("stream_status")


@dataclass(frozen=True, slots=True)
class AsyncPendingAction:
    """Native action awaiting explicit async confirmation or denial."""

    _browser: AsyncBrowser
    confirmation_id: str
    action: str
    data: Mapping[str, Any]

    async def confirm(self) -> Mapping[str, Any]:
        """Confirm this pending action."""
        return await self._browser.confirm(self)

    async def deny(self) -> Mapping[str, Any]:
        """Deny this pending action."""
        return await self._browser.deny(self)


class AsyncBrowser:
    """Async controller for the native agent-browser engine.

    `AsyncBrowser` mirrors `Browser` while keeping native calls off the event
    loop. It owns one native browser session and exposes async command
    namespaces such as `page`, `find`, `capture`, `tabs`, `network`, and `cdp`.
    Construction is lazy. Use `await AsyncBrowser.launch({"headless": True})`
    to create and start a browser, `await AsyncBrowser.attach({"port": 9222})`
    to attach to a running browser, or `AsyncBrowser.from_session(...)` to name
    a restorable session before the first native command.

    Example:
        ```python
        from agentbrowser import AsyncBrowser

        browser = await AsyncBrowser.launch({"headless": True})
        async with browser:
            await browser.page.open("https://example.com")
            page = await browser.agent.observe()
            print(page.text)

            await browser.find.text("Learn more").click()
            await browser.page.wait_for_url("*://www.iana.org/*")
            print(await browser.page.url())
        ```
    """

    def __init__(
        self,
        *,
        session: BrowserSessionOptionsInput | None = None,
        native_session: AsyncNativeSession | None = None,
    ) -> None:
        base_options = normalize_session(session)
        launch_configuration = LaunchConfiguration.from_public_options(
            allowed_domains=base_options.allowed_domains
        )
        self._init(
            launch_configuration,
            session=base_options,
            native_session=native_session,
        )

    @classmethod
    def _from_configuration(
        cls,
        launch_configuration: LaunchConfiguration,
        *,
        session: BrowserSessionOptionsInput | None = None,
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
        session: BrowserSessionOptionsInput | None = None,
        native_session: AsyncNativeSession | None = None,
    ) -> None:
        session_config = normalize_session(session)
        self._session = native_session or AsyncNativeSession(
            session=session_config.session_id,
            restore=session_config.restore,
            namespace=session_config.namespace,
            default_timeout_ms=session_config.default_timeout_ms,
            allowed_domains=session_config.allowed_domains,
            engine=launch_configuration.engine,
            action_policy=session_config.action_policy,
            confirm_actions=session_config.confirm_actions,
            no_auto_dialog=session_config.no_auto_dialog,
        )
        if native_session is not None and session_config.allowed_domains is not None:
            self._session.set_allowed_domains(session_config.allowed_domains)
        default_session_config = BrowserSessionOptions()
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
        if (
            native_session is not None
            and session_config.default_timeout_ms != default_session_config.default_timeout_ms
        ):
            raise ValueError(
                "default_timeout_ms must be set on AsyncNativeSession "
                "when native_session is supplied"
            )
        if native_session is not None and session_config.action_policy is not None:
            raise ValueError(
                "action_policy must be set on AsyncNativeSession when native_session is supplied"
            )
        if native_session is not None and session_config.confirm_actions is not None:
            raise ValueError(
                "confirm_actions must be set on AsyncNativeSession when native_session is supplied"
            )
        if (
            native_session is not None
            and session_config.no_auto_dialog != default_session_config.no_auto_dialog
        ):
            raise ValueError(
                "no_auto_dialog must be set on AsyncNativeSession when native_session is supplied"
            )
        self._launch_configuration = launch_configuration
        self._auto_install = native_session is None
        self._install_prepared = False
        self._launched = False
        self._cdp_controller: AsyncCDPController | None = None

        command_target = cast(AsyncCommandTarget, weak_proxy(self))
        self.active_frame = AsyncActiveFrame(command_target)
        self.agent = AsyncAgent(self)
        self.capture = AsyncCapture(command_target)
        self.cdp = AsyncCDP(self)
        self.clipboard = AsyncClipboard(command_target)
        self.cookies = AsyncCookies(command_target)
        self.dialogs = AsyncDialogs(command_target)
        self.diagnostics = AsyncDiagnostics(command_target)
        self.dashboard = AsyncDashboard(self)
        self.diff = AsyncDiff(command_target)
        self.downloads = AsyncDownloads(command_target)
        self.find = AsyncFind(self)
        self.keyboard = AsyncKeyboard(command_target)
        self.mouse = AsyncMouse(command_target)
        self.native = AsyncNative(self)
        self.network = AsyncNetwork(command_target)
        self.page = AsyncPage(self)
        self.restore = AsyncRestore(command_target)
        self.runtime = AsyncRuntime(command_target)
        self.scripts = AsyncScripts(self)
        self.state = AsyncState(command_target)
        self.storage = AsyncStorage(command_target)
        self.tabs = AsyncTabs(command_target)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: object, _exc: object, _tb: object) -> None:
        if exc_type is None:
            await self.aclose()
            return
        with suppress(BaseException):
            await self.aclose()

    @property
    def is_launched(self) -> bool:
        """Whether the native browser has been launched in this session."""
        return self._launched

    @classmethod
    async def launch(
        cls,
        options: LaunchOptionsInput | None = None,
        *,
        session: BrowserSessionOptionsInput | None = None,
        native_session: AsyncNativeSession | None = None,
    ) -> AsyncBrowser:
        """Create a browser and start the native browser process."""
        session_config = normalize_session(session)
        browser = cls._from_configuration(
            LaunchConfiguration.from_public_options(
                options,
                allowed_domains=session_config.allowed_domains,
            ),
            session=session_config,
            native_session=native_session,
        )
        await browser.launch_process()
        return browser

    @classmethod
    async def attach(
        cls,
        target: CDPAttachInput,
        *,
        launch: LaunchOptionsInput | None = None,
        session: BrowserSessionOptionsInput | None = None,
        native_session: AsyncNativeSession | None = None,
    ) -> AsyncBrowser:
        """Create a browser and attach to a running CDP target."""
        session_config = normalize_session(session)
        browser = cls._from_configuration(
            LaunchConfiguration.from_public_options(
                launch,
                attach=target,
                allowed_domains=session_config.allowed_domains,
            ),
            session=session_config,
            native_session=native_session,
        )
        await browser.connect()
        return browser

    @classmethod
    def from_session(
        cls,
        session_id: str,
        *,
        restore: RestoreOptions | None = None,
        launch: LaunchOptionsInput | None = None,
        session: BrowserSessionOptionsInput | None = None,
        native_session: AsyncNativeSession | None = None,
    ) -> AsyncBrowser:
        """Create a lazy async browser controller for a named native session."""
        base_options = normalize_session(session)
        if base_options.session_id not in {None, session_id}:
            raise ValueError("session.session_id must match session_id")
        if restore is not None and base_options.restore is not None:
            raise ValueError("pass restore or session.restore, not both")
        resolved_options = replace(
            base_options,
            session_id=session_id,
            restore=restore or base_options.restore,
        )
        return cls._from_configuration(
            LaunchConfiguration.from_public_options(
                launch,
                allowed_domains=resolved_options.allowed_domains,
            ),
            session=resolved_options,
            native_session=native_session,
        )

    async def observe(
        self,
        *,
        selector: str | None = None,
        interactive: bool = True,
        compact: bool = False,
        max_depth: int | None = None,
        urls: bool = False,
    ) -> AsyncAgentSnapshot:
        """Capture an accessibility snapshot bound to this browser.

        Parameters
        ----------
        selector
            Optional selector that scopes the snapshot.
        interactive
            Include interactable element refs when supported by the native engine.
        compact
            Request compact snapshot text.
        max_depth
            Maximum accessibility tree depth.
        urls
            Include URLs in snapshot output when available.

        Returns
        -------
        AsyncAgentSnapshot
            Snapshot wrapper whose refs can be acted on directly.
        """
        return await self.agent.observe(
            selector=selector,
            interactive=interactive,
            compact=compact,
            max_depth=max_depth,
            urls=urls,
        )

    async def _command(self, action: str, **params: Any) -> JSONMapping:
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
        data = await self._native_data(action, expect="object", **params)
        return cast(JSONMapping, data)

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
        except ActionConfirmationRequired as err:
            if err.confirmation_id is not None:
                err.pending_action = self.pending_action(err)
            raise
        self._record_successful_action(response.action)
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
                self._record_successful_action(response.action)
            return response
        if response.success:
            self._record_successful_action(response.action)
        return response

    def pending_action(
        self,
        confirmation: ActionConfirmationRequired | BrowserResponse | str,
    ) -> AsyncPendingAction:
        """Return a named pending action for a confirmation exception, response, or id."""
        if isinstance(confirmation, BrowserResponse):
            pending_id = response_confirmation_id(confirmation)
            action = confirmation.action
            data = response_data_mapping(confirmation) or {}
        else:
            pending_id = confirmation_id(confirmation)
            if isinstance(confirmation, ActionConfirmationRequired):
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
            data=dict(data),
        )

    def _record_successful_action(self, action: str) -> None:
        if action_sets_launched(action):
            self._launched = True
        elif action_clears_pending_confirmation(action) and action_closes_browser(action):
            self._launched = False
        if action_invalidates_cdp(action):
            self._invalidate_cdp()

    def _cdp(self) -> AsyncCDPController:
        if self._cdp_controller is None:
            from agentbrowser.cdp import AsyncCDPController

            self._cdp_controller = AsyncCDPController(self)
        return self._cdp_controller

    def _invalidate_cdp(self) -> None:
        if self._cdp_controller is not None:
            self._cdp_controller.invalidate()

    async def connect(self) -> Mapping[str, Any]:
        """Attach to the configured CDP target without navigating.

        `connect()` is only valid for browsers created through
        `AsyncBrowser.attach(CDPAttach(...))`.

        Returns
        -------
        Mapping[str, object]
            Native attach response data.
        """
        if (
            self._launch_configuration.cdp_url is None
            and self._launch_configuration.cdp_port is None
        ):
            raise RuntimeError("connect requires AsyncBrowser.attach(CDPAttach(...))")
        return await self._launch_native()

    async def launch_process(
        self,
        *,
        options: LaunchOptionsInput | None = None,
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
            raise RuntimeError("launch_process cannot use CDPAttach; call connect()")
        return await self._launch_native(options=options)

    async def _launch_native(
        self,
        *,
        options: LaunchOptionsInput | None = None,
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

    async def _close_browser(self) -> None:
        if self._cdp_controller is not None:
            with suppress(Exception):
                await self._cdp_controller.close()
            self._cdp_controller = None
        response = await self._session.shutdown_native()
        if response is not None:
            _checked_response("close", replace(response, action="close"))
            self._record_successful_action("close")

    async def close(self, *, timeout: float = 5.0) -> None:
        """Close the browser and stop the async native worker."""
        try:
            if not self._session.closed:
                await asyncio.wait_for(self._close_browser(), timeout=timeout)
        finally:
            await self._session.aclose(timeout=timeout)

    aclose = close

    async def confirm(
        self,
        confirmation: ConfirmationTarget,
    ) -> Mapping[str, Any]:
        """Confirm a pending native action.

        Parameters
        ----------
        confirmation
            Confirmation exception, pending action, or confirmation id.

        Returns
        -------
        Mapping[str, object]
            Native response data for the confirmed action.
        """
        pending_id = (
            confirmation.confirmation_id
            if isinstance(confirmation, AsyncPendingAction)
            else confirmation_id(confirmation)
        )
        if pending_id is None:
            raise ValueError("confirm requires an ActionConfirmationRequired or confirmation id")
        return await self._command("confirm", confirmation_id=pending_id)

    async def deny(
        self,
        confirmation: ConfirmationTarget,
    ) -> Mapping[str, Any]:
        """Deny a pending native action.

        Parameters
        ----------
        confirmation
            Confirmation exception, pending action, or confirmation id.

        Returns
        -------
        Mapping[str, object]
            Native response data for the denial command.
        """
        pending_id = (
            confirmation.confirmation_id
            if isinstance(confirmation, AsyncPendingAction)
            else confirmation_id(confirmation)
        )
        if pending_id is None:
            raise ValueError("deny requires an ActionConfirmationRequired or confirmation id")
        return await self._command("deny", confirmation_id=pending_id)

    async def snapshot(
        self,
        *,
        selector: str | None = None,
        interactive: bool = False,
        compact: bool = False,
        max_depth: int | None = None,
        urls: bool = False,
    ) -> Snapshot:
        """Return a raw accessibility snapshot.

        Parameters
        ----------
        selector
            Optional selector that scopes the snapshot.
        interactive
            Include interactable element refs when supported by the native engine.
        compact
            Request compact snapshot text.
        max_depth
            Maximum accessibility tree depth.
        urls
            Include URLs in snapshot output when available.

        Returns
        -------
        Snapshot
            Parsed snapshot text, refs, origin, and raw response data.
        """
        data = await self._command(
            "snapshot",
            selector=optional(selector),
            interactive=interactive,
            compact=compact,
            maxDepth=optional(max_depth),
            urls=urls,
        )
        return snapshot_from_data(data)

    async def diff_snapshot(
        self,
        baseline: str | Path | Snapshot | None = None,
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
        baseline_value = baseline.text if isinstance(baseline, Snapshot) else baseline
        return await self.diff.snapshot(
            baseline=baseline_value,
            selector=selector,
            compact=compact,
            max_depth=max_depth,
        )

    async def set_viewport(
        self,
        width: int,
        height: int,
        *,
        device_scale_factor: float = 1.0,
        mobile: bool = False,
    ) -> Mapping[str, Any]:
        """Set the browser viewport.

        Parameters
        ----------
        width, height
            Viewport size in CSS pixels.
        device_scale_factor
            Device scale factor used for emulation.
        mobile
            Whether to emulate a mobile viewport.

        Returns
        -------
        Mapping[str, object]
            Native response data.
        """
        return await self._command(
            "viewport",
            **viewport_params(
                width,
                height,
                device_scale_factor=device_scale_factor,
                mobile=mobile,
            ),
        )

    async def set_device(self, name: str) -> Mapping[str, Any]:
        """Set a named device preset."""
        return await self._command("device", name=name)

    async def set_headers(self, headers: Mapping[str, str]) -> Mapping[str, Any]:
        """Set extra HTTP headers for subsequent page requests."""
        return await self._command("headers", headers=dict(headers))

    async def set_offline(self, enabled: bool = True) -> Mapping[str, Any]:
        """Enable or disable offline network emulation."""
        return await self._command("offline", offline=enabled)

    async def set_user_agent(self, user_agent: str) -> Mapping[str, Any]:
        """Set the browser user-agent string."""
        return await self._command("useragent", userAgent=user_agent)

    async def set_media(
        self,
        *,
        media: str | None = None,
        color_scheme: str | None = None,
        reduced_motion: str | None = None,
        features: Mapping[str, str] | None = None,
    ) -> Mapping[str, Any]:
        """Set emulated CSS media features."""
        return await self._command(
            "set_media",
            **media_params(
                media=media,
                color_scheme=color_scheme,
                reduced_motion=reduced_motion,
                features=features,
            ),
        )

    async def set_timezone(self, timezone_id: str) -> Mapping[str, Any]:
        """Set the emulated timezone id, for example `Europe/Vienna`."""
        return await self._command("timezone", timezoneId=timezone_id)

    async def set_locale(self, locale: str) -> Mapping[str, Any]:
        """Set the emulated browser locale, for example `en-US`."""
        return await self._command("locale", locale=locale)

    async def set_geolocation(
        self,
        latitude: float,
        longitude: float,
        *,
        accuracy: float | None = None,
    ) -> Mapping[str, Any]:
        """Set emulated geolocation coordinates."""
        return await self._command(
            "geolocation",
            **geolocation_params(latitude, longitude, accuracy=accuracy),
        )

    async def set_permissions(
        self,
        permissions: Sequence[str],
        *,
        origin: str | None = None,
    ) -> Mapping[str, Any]:
        """Grant browser permissions, optionally scoped to an origin."""
        return await self._command("permissions", **permissions_params(permissions, origin=origin))

    async def bring_to_front(self) -> Mapping[str, Any]:
        """Bring the browser window to the foreground."""
        return await self._command("bringtofront")
