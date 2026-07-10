from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generic, Literal, Self, TypeVar, cast, overload
from weakref import proxy as weak_proxy

from agentbrowser._browser_common import (
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
    snapshot_diff_from_data,
)
from agentbrowser.agent import Snapshot
from agentbrowser.command_params import (
    geolocation_params,
    media_params,
    optional,
    permissions_params,
    viewport_params,
)
from agentbrowser.domains import (
    CDP,
    ActiveFrame,
    Capture,
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
from agentbrowser.query import Queries
from agentbrowser.session import (
    NativeSession,
    _checked_response,
    _require_response_data_mapping,
    _try_unwrap_confirmed_response,
)

if TYPE_CHECKING:
    from agentbrowser.cdp import CDPController

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
        result: Any = self._browser._native_data(
            "confirm",
            expect=self._expect,
            confirmation_id=self.confirmation_id,
        )
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

    Use `launch()` for a local process, `attach()` for an existing CDP target,
    and `observe()` for browser-bound snapshots and refs.
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

        command_target = cast(CommandTarget, weak_proxy(self))
        browser_proxy = cast(Browser, weak_proxy(self))
        self.active_frame = ActiveFrame(command_target)
        self.capture = Capture(command_target)
        self.cdp = CDP(browser_proxy)
        self.clipboard = Clipboard(command_target)
        self.cookies = Cookies(command_target)
        self.diagnostics = Diagnostics(command_target)
        self.dashboard = Dashboard(browser_proxy)
        self.dialogs = Dialogs(command_target)
        self.diff = Diff(command_target)
        self.downloads = Downloads(command_target)
        self.emulation = Emulation(browser_proxy)
        self.find = Queries(browser_proxy)
        self.keyboard = Keyboard(command_target)
        self.mouse = Mouse(command_target)
        self.native = Native(browser_proxy)
        self.network = Network(command_target)
        self.page = Page(browser_proxy)
        self.scripts = Scripts(command_target)
        self.session = Session(command_target)
        self.state = State(command_target)
        self.storage = Storage(command_target)
        self.tabs = Tabs(command_target)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, _exc: object, _tb: object) -> None:
        if exc_type is None:
            self.close()
            return
        with suppress(BaseException):
            self.close()

    @property
    def is_launched(self) -> bool:
        """Whether the native browser has been launched in this session."""
        return self._launched

    @property
    def closed(self) -> bool:
        """Whether this browser has been closed."""
        return self._closed

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

    def observe(
        self,
        spec: SnapshotSpec | None = None,
    ) -> Snapshot:
        """Capture an accessibility snapshot bound to this browser."""
        try:
            data = self._snapshot_data(spec or SnapshotSpec())
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map(lambda result: Snapshot(self, result))
            raise
        return Snapshot(self, data)

    def open(self, url: str, *, wait_until: LoadState = "load") -> Self:
        """Navigate the active tab and return this browser."""
        try:
            self.page.open(url, wait_until=wait_until)
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map(lambda _value: self)
            raise
        return self

    def title(self) -> str:
        """Return the active page title."""
        return self.page.title()

    def url(self) -> str:
        """Return the active page URL."""
        return self.page.url()

    def content(self) -> str:
        """Return the active page HTML."""
        return self.page.content()

    def evaluate(self, script: str) -> Any:
        """Evaluate JavaScript in the active page."""
        return self.page.evaluate(script)

    def read(
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
        return self.page.read(
            url,
            mode=mode,
            filter=filter,
            timeout_ms=timeout_ms,
            headers=headers,
            allowed_domains=allowed_domains,
        )

    def wait_for_text(self, text: str, *, timeout_ms: int | None = None) -> None:
        """Wait until text appears in the active page."""
        self.page.wait_for_text(text, timeout_ms=timeout_ms)

    def wait_for_url(self, url: str, *, timeout_ms: int | None = None) -> None:
        """Wait until the active URL matches a pattern."""
        self.page.wait_for_url(url, timeout_ms=timeout_ms)

    def wait_for_load(self, state: LoadState = "load") -> None:
        """Wait for a page load state."""
        self.page.wait_for_load_state(state)

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
        try:
            response = _checked_response(action, self._session.execute(action, **params))
        except ConfirmationRequired as err:
            if err.confirmation_id is not None:
                err.pending = self._pending_action(
                    err,
                    expect=cast(Literal["object", "any"], expect),
                )
            raise
        self._record_successful_action(response)
        if expect == "any":
            return response.data
        return _require_response_data_mapping(response)

    def _native_execute(self, action: str, **params: Any) -> BrowserResponse:
        self._ensure_open()
        self._prepare_install_for_action(action, params)
        response = self._session.execute(action, **params)
        confirmation_consumed = action == "confirm" and response.success
        if confirmation_consumed:
            response = _try_unwrap_confirmed_response(response)
        data = response_data_mapping(response)
        if data is not None and bool(data.get("confirmation_required")):
            return response
        if confirmation_consumed:
            if response.success:
                self._record_successful_action(response)
            return response
        if response.success:
            self._record_successful_action(response)
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

    def _record_successful_action(self, response: BrowserResponse) -> None:
        action = response.action
        browser_launched = response_browser_launched(response)
        if browser_launched is not None:
            self._launched = browser_launched
        elif action_sets_launched(action):
            self._launched = True
        elif action_clears_pending_confirmation(action) and action_closes_browser(action):
            self._launched = False
        if action_resets_cdp(action):
            self._reset_cdp()
        elif action_invalidates_cdp(action):
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

    def _snapshot_data(
        self,
        spec: SnapshotSpec | None = None,
    ) -> SnapshotData:
        spec = spec or SnapshotSpec(interactive=False)
        return self._command(
            "snapshot",
            _decode=lambda data: snapshot_from_data(data, spec=spec),
            selector=optional(spec.selector),
            interactive=spec.interactive,
            compact=spec.compact,
            maxDepth=optional(spec.max_depth),
            urls=spec.urls,
        )

    def _diff_snapshot(
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
        return self._command(
            "diff_snapshot",
            _decode=snapshot_diff_from_data,
            baseline=optional(
                path_value(baseline_value) if isinstance(baseline_value, Path) else baseline_value
            ),
            selector=optional(selector),
            compact=compact,
            maxDepth=optional(max_depth),
        )

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
