from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from weakref import proxy as weak_proxy

from typing_extensions import Self

from pyagentbrowser._browser_common import (
    action_clears_pending_confirmation,
    action_closes_browser,
    action_invalidates_cdp,
    action_sets_launched,
    confirmation_id,
    response_confirmation_id,
    response_data_mapping,
)
from pyagentbrowser.agent import Agent, AgentSnapshot
from pyagentbrowser.command_params import (
    geolocation_params,
    media_params,
    optional,
    permissions_params,
    viewport_params,
)
from pyagentbrowser.domains import (
    CDP,
    Capture,
    Clipboard,
    CommandTarget,
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
from pyagentbrowser.launch import LaunchConfiguration
from pyagentbrowser.models import (
    ActionConfirmationRequired,
    BrowserError,
    BrowserResponse,
    ColorScheme,
    DashboardOptions,
    JSONMapping,
    JSONValue,
    ProxyConfig,
    Snapshot,
    SnapshotDiff,
    snapshot_from_data,
)
from pyagentbrowser.session import (
    DEFAULT_TIMEOUT_MS,
    NativeSession,
    _checked_response,
    _require_response_data_mapping,
    _try_unwrap_confirmed_response,
)

if TYPE_CHECKING:
    from pyagentbrowser.cdp import CDPController


class Browser:
    """Synchronous controller for the native agent-browser engine.

    `Browser` owns one native browser session and exposes command namespaces
    such as `page`, `find`, `capture`, `tabs`, `network`, and `cdp`.
    Construction is lazy. The native browser launches on `launch()`,
    `connect()`, or the first helper that needs a page.

    Parameters
    ----------
    headless
        Whether browser windows should be hidden when the browser launches.
    executable_path
        Path to a Chrome-compatible browser executable.
    engine
        Native engine name passed through to agent-browser.
    session, session_name
        Native session identifiers used for browser state isolation.
    default_timeout_ms
        Default native command timeout in milliseconds. Defaults to 15,000.
    allowed_domains
        Comma-separated host allowlist such as `example.com`,
        `*.example.com`, `localhost`, or `::1`. The SDK checks raw URL targets,
        host-qualified URL patterns, cookie targets, and permission origins
        before native execution. Storage-state loads are filtered before native
        import. Storage-state saves and cookie reads are filtered before they
        return unless the unsafe export option is used.
    action_policy
        Path to a native action policy file.
    confirm_actions
        Native action names that require confirmation.
    profile
        Browser profile directory.
    storage_state
        Storage-state file loaded during launch. When `allowed_domains` is set,
        disallowed cookies and origins are filtered before native import.
    extensions
        Browser extension paths loaded at launch.
    proxy
        Browser proxy configuration.
    provider
        Native provider name.
    cdp_url
        Browser-level CDP WebSocket URL to attach to.
    cdp_port
        Local CDP port to attach to.
    auto_connect
        Attach immediately when native launch options request auto-connect.
    color_scheme
        Emulated browser color scheme.
    hide_scrollbars
        Whether headless Chromium launches with native scrollbars hidden.
        `None` leaves the native default and `AGENT_BROWSER_HIDE_SCROLLBARS`
        in control.
    args
        Extra browser process arguments.
    no_auto_dialog
        Disable native automatic dialog handling.
    dashboard
        Enable SDK-owned dashboard observability. Pass `DashboardOptions` to
        set dashboard sidecar options.
    native_session
        Existing `NativeSession` to use instead of constructing one.
    """

    def __init__(
        self,
        *,
        headless: bool = True,
        executable_path: str | Path | None = None,
        engine: str | None = None,
        session: str | None = None,
        session_name: str | None = None,
        default_timeout_ms: int | None = DEFAULT_TIMEOUT_MS,
        allowed_domains: str | None = None,
        action_policy: str | Path | None = None,
        confirm_actions: Sequence[str] | None = None,
        profile: str | Path | None = None,
        storage_state: str | Path | None = None,
        extensions: Sequence[str | Path] = (),
        proxy: str | ProxyConfig | Mapping[str, Any] | None = None,
        provider: str | None = None,
        cdp_url: str | None = None,
        cdp_port: int | None = None,
        auto_connect: bool = False,
        color_scheme: ColorScheme | None = None,
        hide_scrollbars: bool | None = None,
        args: Sequence[str] = (),
        no_auto_dialog: bool = False,
        dashboard: bool | DashboardOptions | None = False,
        native_session: NativeSession | None = None,
    ) -> None:
        self._session = native_session or NativeSession(
            session=session,
            session_name=session_name,
            default_timeout_ms=default_timeout_ms,
            allowed_domains=allowed_domains,
            engine=engine,
            action_policy=action_policy,
            confirm_actions=confirm_actions,
            no_auto_dialog=no_auto_dialog,
            dashboard=dashboard,
        )
        if native_session is not None and allowed_domains is not None:
            self._session.set_allowed_domains(allowed_domains)
        self._launch_configuration = LaunchConfiguration.from_options(
            headless=headless,
            executable_path=executable_path,
            engine=engine,
            allowed_domains=allowed_domains,
            profile=profile,
            storage_state=storage_state,
            extensions=extensions,
            proxy=proxy,
            provider=provider,
            cdp_url=cdp_url,
            cdp_port=cdp_port,
            auto_connect=auto_connect,
            color_scheme=color_scheme,
            hide_scrollbars=hide_scrollbars,
            args=args,
        )
        self._launched = False
        self._pending_confirmation_id: str | None = None
        self._cdp_controller: CDPController | None = None

        command_target = cast(CommandTarget, weak_proxy(self))
        self.agent = Agent(self)
        self.capture = Capture(command_target)
        self.cdp = CDP(self)
        self.clipboard = Clipboard(command_target)
        self.cookies = Cookies(command_target)
        self.dialogs = Dialogs(command_target)
        self.diagnostics = Diagnostics(command_target)
        self.diff = Diff(command_target)
        self.downloads = Downloads(command_target)
        self.find = Find(self)
        self.frames = Frames(command_target)
        self.keyboard = Keyboard(command_target)
        self.mouse = Mouse(command_target)
        self.network = Network(command_target)
        self.page = Page(self)
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

    def command(self, action: str, **params: Any) -> JSONMapping:
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
        try:
            response = _checked_response(action, self._session.execute(action, **params))
        except ActionConfirmationRequired as err:
            self._pending_confirmation_id = err.confirmation_id
            raise
        data = _require_response_data_mapping(response)
        self._record_successful_action(response.action)
        return data

    def execute_raw(self, action: str, **params: Any) -> JSONValue:
        """Run a native command and return response data without shape checks.

        Low-level native commands may return scalar, array, or null `data`.

        Parameters
        ----------
        action
            Native agent-browser command action.
        **params
            JSON-compatible command parameters.

        Returns
        -------
        object
            Raw `data` value returned by the native engine.
        """
        try:
            response = _checked_response(action, self._session.execute(action, **params))
        except ActionConfirmationRequired as err:
            self._pending_confirmation_id = err.confirmation_id
            raise
        self._record_successful_action(response.action)
        return response.data

    def try_command(self, action: str, **params: Any) -> BrowserResponse:
        """Run a native command without raising for unsuccessful responses.

        Parameters
        ----------
        action
            Native agent-browser command action.
        **params
            JSON-compatible command parameters.

        Returns
        -------
        BrowserResponse
            Full native response envelope.
        """
        response = self._session.execute(action, **params)
        confirmation_consumed = action == "confirm" and response.success
        if confirmation_consumed:
            response = _try_unwrap_confirmed_response(response)
        data = response_data_mapping(response)
        if data is not None and bool(data.get("confirmation_required")):
            self._pending_confirmation_id = response_confirmation_id(response)
            return response
        if confirmation_consumed:
            if response.success:
                self._record_successful_action(response.action)
            self._pending_confirmation_id = None
            return response
        if response.success:
            self._record_successful_action(response.action)
        return response

    def _record_successful_action(self, action: str) -> None:
        if action_sets_launched(action):
            self._launched = True
        elif action_clears_pending_confirmation(action):
            if action_closes_browser(action):
                self._launched = False
            self._pending_confirmation_id = None
        if action_invalidates_cdp(action):
            self._invalidate_cdp()

    def _cdp(self) -> CDPController:
        if self._cdp_controller is None:
            from pyagentbrowser.cdp import CDPController

            self._cdp_controller = CDPController(self)
        return self._cdp_controller

    def _invalidate_cdp(self) -> None:
        if self._cdp_controller is not None:
            self._cdp_controller.invalidate()

    def connect(self) -> Mapping[str, Any]:
        """Establish the browser connection without navigating.

        Calling `connect()` gives configured CDP attachment options such as
        `cdp_port`, `cdp_url`, or `auto_connect` an explicit launch or attach
        step.

        Returns
        -------
        Mapping[str, object]
            Native launch response data.
        """
        return self.launch()

    def launch(
        self,
        *,
        headless: bool | None = None,
        executable_path: str | Path | None = None,
        engine: str | None = None,
        args: Sequence[str] | None = None,
        allow_file_access: bool = False,
        ignore_https_errors: bool = False,
        user_agent: str | None = None,
        download_path: str | Path | None = None,
        profile: str | Path | None = None,
        storage_state: str | Path | None = None,
        extensions: Sequence[str | Path] | None = None,
        proxy: str | ProxyConfig | Mapping[str, Any] | None = None,
        provider: str | None = None,
        cdp_url: str | None = None,
        cdp_port: int | None = None,
        auto_connect: bool | None = None,
        color_scheme: ColorScheme | None = None,
        hide_scrollbars: bool | None = None,
    ) -> Mapping[str, Any]:
        """Launch the browser, overriding constructor launch options if needed.

        Parameters
        ----------
        headless, executable_path, engine, args
            Core browser process options.
        allow_file_access, ignore_https_errors
            Browser security and certificate options.
        user_agent, download_path, profile, storage_state
            Browser environment options.
        extensions, proxy, provider
            Optional launch integrations.
        cdp_url, cdp_port, auto_connect
            Chrome DevTools Protocol connection options.
        color_scheme
            Emulated browser color scheme.
        hide_scrollbars
            Whether headless Chromium screenshots hide native scrollbars.
            `None` uses the constructor option, then the native default.

        Returns
        -------
        Mapping[str, object]
            Native launch response data.
        """
        launch_params = self._launch_configuration.command_params(
            headless=headless,
            executable_path=executable_path,
            engine=engine,
            args=args,
            allow_file_access=allow_file_access,
            ignore_https_errors=ignore_https_errors,
            user_agent=user_agent,
            download_path=download_path,
            profile=profile,
            storage_state=storage_state,
            extensions=extensions,
            proxy=proxy,
            provider=provider,
            cdp_url=cdp_url,
            cdp_port=cdp_port,
            auto_connect=auto_connect,
            color_scheme=color_scheme,
            hide_scrollbars=hide_scrollbars,
        )
        data = self.command("launch", **launch_params)
        self._launched = True
        return data

    def close(self) -> None:
        """Close the native browser session and any active CDP connection."""
        if self._cdp_controller is not None:
            with suppress(Exception):
                self._cdp_controller.close()
            self._cdp_controller = None
        self.command("close")
        self._launched = False

    def confirm(
        self, confirmation: ActionConfirmationRequired | str | None = None
    ) -> Mapping[str, Any]:
        """Confirm a pending native action.

        Parameters
        ----------
        confirmation
            Confirmation exception, confirmation id, or `None` to use the last
            pending confirmation tracked by this browser.

        Returns
        -------
        Mapping[str, object]
            Native response data for the confirmed action.
        """
        pending_id = confirmation_id(confirmation) or self._pending_confirmation_id
        if pending_id is None:
            raise ValueError("confirm requires an ActionConfirmationRequired or confirmation id")
        try:
            data = self.command("confirm", confirmation_id=pending_id)
        except BrowserError as err:
            if err.action != "confirm":
                self._pending_confirmation_id = None
            raise
        self._pending_confirmation_id = None
        return data

    def deny(
        self, confirmation: ActionConfirmationRequired | str | None = None
    ) -> Mapping[str, Any]:
        """Deny a pending native action.

        Parameters
        ----------
        confirmation
            Confirmation exception, confirmation id, or `None` to use the last
            pending confirmation tracked by this browser.

        Returns
        -------
        Mapping[str, object]
            Native response data for the denial command.
        """
        pending_id = confirmation_id(confirmation) or self._pending_confirmation_id
        if pending_id is None:
            raise ValueError("deny requires an ActionConfirmationRequired or confirmation id")
        data = self.command("deny", confirmation_id=pending_id)
        self._pending_confirmation_id = None
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
        data = self.command(
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
        return self.command(
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
        return self.command("device", name=name)

    def set_headers(self, headers: Mapping[str, str]) -> Mapping[str, Any]:
        """Set extra HTTP headers for subsequent page requests."""
        return self.command("headers", headers=dict(headers))

    def set_offline(self, enabled: bool = True) -> Mapping[str, Any]:
        """Enable or disable offline network emulation."""
        return self.command("offline", offline=enabled)

    def set_user_agent(self, user_agent: str) -> Mapping[str, Any]:
        """Set the browser user-agent string."""
        return self.command("useragent", userAgent=user_agent)

    def set_media(
        self,
        *,
        media: str | None = None,
        color_scheme: str | None = None,
        reduced_motion: str | None = None,
        features: Mapping[str, str] | None = None,
    ) -> Mapping[str, Any]:
        """Set emulated CSS media features."""
        return self.command(
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
        return self.command("timezone", timezoneId=timezone_id)

    def set_locale(self, locale: str) -> Mapping[str, Any]:
        """Set the emulated browser locale, for example `en-US`."""
        return self.command("locale", locale=locale)

    def set_geolocation(
        self,
        latitude: float,
        longitude: float,
        *,
        accuracy: float | None = None,
    ) -> Mapping[str, Any]:
        """Set emulated geolocation coordinates."""
        return self.command(
            "geolocation",
            **geolocation_params(latitude, longitude, accuracy=accuracy),
        )

    def set_permissions(
        self, permissions: Sequence[str], *, origin: str | None = None
    ) -> Mapping[str, Any]:
        """Grant browser permissions, optionally scoped to an origin."""
        return self.command("permissions", **permissions_params(permissions, origin=origin))

    def bring_to_front(self) -> Mapping[str, Any]:
        """Bring the browser window to the foreground."""
        return self.command("bringtofront")
