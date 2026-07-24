from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from time import sleep as sync_sleep
from typing import Any, Protocol, TypeVar, cast, overload

from agentbrowser._browser_common import (
    exclusive_source,
    normalize_url,
    snapshot_diff_from_data,
    validate_screenshot_wait_ms,
)
from agentbrowser.command_params import (
    accessibility_audit_params,
    cookies_clear_params,
    cookies_get_params,
    cookies_set_params,
    har_start_params,
    keyboard_params,
    mouse_params,
    optional,
    pdf_params,
    read_params,
    requests_params,
    route_params,
    screenshot_params,
    state_path_params,
    storage_clear_params,
    storage_get_params,
    storage_set_params,
    wait_params,
    wheel_params,
)
from agentbrowser.models import (
    AccessibilityAudit,
    ConfirmationRequired,
    ConsoleMessage,
    Cookie,
    HarContentMode,
    JSONMapping,
    LoadState,
    MouseButton,
    MouseEventType,
    NativeParseError,
    NetworkRequest,
    ReadMode,
    ReadResult,
    RequestDetail,
    RouteResponse,
    SameSite,
    Screenshot,
    SessionStatus,
    SnapshotDiff,
    StorageArea,
    TabCloseResult,
    TabInfo,
    TabSwitchResult,
    WaitSelectorState,
    accessibility_audit_from_data,
    console_messages_from_data,
    cookies_from_data,
    network_requests_from_data,
    path_value,
    read_result_from_data,
    request_detail_from_data,
    screenshot_from_data,
    session_status_from_data,
    tab_close_result_from_data,
    tab_from_data,
    tab_switch_from_data,
    tabs_from_data,
)

DEFAULT_SCREENSHOT_WAIT_MS = 100
T = TypeVar("T")


def _required_string(data: Mapping[str, Any], field: str, *, action: str) -> str:
    value = data.get(field)
    if not isinstance(value, str):
        raise NativeParseError(f"{action} field '{field}' must be a string")
    return value


def _required_path(data: Mapping[str, Any], *, action: str) -> Path:
    return Path(_required_string(data, "path", action=action))


def _none(_data: Mapping[str, Any]) -> None:
    return None


class CommandTarget(Protocol):
    """Protocol for objects that can execute native commands."""

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


@dataclass(frozen=True, slots=True)
class Page:
    """Page navigation, document, and wait helpers.

    Parameters
    ----------
    browser
        Browser-like object that implements `_command()`.
    """

    browser: Any

    def open(self, url: str, *, wait_until: LoadState = "load") -> None:
        """Navigate the current page to a URL.

        Example:
            ```python
            browser.open("https://example.com")
            print(browser.title())
            ```

        Parameters
        ----------
        url
            Absolute URL or host-like value. Host-like values are normalized to
            `https://...`.
        wait_until
            Load state the native engine should wait for.

        """
        if not self.browser.is_launched:
            try:
                self.browser._launch_process()
            except ConfirmationRequired as error:
                if error.pending is not None:
                    error.pending = error.pending.map(
                        lambda _value: self.open(url, wait_until=wait_until)
                    )
                raise
        self.browser._command(
            "navigate",
            _decode=_none,
            url=normalize_url(url),
            waitUntil=wait_until,
        )

    def title(self) -> str:
        """Return the current page title."""
        return self.browser._command(
            "title",
            _decode=lambda data: _required_string(data, "title", action="title"),
        )

    def url(self) -> str:
        """Return the current page URL."""
        return self.browser._command(
            "url",
            _decode=lambda data: _required_string(data, "url", action="url"),
        )

    def content(self) -> str:
        """Return the current page HTML."""
        return self.browser._command(
            "content",
            _decode=lambda data: _required_string(data, "html", action="content"),
        )

    def set_content(self, html: str) -> None:
        """Replace the current page document with HTML."""
        self.browser._command("setcontent", _decode=_none, html=html)

    def evaluate(self, script: str) -> Any:
        """Evaluate JavaScript in the current page context."""
        return self.browser._command(
            "evaluate",
            _decode=lambda data: data.get("result"),
            script=script,
        )

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
        """Return agent-readable content for a URL or the active page.

        Example:
            ```python
            result = browser.read(
                "https://example.com",
                mode=ReadMode.markdown(require=True),
            )
            print(result.content)
            ```
        """
        if url is None and not self.browser.is_launched:
            try:
                self.browser._launch_process()
            except ConfirmationRequired as error:
                if error.pending is not None:
                    error.pending = error.pending.map(
                        lambda _value: self.read(
                            url,
                            mode=mode,
                            filter=filter,
                            timeout_ms=timeout_ms,
                            headers=headers,
                            allowed_domains=allowed_domains,
                        )
                    )
                raise
        normalized_url = normalize_url(url) if url is not None else None
        return self.browser._command(
            "read",
            _decode=read_result_from_data,
            **read_params(
                normalized_url,
                mode=mode,
                filter=filter,
                timeout_ms=timeout_ms,
                headers=headers,
                allowed_domains=allowed_domains,
            ),
        )

    def ready(self, *, timeout_ms: int | None = None, min_text_length: int = 1) -> None:
        """Wait until the page has a body with readable text.

        Use this when a page is ready for inspection before a strict load-state
        wait settles.
        """
        if min_text_length < 0:
            raise ValueError("min_text_length must be non-negative")
        self.wait_for_function(
            f"document.body && document.body.innerText.length >= {min_text_length}",
            timeout_ms=timeout_ms,
        )

    def back(self) -> None:
        """Navigate back in history."""
        self.browser._command("back", _decode=_none)

    def forward(self) -> None:
        """Navigate forward in history."""
        self.browser._command("forward", _decode=_none)

    def reload(self) -> None:
        """Reload the current page."""
        self.browser._command("reload", _decode=_none)

    def wait_for_text(self, text: str, *, timeout_ms: int | None = None) -> None:
        """Wait until text appears."""
        self.browser._command(
            "wait",
            _decode=_none,
            **wait_params(None, text=text, timeout_ms=timeout_ms),
        )

    def wait_for_selector(
        self,
        selector: str,
        *,
        state: WaitSelectorState = "visible",
        timeout_ms: int | None = None,
    ) -> None:
        """Wait for a selector to reach a state."""
        self.browser._command(
            "wait",
            _decode=_none,
            **wait_params(None, selector=selector, state=state, timeout_ms=timeout_ms),
        )

    def wait_for_url(self, pattern: str, *, timeout_ms: int | None = None) -> None:
        """Wait for the page URL to match a pattern."""
        self.browser._command(
            "wait",
            _decode=_none,
            **wait_params(None, url=pattern, timeout_ms=timeout_ms),
        )

    def wait_for_function(self, predicate: str, *, timeout_ms: int | None = None) -> None:
        """Wait for a JavaScript predicate to become truthy."""
        self.browser._command(
            "wait",
            _decode=_none,
            **wait_params(None, predicate=predicate, timeout_ms=timeout_ms),
        )

    def wait_for_load_state(self, state: LoadState = "load") -> None:
        """Wait for a page load state."""
        self.browser._command("wait", _decode=_none, **wait_params(None, load_state=state))


@dataclass(frozen=True, slots=True)
class Capture:
    """Screenshot and PDF capture helpers."""

    browser: CommandTarget

    def screenshot(
        self,
        path: str | Path | None = None,
        *,
        selector: str | None = None,
        full_page: bool = False,
        annotate: bool = False,
        output_dir: str | Path | None = None,
        format: str = "png",
        quality: int | None = None,
        wait_ms: int = DEFAULT_SCREENSHOT_WAIT_MS,
    ) -> Screenshot:
        """Capture a screenshot.

        Parameters
        ----------
        path
            Optional output path.
        selector
            Optional selector to capture instead of the full viewport or page.
        full_page
            Capture the full scrollable page.
        annotate
            Include native snapshot annotations when supported.
        output_dir
            Optional output directory used by the native engine.
        format
            Image format such as `png`, `jpeg`, or `webp`.
        quality
            Optional lossy image quality.
        wait_ms
            Milliseconds to wait before capture to allow recent paint to settle.

        Returns
        -------
        Screenshot
            Parsed screenshot metadata and file path.
        """
        _wait_before_screenshot(wait_ms)
        return self.browser._command(
            "screenshot",
            _decode=lambda data: screenshot_from_data(data, format=format),
            **screenshot_params(
                path=path,
                selector=selector,
                full_page=full_page,
                annotate=annotate,
                output_dir=output_dir,
                format=format,
                quality=quality,
            ),
        )

    def pdf(
        self,
        path: str | Path | None = None,
        *,
        print_background: bool = True,
        landscape: bool = False,
        prefer_css_page_size: bool = False,
    ) -> Path:
        """Print the current page to PDF."""
        return self.browser._command(
            "pdf",
            _decode=lambda data: _required_path(data, action="pdf"),
            **pdf_params(
                path=path,
                print_background=print_background,
                landscape=landscape,
                prefer_css_page_size=prefer_css_page_size,
            ),
        )


@dataclass(frozen=True, slots=True)
class Scripts:
    """JavaScript and stylesheet injection helpers."""

    browser: Any

    def add_init(
        self,
        script: str | None = None,
        *,
        path: str | Path | None = None,
    ) -> str:
        """Add a script that runs before future page scripts."""
        source = exclusive_source("scripts.add_init", inline=script, path=path)
        if not self.browser.is_launched:
            try:
                self.browser._launch_process()
            except ConfirmationRequired as error:
                if error.pending is not None:
                    error.pending = error.pending.map(lambda _value: self._register_init(source))
                raise
        return self._register_init(source)

    def _register_init(self, source: str) -> str:
        return self.browser._command(
            "addinitscript",
            _decode=lambda data: _required_string(data, "identifier", action="addinitscript"),
            script=source,
        )

    def remove_init(self, identifier: str) -> None:
        """Remove a previously registered init script."""
        self.browser._command("removeinitscript", _decode=_none, identifier=identifier)

    def add(
        self,
        script: str | None = None,
        *,
        url: str | None = None,
    ) -> None:
        """Inject JavaScript into the current page from source or URL."""
        if script is None and url is None:
            raise ValueError("scripts.add requires either script=... or url=...")
        if script is not None and url is not None:
            raise ValueError("scripts.add accepts script=... or url=..., not both")
        self.browser._command(
            "addscript",
            _decode=_none,
            script=optional(script),
            url=optional(url),
        )

    def add_style(
        self,
        content: str | None = None,
        *,
        url: str | None = None,
    ) -> None:
        """Inject CSS into the current page from source or URL."""
        if content is None and url is None:
            raise ValueError("scripts.add_style requires either content=... or url=...")
        if content is not None and url is not None:
            raise ValueError("scripts.add_style accepts content=... or url=..., not both")
        self.browser._command(
            "addstyle",
            _decode=_none,
            content=optional(content),
            url=optional(url),
        )


@dataclass(frozen=True, slots=True)
class Tabs:
    """Tab listing, creation, switching, and closing helpers."""

    browser: CommandTarget

    def list(self) -> tuple[TabInfo, ...]:
        """Return open tabs."""
        return self.browser._command("tab_list", _decode=tabs_from_data)

    def new(self, url: str | None = None, *, label: str | None = None) -> TabInfo:
        """Open a new tab and return its metadata."""
        return self.browser._command(
            "tab_new",
            url=optional(url),
            label=optional(label),
            _decode=tab_from_data,
        )

    def open(
        self,
        url: str,
        *,
        label: str | None = None,
        reuse: bool = True,
        wait_until: LoadState = "load",
    ) -> TabInfo:
        """Open a URL in a tab, reusing a labelled tab when available."""
        normalized_url = normalize_url(url)
        if label is None or not reuse:
            return self.new(normalized_url, label=label)

        try:
            tabs = self.list()
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map(
                    lambda confirmed: self._open_from_tabs(
                        normalized_url,
                        label,
                        confirmed,
                        wait_until,
                    )
                )
            raise
        return self._open_from_tabs(normalized_url, label, tabs, wait_until)

    def _open_from_tabs(
        self,
        normalized_url: str,
        label: str,
        tabs: Sequence[TabInfo],
        wait_until: LoadState,
    ) -> TabInfo:
        existing = _tab_with_label(tabs, label)
        if existing is None:
            return self.new(normalized_url, label=label)

        try:
            self.switch(id=existing.id)
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map(
                    lambda _value: self._navigate_reused(
                        existing,
                        normalized_url,
                        wait_until,
                    )
                )
            raise
        return self._navigate_reused(existing, normalized_url, wait_until)

    def _navigate_reused(
        self,
        existing: TabInfo,
        normalized_url: str,
        wait_until: LoadState,
    ) -> TabInfo:
        return self.browser._command(
            "navigate",
            _decode=lambda _data: replace(existing, url=normalized_url, active=True),
            url=normalized_url,
            waitUntil=wait_until,
        )

    def switch(
        self,
        *,
        id: str | None = None,
        label: str | None = None,
        index: int | None = None,
    ) -> TabSwitchResult:
        """Switch to a tab and return observed renderer state."""
        return self.browser._command(
            "tab_switch",
            _decode=tab_switch_from_data,
            tabId=self._resolve_selector(id=id, label=label, index=index, required=True),
        )

    def close(
        self,
        *,
        id: str | None = None,
        label: str | None = None,
        index: int | None = None,
    ) -> TabCloseResult:
        """Close a tab and return observed successor reactivation."""
        return self.browser._command(
            "tab_close",
            _decode=tab_close_result_from_data,
            tabId=self._resolve_selector(id=id, label=label, index=index),
        )

    def _resolve_selector(
        self,
        *,
        id: str | None = None,
        label: str | None = None,
        index: int | None = None,
        required: bool = False,
    ) -> str | Any:
        selected = [value is not None for value in (id, label, index)]
        if sum(selected) == 0:
            if required:
                raise ValueError("pass one of id, label, or index")
            return optional(None)
        if sum(selected) > 1:
            raise ValueError("pass exactly one of id, label, or index")
        if label is not None:
            return label
        return _tab_selector(id=id, index=index, required=required)


@dataclass(frozen=True, slots=True)
class Cookies:
    """Cookie import, export, and clearing helpers."""

    browser: CommandTarget

    def get(
        self,
        urls: Sequence[str] | None = None,
        *,
        unsafe_export_all: bool = False,
    ) -> tuple[Cookie, ...]:
        """Return cookies visible to the selected URLs."""
        return self.browser._command(
            "cookies_get",
            _decode=cookies_from_data,
            **cookies_get_params(urls, unsafe_export_all=unsafe_export_all),
        )

    def set(
        self,
        name: str | None = None,
        value: str | None = None,
        *,
        cookies: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
        url: str | None = None,
        domain: str | None = None,
        path: str | None = None,
        expires: int | None = None,
        http_only: bool | None = None,
        secure: bool | None = None,
        same_site: SameSite | None = None,
    ) -> None:
        """Set one cookie or a sequence of cookie dictionaries."""
        self.browser._command(
            "cookies_set",
            _decode=_none,
            **cookies_set_params(
                name=name,
                value=value,
                cookies=cookies,
                url=url,
                domain=domain,
                path=path,
                expires=expires,
                http_only=http_only,
                secure=secure,
                same_site=same_site,
            ),
        )

    def clear(self, *, unsafe_clear_all: bool = False) -> None:
        """Clear browser cookies."""
        self.browser._command(
            "cookies_clear",
            _decode=_none,
            **cookies_clear_params(unsafe_clear_all=unsafe_clear_all),
        )


@dataclass(frozen=True, slots=True)
class Storage:
    """Local and session storage helpers."""

    browser: CommandTarget

    def get(self, key: str | None = None, *, area: StorageArea = "local") -> Any:
        """Return one storage value or the whole storage area."""
        return self.browser._command(
            "storage_get",
            _decode=lambda data: data.get("value") if key is not None else data.get("data", {}),
            **storage_get_params(key, area=area),
        )

    def set(self, key: str, value: str, *, area: StorageArea = "local") -> None:
        """Set one storage value."""
        self.browser._command(
            "storage_set",
            _decode=_none,
            **storage_set_params(key, value, area=area),
        )

    def clear(self, *, area: StorageArea = "local") -> None:
        """Clear a storage area."""
        self.browser._command(
            "storage_clear",
            _decode=_none,
            **storage_clear_params(area=area),
        )


@dataclass(frozen=True, slots=True)
class Network:
    """Request routing, capture, HAR, and credential helpers."""

    browser: CommandTarget

    def route(
        self,
        url: str,
        *,
        abort: bool = False,
        response: RouteResponse | Mapping[str, Any] | None = None,
        status: int | None = None,
        body: str | None = None,
        content_type: str | None = None,
        headers: Mapping[str, str] | None = None,
        resource_type: str | None = None,
        resource_types: Sequence[str] | None = None,
    ) -> None:
        """Register a request route."""
        self.browser._command(
            "route",
            _decode=_none,
            **route_params(
                url=url,
                abort=abort,
                response=response,
                status=status,
                body=body,
                content_type=content_type,
                headers=headers,
                resource_type=resource_type,
                resource_types=resource_types,
            ),
        )

    def unroute(self, url: str | None = None) -> None:
        """Remove one route or all routes."""
        self.browser._command("unroute", _decode=_none, url=optional(url))

    def requests(
        self,
        *,
        clear: bool = False,
        url_pattern: str | None = None,
        resource_type: str | None = None,
        method: str | None = None,
        status: str | int | None = None,
    ) -> tuple[NetworkRequest, ...]:
        """Return captured network requests."""
        return self.browser._command(
            "requests",
            _decode=network_requests_from_data,
            **requests_params(
                clear=clear,
                url_pattern=url_pattern,
                resource_type=resource_type,
                method=method,
                status=status,
            ),
        )

    def request_detail(self, request_id: str) -> RequestDetail:
        """Return detailed request data for a captured request id."""
        return self.browser._command(
            "request_detail",
            requestId=request_id,
            _decode=request_detail_from_data,
        )

    def har_start(self, *, content: HarContentMode = "text") -> None:
        """Start HAR capture with the selected response-body content."""
        self.browser._command("har_start", _decode=_none, **har_start_params(content))

    def har_stop(self, path: str | Path | None = None) -> Path:
        """Stop HAR capture and return the written file path."""
        return self.browser._command(
            "har_stop",
            _decode=lambda data: _required_path(data, action="har_stop"),
            path=optional(path_value(path)),
        )

    def credentials(self, username: str, password: str) -> None:
        """Set HTTP authentication credentials."""
        self.browser._command(
            "credentials",
            _decode=_none,
            username=username,
            password=password,
        )


@dataclass(frozen=True, slots=True)
class Keyboard:
    """Keyboard typing, key press, and dispatch helpers."""

    browser: CommandTarget

    def type(self, text: str) -> None:
        """Type text with the keyboard."""
        self.browser._command("keyboard", _decode=_none, subaction="type", text=text)

    def insert_text(self, text: str) -> None:
        """Insert text without key events when supported."""
        self.browser._command("keyboard", _decode=_none, subaction="insertText", text=text)

    def press(self, key: str) -> None:
        """Press a key such as `Enter` or `Meta+K`."""
        self.browser._command("press", _decode=_none, key=key)

    def down(self, key: str, *, code: str | None = None, text: str | None = None) -> None:
        """Dispatch a key-down event."""
        self.dispatch("keyDown", key=key, code=code, text=text)

    def up(self, key: str, *, code: str | None = None) -> None:
        """Dispatch a key-up event."""
        self.dispatch("keyUp", key=key, code=code)

    def dispatch(
        self,
        event_type: str,
        *,
        key: str | None = None,
        code: str | None = None,
        text: str | None = None,
    ) -> None:
        """Dispatch a low-level keyboard event."""
        self.browser._command(
            "keyboard",
            _decode=_none,
            **keyboard_params(event_type, key=key, code=code, text=text),
        )


@dataclass(frozen=True, slots=True)
class Mouse:
    """Mouse movement, button, wheel, and dispatch helpers."""

    browser: CommandTarget

    def move(self, x: float, y: float) -> None:
        """Move the mouse to page coordinates."""
        self.browser._command("mousemove", _decode=_none, x=x, y=y)

    def down(self, *, button: MouseButton = "left") -> None:
        """Press a mouse button."""
        self.browser._command("mousedown", _decode=_none, button=button)

    def up(self, *, button: MouseButton = "left") -> None:
        """Release a mouse button."""
        self.browser._command("mouseup", _decode=_none, button=button)

    def wheel(
        self,
        delta_y: float = 100,
        *,
        delta_x: float = 0,
        x: float = 0,
        y: float = 0,
    ) -> None:
        """Scroll with the mouse wheel."""
        self.browser._command(
            "wheel",
            _decode=_none,
            **wheel_params(delta_y, delta_x=delta_x, x=x, y=y),
        )

    def dispatch(
        self,
        event_type: MouseEventType,
        *,
        x: float = 0,
        y: float = 0,
        button: str = "none",
        click_count: int = 0,
    ) -> None:
        """Dispatch a low-level mouse event."""
        self.browser._command(
            "mouse",
            _decode=_none,
            **mouse_params(event_type, x=x, y=y, button=button, click_count=click_count),
        )


@dataclass(frozen=True, slots=True)
class Session:
    """Native session and restore lifecycle."""

    browser: CommandTarget

    def status(self) -> SessionStatus:
        """Return current session, browser, restore, and save state."""
        return self.browser._command("session_info", _decode=session_status_from_data)


@dataclass(frozen=True, slots=True)
class State:
    """Browser storage-state save, load, and maintenance helpers."""

    browser: CommandTarget

    def save(self, path: str | Path | None = None, *, unsafe_export_all: bool = False) -> Path:
        """Save browser storage state and return the written file path."""
        return self.browser._command(
            "state_save",
            _decode=lambda data: _required_path(data, action="state_save"),
            **state_path_params(path, unsafeExportAll=unsafe_export_all),
        )

    def load(self, path: str | Path, *, unsafe_import_all: bool = False) -> None:
        """Load browser storage state from a file.

        Raises `BrowserError` when the session uses `allowed_domains`.
        """
        self.browser._command(
            "state_load",
            _decode=_none,
            **state_path_params(path, unsafeImportAll=unsafe_import_all),
        )

    def list(self) -> Mapping[str, Any]:
        """List saved storage states."""
        return self.browser._command("state_list")

    def show(self, path: str | Path) -> Mapping[str, Any]:
        """Show metadata for a saved storage state."""
        return self.browser._command("state_show", **state_path_params(path))

    def clear(self, path: str | Path | None = None) -> None:
        """Clear one saved state or all saved states."""
        self.browser._command("state_clear", _decode=_none, **state_path_params(path))

    def clean(self, *, days: int = 30) -> None:
        """Delete saved states older than a number of days."""
        self.browser._command("state_clean", _decode=_none, days=days)

    def rename(self, path: str | Path, name: str) -> None:
        """Rename a saved storage state."""
        self.browser._command(
            "state_rename",
            _decode=_none,
            **state_path_params(path, name=name),
        )


@dataclass(frozen=True, slots=True)
class Clipboard:
    """System clipboard helpers for the active browser context."""

    browser: CommandTarget

    def read(self) -> str:
        """Read text from the clipboard."""
        return self.browser._command(
            "clipboard",
            _decode=lambda data: _required_string(data, "text", action="clipboard"),
            subAction="read",
        )

    def write(self, text: str) -> None:
        """Write text to the clipboard."""
        self.browser._command("clipboard", _decode=_none, subAction="write", text=text)

    def copy(self) -> None:
        """Copy the current selection."""
        self.browser._command("clipboard", _decode=_none, subAction="copy")

    def paste(self) -> None:
        """Paste clipboard content."""
        self.browser._command("clipboard", _decode=_none, subAction="paste")


@dataclass(frozen=True, slots=True)
class Dialogs:
    """JavaScript dialog status and response helpers."""

    browser: CommandTarget

    def status(self) -> Mapping[str, Any]:
        """Return current dialog status."""
        return self.browser._command("dialog", response="status")

    def accept(self, prompt_text: str | None = None) -> None:
        """Accept the active dialog, optionally with prompt text."""
        self.browser._command(
            "dialog",
            _decode=_none,
            response="accept",
            promptText=optional(prompt_text),
        )

    def dismiss(self) -> None:
        """Dismiss the active dialog."""
        self.browser._command("dialog", _decode=_none, response="dismiss")


@dataclass(frozen=True, slots=True)
class Downloads:
    """Download triggering and waiting helpers."""

    browser: CommandTarget

    def download(self, selector: str, path: str | Path) -> Path:
        """Click a selector that starts a download and return the path."""
        return self.browser._command(
            "download",
            _decode=lambda data: _required_path(data, action="download"),
            selector=selector,
            path=path_value(path),
        )

    def wait(self, path: str | Path | None = None, *, timeout_ms: int | None = None) -> Path:
        """Wait for the next download and return the path."""
        return self.browser._command(
            "waitfordownload",
            _decode=lambda data: _required_path(data, action="waitfordownload"),
            path=optional(path_value(path)),
            timeout=optional(timeout_ms),
        )


@dataclass(frozen=True, slots=True)
class CDPFrames:
    """CDP frame discovery helpers."""

    browser: Any

    def list(self) -> Sequence[Any]:
        """Return frames for the active CDP page target."""
        return self.browser._cdp().frames()

    def get(
        self,
        *,
        selector: str | None = None,
        name: str | None = None,
        url: str | None = None,
    ) -> Any:
        """Return one CDP frame selected by iframe selector, name, or URL."""
        return self.browser._cdp().frame(selector=selector, name=name, url=url)


@dataclass(frozen=True, slots=True)
class CDP:
    """High-level Chrome DevTools Protocol helpers."""

    browser: Any
    frames: CDPFrames = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "frames", CDPFrames(self.browser))

    def evaluate(
        self,
        script: str,
        *,
        frame: Any = None,
        extension_id: str | None = None,
        context: Any = None,
        await_promise: bool = True,
        return_by_value: bool = True,
    ) -> Any:
        """Evaluate JavaScript through CDP in a frame or execution context."""
        return self.browser._cdp().evaluate(
            script,
            frame=frame,
            extension_id=extension_id,
            context=context,
            await_promise=await_promise,
            return_by_value=return_by_value,
        )

    def send(
        self,
        method: str,
        params: Mapping[str, Any] | None = None,
        *,
        session_id: str | None = None,
    ) -> Mapping[str, Any]:
        """Send one raw Chrome DevTools Protocol method."""
        return self.browser._cdp().send(method, params, session_id=session_id)

    def target(
        self,
        *,
        label: str | None = None,
        url: str | None = None,
        target_id: str | None = None,
    ) -> Any:
        """Return a CDP target handle selected by label, URL, or target id."""
        return self.browser._cdp().target(label=label, url=url, target_id=target_id)


@dataclass(frozen=True, slots=True)
class ActiveFrame:
    """Native active-frame selection helpers."""

    browser: CommandTarget

    def select(
        self,
        *,
        selector: str | None = None,
        name: str | None = None,
        url: str | None = None,
    ) -> None:
        """Select the active native frame."""
        self.browser._command(
            "frame",
            _decode=_none,
            selector=optional(selector),
            name=optional(name),
            url=optional(url),
        )

    def main(self) -> None:
        """Select the main native frame."""
        self.browser._command("mainframe", _decode=_none)


@dataclass(frozen=True, slots=True)
class Diff:
    """Snapshot diff helpers."""

    browser: CommandTarget

    def snapshot(
        self,
        baseline: str | Path | None = None,
        *,
        selector: str | None = None,
        compact: bool = False,
        max_depth: int | None = None,
    ) -> SnapshotDiff:
        """Compare the current snapshot with a baseline."""
        return self.browser._command(
            "diff_snapshot",
            _decode=_snapshot_diff,
            baseline=optional(path_value(baseline) if isinstance(baseline, Path) else baseline),
            selector=optional(selector),
            compact=compact,
            maxDepth=optional(max_depth),
        )


@dataclass(frozen=True, slots=True)
class Diagnostics:
    """Accessibility, console, error, vitals, and framework diagnostics."""

    browser: CommandTarget

    def console(self, *, clear: bool = False) -> tuple[ConsoleMessage, ...]:
        """Return captured console messages."""
        return self.browser._command("console", clear=clear, _decode=console_messages_from_data)

    def errors(self) -> Mapping[str, Any]:
        """Return captured page errors."""
        return self.browser._command("errors")

    def vitals(self) -> Mapping[str, Any]:
        """Return page vitals when supported by the native engine."""
        return self.browser._command("vitals")

    def accessibility(
        self,
        url: str | None = None,
        *,
        tags: Sequence[str] = (),
        selector: str | None = None,
    ) -> AccessibilityAudit:
        """Run an axe-core accessibility audit for a URL or the active page."""
        normalized_url = normalize_url(url) if url is not None else None
        return self.browser._command(
            "a11y",
            _decode=accessibility_audit_from_data,
            **accessibility_audit_params(
                normalized_url,
                tags=tags,
                selector=selector,
            ),
        )

    def react_tree(self, *, selector: str | None = None) -> Mapping[str, Any]:
        """Return React tree diagnostics, optionally scoped by selector."""
        return self.browser._command("react_tree", selector=optional(selector))


def _tab_selector(
    *,
    id: str | None = None,
    index: int | None = None,
    required: bool = False,
) -> str | Any:
    selected = [value is not None for value in (id, index)]
    if sum(selected) == 0:
        if required:
            raise ValueError("pass one of id or index")
        return optional(None)
    if sum(selected) > 1:
        raise ValueError("pass exactly one of id or index")
    if index is not None:
        if index < 0:
            raise ValueError("index must be non-negative")
        return f"t{index}"
    return cast(str, id)


def _tab_with_label(tabs: Sequence[TabInfo], label: str) -> TabInfo | None:
    return next((tab for tab in tabs if tab.label == label), None)


def _snapshot_diff(data: Mapping[str, Any]) -> SnapshotDiff:
    return snapshot_diff_from_data(data)


def _wait_before_screenshot(wait_ms: int) -> None:
    validate_screenshot_wait_ms(wait_ms)
    if wait_ms:
        sync_sleep(wait_ms / 1000)
