from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Generic, Literal, Self, TypeVar, cast, overload
from weakref import proxy as weak_proxy

from agentbrowser._browser_common import (
    CDP_URL_ACTIONS,
    INTERNAL_SHUTDOWN_ACTION,
    action_clears_pending_confirmation,
    action_closes_browser,
    action_invalidates_cdp,
    action_resets_cdp,
    action_sets_launched,
    confirmation_id,
    response_browser_launched,
    response_confirmation_id,
    response_data_mapping,
)
from agentbrowser.command_params import (
    geolocation_params,
    media_params,
    permissions_params,
    viewport_params,
)
from agentbrowser.domains import (
    CDP,
    Clipboard,
    CommandTarget,
    Cookies,
    Diagnostics,
    Dialogs,
    Diff,
    Downloads,
    Keyboard,
    Mouse,
    Network,
    Page,
    Scripts,
    Session,
    State,
    Storage,
    Tabs,
    WebMCP,
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
    OMIT,
    BrowserResponse,
    CloseResult,
    ConfirmationRequired,
    JSONMapping,
    JSONValue,
    RestoreSaveError,
    close_result_from_data,
)
from agentbrowser.session import (
    NativeSession,
    _checked_response,
    _require_response_data_mapping,
    _try_unwrap_confirmed_response,
)

if TYPE_CHECKING:
    from agentbrowser.cdp import CDPController
    from agentbrowser.health import BrowserCapabilities, HealthCheck

T = TypeVar("T")
U = TypeVar("U")

_SKIP_AUTO_INSTALL_ACTIONS = {
    "",
    INTERNAL_SHUTDOWN_ACTION,
    "close",
    "read",
    "har_stop",
    "credentials_set",
    "credentials_get",
    "credentials_delete",
    "credentials_list",
    "auth_save",
    "auth_show",
    "auth_delete",
    "auth_list",
    "confirm",
    "deny",
    "state_list",
    "state_show",
    "state_clear",
    "state_clean",
    "state_rename",
    "device_list",
    "stream_enable",
    "stream_disable",
    "stream_status",
    "session_info",
}


@dataclass(frozen=True, slots=True)
class Native:
    """Raw native command boundary for a `Browser`."""

    _browser: Browser

    def execute(self, action: str, **params: Any) -> BrowserResponse:
        """Run a native command and return the response envelope."""
        return self._browser._native_execute(action, **params)

    @overload
    def data(self, action: str, **params: Any) -> JSONMapping: ...

    @overload
    def data(
        self,
        action: str,
        *,
        expect: Literal["object"],
        **params: Any,
    ) -> JSONMapping: ...

    @overload
    def data(
        self,
        action: str,
        *,
        expect: Literal["any"],
        **params: Any,
    ) -> JSONValue: ...

    def data(
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
        return self._browser._native_data(action, expect=expect, **params)


@dataclass(frozen=True, slots=True)
class Dashboard:
    """Dashboard observability lifecycle for a `Browser`."""

    _browser: Browser

    def status(self) -> Mapping[str, Any]:
        """Return the configured dashboard stream status."""
        return self._browser._command("stream_status")

    def stop(self) -> None:
        """Stop dashboard streaming for this browser."""
        self._browser._command("stream_disable", _decode=lambda _data: None)


@dataclass(frozen=True, slots=True)
class Emulation:
    """Browser environment and device emulation."""

    _browser: Browser

    def viewport(
        self,
        width: int,
        height: int,
        *,
        device_scale_factor: float = 1.0,
        mobile: bool = False,
    ) -> None:
        """Set viewport dimensions in CSS pixels."""
        self._browser._command(
            "viewport",
            _decode=lambda _data: None,
            **viewport_params(
                width,
                height,
                device_scale_factor=device_scale_factor,
                mobile=mobile,
            ),
        )

    def device(self, name: str) -> None:
        """Apply a named device preset."""
        self._browser._command("device", _decode=lambda _data: None, name=name)

    def headers(self, headers: Mapping[str, str]) -> None:
        """Set extra HTTP headers."""
        self._browser._command(
            "headers",
            _decode=lambda _data: None,
            headers=dict(headers),
        )

    def offline(self, enabled: bool = True) -> None:
        """Set network offline emulation."""
        self._browser._command(
            "offline",
            _decode=lambda _data: None,
            offline=enabled,
        )

    def user_agent(self, value: str) -> None:
        """Set the browser user agent."""
        self._browser._command(
            "useragent",
            _decode=lambda _data: None,
            userAgent=value,
        )

    def media(
        self,
        *,
        media: str | None = None,
        color_scheme: str | None = None,
        reduced_motion: str | None = None,
        features: Mapping[str, str] | None = None,
    ) -> None:
        """Set CSS media emulation."""
        self._browser._command(
            "set_media",
            _decode=lambda _data: None,
            **media_params(
                media=media,
                color_scheme=color_scheme,
                reduced_motion=reduced_motion,
                features=features,
            ),
        )

    def timezone(self, timezone_id: str) -> None:
        """Set the emulated timezone."""
        self._browser._command(
            "timezone",
            _decode=lambda _data: None,
            timezoneId=timezone_id,
        )

    def locale(self, locale: str) -> None:
        """Set the emulated locale."""
        self._browser._command("locale", _decode=lambda _data: None, locale=locale)

    def geolocation(
        self,
        latitude: float,
        longitude: float,
        *,
        accuracy: float | None = None,
    ) -> None:
        """Set emulated coordinates."""
        self._browser._command(
            "geolocation",
            _decode=lambda _data: None,
            **geolocation_params(latitude, longitude, accuracy=accuracy),
        )

    def permissions(
        self,
        permissions: Sequence[str],
        *,
        origin: str | None = None,
    ) -> None:
        """Grant permissions for an optional origin."""
        self._browser._command(
            "permissions",
            _decode=lambda _data: None,
            **permissions_params(permissions, origin=origin),
        )


@dataclass(frozen=True, slots=True)
class PendingAction(Generic[T]):
    """Native action awaiting explicit confirmation or denial."""

    _browser: Browser
    confirmation_id: str
    action: str
    details: Mapping[str, Any]
    _decode: Callable[[JSONMapping], T] | None = None
    _expect: Literal["object", "any"] = "object"
    _complete: Callable[[Any], T] | None = None

    def confirm(self) -> T:
        """Confirm this pending action and decode its original return type."""
        try:
            result: Any = self._browser._native_data(
                "confirm",
                expect=self._expect,
                confirmation_id=self.confirmation_id,
            )
        except ConfirmationRequired as error:
            if isinstance(error.pending, PendingAction):
                error.pending = replace(
                    error.pending,
                    _decode=self._decode,
                    _expect=self._expect,
                    _complete=self._complete,
                )
            raise
        if self._decode is not None:
            result = self._decode(cast(JSONMapping, result))
        return self._complete(result) if self._complete is not None else cast(T, result)

    def deny(self) -> None:
        """Deny this pending action."""
        self._browser._command("deny", confirmation_id=self.confirmation_id)

    def map(self, complete: Callable[[T], U]) -> PendingAction[U]:
        """Complete a higher-level operation after native confirmation."""
        previous = self._complete
        if previous is None:
            composed: Callable[[Any], U] = complete
        else:

            def composed(value: Any) -> U:
                try:
                    intermediate = previous(value)
                except ConfirmationRequired as error:
                    if error.pending is not None:
                        error.pending = error.pending.map(complete)
                    raise
                return complete(intermediate)

        return cast(PendingAction[U], replace(self, _complete=composed))


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
        native_session: NativeSession | None = None,
    ) -> Browser:
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
        native_session: NativeSession | None = None,
    ) -> None:
        session_config = normalize_session(session)
        self._session = native_session or NativeSession(
            session=session_config.session_id,
            restore=session_config.restore,
            namespace=session_config.namespace,
            default_timeout_ms=session_config._timeout_ms(),
            allowed_domains=session_config._allowed_domains(),
            engine=launch_configuration.engine,
            action_policy=session_config.action_policy,
            confirm_actions=session_config.confirm_actions,
            no_auto_dialog=not session_config.auto_dialogs,
            pin_tab=session_config.pin_tab,
            dashboard=session_config.dashboard,
        )
        if native_session is not None and session_config.allowed_domains:
            self._session.set_allowed_domains(session_config._allowed_domains())
        default_session_config = SessionOptions()
        if native_session is not None and session_config.namespace is not None:
            raise ValueError(
                "namespace must be set on NativeSession when native_session is supplied"
            )
        if native_session is not None and session_config.session_id is not None:
            raise ValueError(
                "session_id must be set on NativeSession when native_session is supplied"
            )
        if native_session is not None and session_config.restore is not None:
            raise ValueError("restore must be set on NativeSession when native_session is supplied")
        if native_session is not None and session_config.timeout != default_session_config.timeout:
            raise ValueError(
                "default_timeout_ms must be set on NativeSession when native_session is supplied"
            )
        if native_session is not None and session_config.action_policy is not None:
            raise ValueError(
                "action_policy must be set on NativeSession when native_session is supplied"
            )
        if native_session is not None and session_config.confirm_actions:
            raise ValueError(
                "confirm_actions must be set on NativeSession when native_session is supplied"
            )
        if native_session is not None and session_config.pin_tab is not None:
            raise ValueError("pin_tab must be set on NativeSession when native_session is supplied")
        if (
            native_session is not None
            and session_config.auto_dialogs != default_session_config.auto_dialogs
        ):
            raise ValueError(
                "no_auto_dialog must be set on NativeSession when native_session is supplied"
            )
        if native_session is not None and session_config.dashboard is not None:
            raise ValueError(
                "dashboard must be set on NativeSession when native_session is supplied"
            )
        self._launch_configuration = launch_configuration
        self._auto_install = native_session is None
        self._install_prepared = False
        self._launched = False
        self._closed = False
        self._close_result: CloseResult | None = None
        self._close_error: BaseException | None = None
        self._cdp_controller: CDPController | None = None
        self._pending_cdp_invalidations: set[str] = set()
        self._ref_generation = 0

        command_target = cast(CommandTarget, weak_proxy(self))
        browser_proxy = cast(Browser, weak_proxy(self))
        self._page_target_id: str | None = None
        self._active_target_id: str | None = None
        self.cdp = CDP(browser_proxy)
        self.clipboard = Clipboard(command_target)
        self.cookies = Cookies(command_target)
        self.diagnostics = Diagnostics(command_target)
        self.dashboard = Dashboard(browser_proxy)
        self.dialogs = Dialogs(command_target)
        self.diff = Diff(command_target)
        self.downloads = Downloads(command_target)
        self.emulation = Emulation(browser_proxy)
        self.keyboard = Keyboard(command_target)
        self.mouse = Mouse(command_target)
        self.native = Native(browser_proxy)
        self.network = Network(command_target)
        self.scripts = Scripts(command_target)
        self.session = Session(command_target)
        self.state = State(command_target)
        self.storage = Storage(command_target)
        self.tabs = Tabs(command_target)
        self.webmcp = WebMCP(command_target)

    def __enter__(self) -> Self:
        return self

    @property
    def page(self) -> Page:
        """Return a main-document handle for the configured page target."""
        return Page(self, target_id=self._page_target_id or self._active_target_id)

    def __exit__(self, exc_type: object, _exc: object, _tb: object) -> None:
        if exc_type is None:
            self.close()
            return
        with suppress(BaseException):
            self.close()

    def __repr__(self) -> str:
        return f"Browser(launched={self.is_launched!r}, closed={self.closed!r})"

    @property
    def is_launched(self) -> bool:
        """Whether the native browser has been launched in this session."""
        return self._launched

    @property
    def closed(self) -> bool:
        """Whether this browser has been closed."""
        return self._closed

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
            browser._launch_process()
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
            browser._connect()
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map(lambda _value: browser)
            raise
        return browser

    @overload
    def _command(
        self,
        action: str,
        *,
        _decode: Callable[[JSONMapping], T],
        **params: Any,
    ) -> T: ...

    @overload
    def _command(
        self,
        action: str,
        *,
        _decode: None = None,
        **params: Any,
    ) -> JSONMapping: ...

    def _command(
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

        Raises
        ------
        ConfirmationRequired
            If the native policy requires confirmation before execution.
        BrowserError
            If the native command fails or returns non-object response data.
        """
        try:
            data = self._native_data(action, expect="object", **params)
        except ConfirmationRequired as err:
            if err.confirmation_id is not None:
                err.pending = self._pending_action(err, decoder=_decode)
            raise
        mapping = cast(JSONMapping, data)
        return _decode(mapping) if _decode is not None else mapping

    def _native_data(
        self,
        action: str,
        *,
        expect: str = "object",
        **params: Any,
    ) -> JSONMapping | JSONValue:
        self._ensure_open()
        if expect not in {"object", "any"}:
            raise ValueError('expect must be "object" or "any"')
        self._prepare_install_for_action(action, params)
        pending_id, compound_invalidation = self._cdp_invalidation_context(action, params)
        confirmation_consumed = False
        try:
            raw_response = self._session.execute(action, **params)
            self._record_native_metadata(raw_response)
            confirmation_consumed = action == "confirm" and raw_response.success
            response = _checked_response(action, raw_response)
        except ConfirmationRequired as err:
            self._continue_cdp_invalidation(
                pending_id,
                err.confirmation_id,
                compound_invalidation,
            )
            if err.confirmation_id is not None:
                err.pending = self._pending_action(
                    err,
                    expect=cast(Literal["object", "any"], expect),
                )
            raise
        except BaseException:
            if compound_invalidation:
                self._invalidate_cdp()
            if pending_id is not None and confirmation_consumed:
                self._pending_cdp_invalidations.discard(pending_id)
            raise
        if pending_id is not None and (action == "deny" or confirmation_consumed):
            self._pending_cdp_invalidations.discard(pending_id)
        self._record_successful_action(
            response,
            params=params,
            force_cdp_invalidation=compound_invalidation,
        )
        if expect == "any":
            return response.data
        return _require_response_data_mapping(response)

    def _native_execute(self, action: str, **params: Any) -> BrowserResponse:
        self._ensure_open()
        self._prepare_install_for_action(action, params)
        pending_id, compound_invalidation = self._cdp_invalidation_context(action, params)
        try:
            response = self._session.execute(action, **params)
            self._record_native_metadata(response)
        except BaseException:
            if compound_invalidation:
                self._invalidate_cdp()
            raise
        confirmation_consumed = action == "confirm" and response.success
        if confirmation_consumed:
            response = _try_unwrap_confirmed_response(response)
        data = response_data_mapping(response)
        if data is not None and bool(data.get("confirmation_required")):
            self._continue_cdp_invalidation(
                pending_id,
                response_confirmation_id(response),
                compound_invalidation,
            )
            return response
        if pending_id is not None and (
            (action == "deny" and response.success) or confirmation_consumed
        ):
            self._pending_cdp_invalidations.discard(pending_id)
        if confirmation_consumed:
            if response.success:
                self._record_successful_action(
                    response,
                    params=params,
                    force_cdp_invalidation=compound_invalidation,
                )
            elif compound_invalidation:
                self._invalidate_cdp()
            return response
        if response.success:
            self._record_successful_action(
                response,
                params=params,
                force_cdp_invalidation=compound_invalidation,
            )
        elif compound_invalidation:
            self._invalidate_cdp()
        return response

    def _pending_action(
        self,
        confirmation: ConfirmationRequired[Any] | BrowserResponse | str,
        *,
        decoder: Callable[[JSONMapping], T] | None = None,
        expect: Literal["object", "any"] = "object",
    ) -> PendingAction[T]:
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
        return PendingAction(
            _browser=self,
            confirmation_id=pending_id,
            action=action,
            details=dict(data),
            _decode=decoder,
            _expect=expect,
        )

    def _cdp_invalidation_context(
        self,
        action: str,
        params: Mapping[str, Any],
    ) -> tuple[str | None, bool]:
        confirmation_value = (
            params.get("confirmation_id") if action in {"confirm", "deny"} else None
        )
        pending_id = str(confirmation_value) if confirmation_value is not None else None
        # URL commands can fail after navigation. Preserve invalidation across
        # confirmation because the confirmed response omits the URL.
        compound_invalidation = action in CDP_URL_ACTIONS and action_invalidates_cdp(action, params)
        if action == "confirm" and pending_id in self._pending_cdp_invalidations:
            compound_invalidation = True
        return pending_id, compound_invalidation

    def _continue_cdp_invalidation(
        self,
        previous_id: str | None,
        next_id: str | None,
        enabled: bool,
    ) -> None:
        if previous_id is not None:
            self._pending_cdp_invalidations.discard(previous_id)
        if enabled and next_id is not None:
            self._pending_cdp_invalidations.add(next_id)

    def _record_native_metadata(self, response: BrowserResponse) -> None:
        generation = response.raw.get("refGeneration")
        if isinstance(generation, int):
            self._ref_generation = generation
        target_id = response.raw.get("targetId")
        if isinstance(target_id, str):
            self._active_target_id = target_id
        if response.raw.get("scopeSwitched"):
            self._invalidate_cdp()

    def _record_successful_action(
        self,
        response: BrowserResponse,
        *,
        params: Mapping[str, Any] | None = None,
        force_cdp_invalidation: bool = False,
    ) -> None:
        action = response.action
        if response.raw.get("refGeneration") is None and (
            action in {"snapshot", "diff_snapshot", "diff_url"}
            or (action == "screenshot" and bool((params or {}).get("annotate")))
        ):
            self._ref_generation += 1
        browser_launched = response_browser_launched(response)
        if browser_launched is not None:
            self._launched = browser_launched
        elif action_sets_launched(action):
            self._launched = True
        elif action_clears_pending_confirmation(action) and action_closes_browser(action):
            self._launched = False
        if action_closes_browser(action):
            self._pending_cdp_invalidations.clear()
        if action_resets_cdp(action):
            self._reset_cdp()
        elif force_cdp_invalidation or action_invalidates_cdp(action, params):
            self._invalidate_cdp()

    def _cdp(self) -> CDPController:
        if self._cdp_controller is None:
            from agentbrowser.cdp import CDPController

            self._cdp_controller = CDPController(self)
        return self._cdp_controller

    def _invalidate_cdp(self) -> None:
        if self._cdp_controller is not None:
            self._cdp_controller.invalidate()

    def _reset_cdp(self) -> None:
        if self._cdp_controller is not None:
            self._cdp_controller.close()
            self._cdp_controller = None

    def _connect(self) -> Mapping[str, Any]:
        """Attach to the configured CDP target without navigating.

        This internal handshake is valid for browsers created through
        `Browser.attach(CDPTarget(...))`.

        Returns
        -------
        Mapping[str, object]
            Native attach response data.
        """
        if (
            self._launch_configuration.cdp_url is None
            and self._launch_configuration.cdp_port is None
        ):
            raise RuntimeError("CDP connection requires Browser.attach(CDPTarget(...))")
        return self._launch_native()

    def _launch_process(
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
        return self._launch_native(options=options)

    def _launch_native(
        self,
        *,
        options: LaunchOptions | None = None,
    ) -> Mapping[str, Any]:
        launch_params = self._launch_configuration.command_params(options=options)
        self._prepare_install_for_launch(launch_params)
        data = self._command("launch", **launch_params)
        self._launched = True
        return data

    def _prepare_install_for_action(self, action: str, params: dict[str, Any]) -> None:
        if not self._auto_install or self._install_prepared or self._launched:
            return
        if action == "launch":
            self._prepare_install_for_launch(params)
            return
        if action in _SKIP_AUTO_INSTALL_ACTIONS:
            return
        if not _uses_local_chrome(self._launch_configuration.command_params()):
            return
        ensure_installed()
        self._install_prepared = True

    def _prepare_install_for_launch(self, launch_params: dict[str, Any]) -> None:
        if not self._auto_install or self._install_prepared:
            return
        if not _uses_local_chrome(launch_params):
            return
        result = ensure_installed()
        launch_params["executablePath"] = str(result.executable_path)
        self._install_prepared = True

    def close(self) -> CloseResult:
        """Close the browser and return terminal restore-save state."""
        if self._closed:
            if self._close_error is not None:
                raise self._close_error
            result = self._close_result or CloseResult(closed=True)
            return result
        result = CloseResult(closed=True)
        if self._cdp_controller is not None:
            with suppress(Exception):
                self._cdp_controller.close()
            self._cdp_controller = None
        try:
            if self._session.started:
                response = self._session.execute(INTERNAL_SHUTDOWN_ACTION)
                checked = _checked_response("close", replace(response, action="close"))
                self._record_successful_action(checked)
                result = close_result_from_data(
                    _require_response_data_mapping(checked, action="close")
                )
        except BaseException as error:
            self._close_error = error
            raise
        finally:
            self._session.discard_pending_confirmations()
            self._launched = False
            self._closed = True
            self._close_result = result
        if result.save_error is not None:
            error = RestoreSaveError(result)
            self._close_error = error
            raise error
        return result

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Browser is closed")

    def activate(self) -> Self:
        """Bring the browser window to the foreground."""
        self._command("bringtofront", _decode=lambda _data: self)
        return self


def _uses_local_chrome(params: Mapping[str, Any]) -> bool:
    if _present(params.get("executablePath")):
        return False
    if _present(params.get("provider")):
        return False
    if _present(params.get("cdpUrl")) or _present(params.get("cdpPort")):
        return False
    if bool(params.get("autoConnect")):
        return False
    engine = params.get("engine")
    if not _present(engine):
        engine = os.environ.get("AGENT_BROWSER_ENGINE")
    if _present(engine) and str(engine).lower() != "chrome":
        return False
    if os.environ.get("AGENT_BROWSER_EXECUTABLE_PATH"):
        return False
    if os.environ.get("AGENT_BROWSER_CDP") or os.environ.get("AGENT_BROWSER_AUTO_CONNECT"):
        return False
    provider = os.environ.get("AGENT_BROWSER_PROVIDER")
    return provider is None or provider.strip().lower() in {"", "ios", "safari"}


def _present(value: Any) -> bool:
    return value is not None and value is not OMIT and value != ""
