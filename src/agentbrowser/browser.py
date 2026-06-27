from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Self, cast, overload
from weakref import proxy as weak_proxy

from agentbrowser._browser_common import (
    INTERNAL_SHUTDOWN_ACTION,
    ConfirmationTarget,
    action_clears_pending_confirmation,
    action_closes_browser,
    action_invalidates_cdp,
    action_sets_launched,
    confirmation_id,
    response_confirmation_id,
    response_data_mapping,
)
from agentbrowser.agent import Agent, AgentSnapshot
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
    NativeSession,
    _checked_response,
    _require_response_data_mapping,
    _try_unwrap_confirmed_response,
)

if TYPE_CHECKING:
    from agentbrowser.cdp import CDPController


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

    def start(self, options: DashboardOptions | None = None) -> Mapping[str, Any]:
        """Start dashboard observability and return the stream status."""
        self._browser._session.set_dashboard(True if options is None else options)
        return self._browser._command("stream_status")


@dataclass(frozen=True, slots=True)
class PendingAction:
    """Native action awaiting explicit confirmation or denial."""

    _browser: Browser
    confirmation_id: str
    action: str
    data: Mapping[str, Any]

    def confirm(self) -> Mapping[str, Any]:
        """Confirm this pending action."""
        return self._browser.confirm(self)

    def deny(self) -> Mapping[str, Any]:
        """Deny this pending action."""
        return self._browser.deny(self)


class Browser:
    """Synchronous controller for the native agent-browser engine.

    `Browser` owns one native browser session and exposes command namespaces
    such as `page`, `find`, `capture`, `tabs`, `network`, and `cdp`.
    Construction is lazy. Use `Browser.launch(LaunchOptions(...))` to create
    and start a browser, `Browser.attach(CDPAttach(...))` to attach to a
    running browser, or `Browser.from_session(...)` to name a restorable
    session before the first native command.
    """

    def __init__(
        self,
        *,
        session_options: BrowserSessionOptions | None = None,
        native_session: NativeSession | None = None,
    ) -> None:
        base_options = session_options or BrowserSessionOptions()
        launch_configuration = LaunchConfiguration.from_public_options(
            allowed_domains=base_options.allowed_domains
        )
        self._init(
            launch_configuration,
            session_options=base_options,
            native_session=native_session,
        )

    @classmethod
    def _from_configuration(
        cls,
        launch_configuration: LaunchConfiguration,
        *,
        session_options: BrowserSessionOptions | None = None,
        native_session: NativeSession | None = None,
    ) -> Browser:
        browser = cls.__new__(cls)
        browser._init(
            launch_configuration,
            session_options=session_options,
            native_session=native_session,
        )
        return browser

    def _init(
        self,
        launch_configuration: LaunchConfiguration,
        *,
        session_options: BrowserSessionOptions | None = None,
        native_session: NativeSession | None = None,
    ) -> None:
        session_options = session_options or BrowserSessionOptions()
        self._session = native_session or NativeSession(
            session=session_options.session_id,
            restore=session_options.restore,
            namespace=session_options.namespace,
            default_timeout_ms=session_options.default_timeout_ms,
            allowed_domains=session_options.allowed_domains,
            engine=launch_configuration.engine,
            action_policy=session_options.action_policy,
            confirm_actions=session_options.confirm_actions,
            no_auto_dialog=session_options.no_auto_dialog,
        )
        if native_session is not None and session_options.allowed_domains is not None:
            self._session.set_allowed_domains(session_options.allowed_domains)
        default_session_options = BrowserSessionOptions()
        if native_session is not None and session_options.namespace is not None:
            raise ValueError(
                "namespace must be set on NativeSession when native_session is supplied"
            )
        if native_session is not None and session_options.session_id is not None:
            raise ValueError(
                "session_id must be set on NativeSession when native_session is supplied"
            )
        if native_session is not None and session_options.restore is not None:
            raise ValueError("restore must be set on NativeSession when native_session is supplied")
        if (
            native_session is not None
            and session_options.default_timeout_ms != default_session_options.default_timeout_ms
        ):
            raise ValueError(
                "default_timeout_ms must be set on NativeSession when native_session is supplied"
            )
        if native_session is not None and session_options.action_policy is not None:
            raise ValueError(
                "action_policy must be set on NativeSession when native_session is supplied"
            )
        if native_session is not None and session_options.confirm_actions is not None:
            raise ValueError(
                "confirm_actions must be set on NativeSession when native_session is supplied"
            )
        if (
            native_session is not None
            and session_options.no_auto_dialog != default_session_options.no_auto_dialog
        ):
            raise ValueError(
                "no_auto_dialog must be set on NativeSession when native_session is supplied"
            )
        self._launch_configuration = launch_configuration
        self._launched = False
        self._cdp_controller: CDPController | None = None

        command_target = cast(CommandTarget, weak_proxy(self))
        self.active_frame = ActiveFrame(command_target)
        self.agent = Agent(self)
        self.capture = Capture(command_target)
        self.cdp = CDP(self)
        self.clipboard = Clipboard(command_target)
        self.cookies = Cookies(command_target)
        self.dialogs = Dialogs(command_target)
        self.diagnostics = Diagnostics(command_target)
        self.dashboard = Dashboard(self)
        self.diff = Diff(command_target)
        self.downloads = Downloads(command_target)
        self.find = Find(self)
        self.keyboard = Keyboard(command_target)
        self.mouse = Mouse(command_target)
        self.native = Native(self)
        self.network = Network(command_target)
        self.page = Page(self)
        self.restore = Restore(command_target)
        self.runtime = Runtime(command_target)
        self.scripts = Scripts(self)
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

    @classmethod
    def launch(
        cls,
        options: LaunchOptions | None = None,
        *,
        session_options: BrowserSessionOptions | None = None,
        native_session: NativeSession | None = None,
    ) -> Browser:
        """Create a browser and start the native browser process."""
        session_options = session_options or BrowserSessionOptions()
        browser = cls._from_configuration(
            LaunchConfiguration.from_public_options(
                options,
                allowed_domains=session_options.allowed_domains,
            ),
            session_options=session_options,
            native_session=native_session,
        )
        browser.launch_process()
        return browser

    @classmethod
    def attach(
        cls,
        target: CDPAttach,
        *,
        launch_options: LaunchOptions | None = None,
        session_options: BrowserSessionOptions | None = None,
        native_session: NativeSession | None = None,
    ) -> Browser:
        """Create a browser and attach to a running CDP target."""
        session_options = session_options or BrowserSessionOptions()
        browser = cls._from_configuration(
            LaunchConfiguration.from_public_options(
                launch_options,
                attach=target,
                allowed_domains=session_options.allowed_domains,
            ),
            session_options=session_options,
            native_session=native_session,
        )
        browser.connect()
        return browser

    @classmethod
    def from_session(
        cls,
        session_id: str,
        *,
        restore: RestoreOptions | None = None,
        launch_options: LaunchOptions | None = None,
        session_options: BrowserSessionOptions | None = None,
        native_session: NativeSession | None = None,
    ) -> Browser:
        """Create a lazy browser controller for a named native session."""
        base_options = session_options or BrowserSessionOptions()
        if base_options.session_id not in {None, session_id}:
            raise ValueError("session_options.session_id must match session_id")
        if restore is not None and base_options.restore is not None:
            raise ValueError("pass restore or session_options.restore, not both")
        resolved_options = replace(
            base_options,
            session_id=session_id,
            restore=restore or base_options.restore,
        )
        return cls._from_configuration(
            LaunchConfiguration.from_public_options(
                launch_options,
                allowed_domains=resolved_options.allowed_domains,
            ),
            session_options=resolved_options,
            native_session=native_session,
        )

    def observe(
        self,
        *,
        selector: str | None = None,
        interactive: bool = True,
        compact: bool = False,
        max_depth: int | None = None,
        urls: bool = False,
    ) -> AgentSnapshot:
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
        AgentSnapshot
            Snapshot wrapper whose refs can be acted on directly.
        """
        return self.agent.observe(
            selector=selector,
            interactive=interactive,
            compact=compact,
            max_depth=max_depth,
            urls=urls,
        )

    def _command(self, action: str, **params: Any) -> JSONMapping:
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
        ActionConfirmationRequired
            If the native policy requires confirmation before execution.
        BrowserError
            If the native command fails or returns non-object response data.
        """
        data = self._native_data(action, expect="object", **params)
        return cast(JSONMapping, data)

    def _native_data(
        self,
        action: str,
        *,
        expect: str = "object",
        **params: Any,
    ) -> JSONMapping | JSONValue:
        if expect not in {"object", "any"}:
            raise ValueError('expect must be "object" or "any"')
        try:
            response = _checked_response(action, self._session.execute(action, **params))
        except ActionConfirmationRequired as err:
            if err.confirmation_id is not None:
                err.pending_action = self.pending_action(err)
            raise
        self._record_successful_action(response.action)
        if expect == "any":
            return response.data
        return _require_response_data_mapping(response)

    def _native_execute(self, action: str, **params: Any) -> BrowserResponse:
        response = self._session.execute(action, **params)
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
    ) -> PendingAction:
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
        return PendingAction(
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

    def _cdp(self) -> CDPController:
        if self._cdp_controller is None:
            from agentbrowser.cdp import CDPController

            self._cdp_controller = CDPController(self)
        return self._cdp_controller

    def _invalidate_cdp(self) -> None:
        if self._cdp_controller is not None:
            self._cdp_controller.invalidate()

    def connect(self) -> Mapping[str, Any]:
        """Attach to the configured CDP target without navigating.

        `connect()` is only valid for browsers created through
        `Browser.attach(CDPAttach(...))`.

        Returns
        -------
        Mapping[str, object]
            Native attach response data.
        """
        if (
            self._launch_configuration.cdp_url is None
            and self._launch_configuration.cdp_port is None
        ):
            raise RuntimeError("connect requires Browser.attach(CDPAttach(...))")
        return self._launch_native()

    def launch_process(
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
            raise RuntimeError("launch_process cannot use CDPAttach; call connect()")
        return self._launch_native(options=options)

    def _launch_native(
        self,
        *,
        options: LaunchOptions | None = None,
    ) -> Mapping[str, Any]:
        launch_params = self._launch_configuration.command_params(options=options)
        data = self._command("launch", **launch_params)
        self._launched = True
        return data

    def close(self, *, timeout: float = 5.0) -> None:
        """Close the native browser session and any active CDP connection."""
        del timeout
        if self._cdp_controller is not None:
            with suppress(Exception):
                self._cdp_controller.close()
            self._cdp_controller = None
        response = self._session.execute(INTERNAL_SHUTDOWN_ACTION)
        _checked_response("close", replace(response, action="close"))
        self._record_successful_action("close")

    def confirm(
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
            if isinstance(confirmation, PendingAction)
            else confirmation_id(confirmation)
        )
        if pending_id is None:
            raise ValueError("confirm requires an ActionConfirmationRequired or confirmation id")
        return self._command("confirm", confirmation_id=pending_id)

    def deny(
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
            if isinstance(confirmation, PendingAction)
            else confirmation_id(confirmation)
        )
        if pending_id is None:
            raise ValueError("deny requires an ActionConfirmationRequired or confirmation id")
        data = self._command("deny", confirmation_id=pending_id)
        return data

    def snapshot(
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
        data = self._command(
            "snapshot",
            selector=optional(selector),
            interactive=interactive,
            compact=compact,
            maxDepth=optional(max_depth),
            urls=urls,
        )
        return snapshot_from_data(data)

    def diff_snapshot(
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
        return self.diff.snapshot(
            baseline=baseline_value,
            selector=selector,
            compact=compact,
            max_depth=max_depth,
        )

    def set_viewport(
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
        return self._command(
            "viewport",
            **viewport_params(
                width,
                height,
                device_scale_factor=device_scale_factor,
                mobile=mobile,
            ),
        )

    def set_device(self, name: str) -> Mapping[str, Any]:
        """Set a named device preset."""
        return self._command("device", name=name)

    def set_headers(self, headers: Mapping[str, str]) -> Mapping[str, Any]:
        """Set extra HTTP headers for subsequent page requests."""
        return self._command("headers", headers=dict(headers))

    def set_offline(self, enabled: bool = True) -> Mapping[str, Any]:
        """Enable or disable offline network emulation."""
        return self._command("offline", offline=enabled)

    def set_user_agent(self, user_agent: str) -> Mapping[str, Any]:
        """Set the browser user-agent string."""
        return self._command("useragent", userAgent=user_agent)

    def set_media(
        self,
        *,
        media: str | None = None,
        color_scheme: str | None = None,
        reduced_motion: str | None = None,
        features: Mapping[str, str] | None = None,
    ) -> Mapping[str, Any]:
        """Set emulated CSS media features."""
        return self._command(
            "set_media",
            **media_params(
                media=media,
                color_scheme=color_scheme,
                reduced_motion=reduced_motion,
                features=features,
            ),
        )

    def set_timezone(self, timezone_id: str) -> Mapping[str, Any]:
        """Set the emulated timezone id, for example `Europe/Vienna`."""
        return self._command("timezone", timezoneId=timezone_id)

    def set_locale(self, locale: str) -> Mapping[str, Any]:
        """Set the emulated browser locale, for example `en-US`."""
        return self._command("locale", locale=locale)

    def set_geolocation(
        self,
        latitude: float,
        longitude: float,
        *,
        accuracy: float | None = None,
    ) -> Mapping[str, Any]:
        """Set emulated geolocation coordinates."""
        return self._command(
            "geolocation",
            **geolocation_params(latitude, longitude, accuracy=accuracy),
        )

    def set_permissions(
        self, permissions: Sequence[str], *, origin: str | None = None
    ) -> Mapping[str, Any]:
        """Grant browser permissions, optionally scoped to an origin."""
        return self._command("permissions", **permissions_params(permissions, origin=origin))

    def bring_to_front(self) -> Mapping[str, Any]:
        """Bring the browser window to the foreground."""
        return self._command("bringtofront")
