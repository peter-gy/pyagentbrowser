from __future__ import annotations

import json
from asyncio import sleep as async_sleep
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Protocol, TypeVar, overload

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
    webmcp_cancel_params,
    webmcp_invoke_params,
    webmcp_result_params,
    wheel_params,
)
from agentbrowser.domains import (
    _none,
    _required_path,
    _required_string,
    _tab_selector,
    _tab_with_label,
)
from agentbrowser.models import (
    AccessibilityAudit,
    ConfirmationRequired,
    ConsoleMessage,
    Cookie,
    DocumentScope,
    HarContentMode,
    JSONMapping,
    LoadState,
    MouseButton,
    MouseEventType,
    NetworkRequest,
    ReadMode,
    ReadResult,
    RequestDetail,
    RouteResponse,
    SameSite,
    Screenshot,
    ScrollResult,
    SessionStatus,
    SnapshotDiff,
    StorageArea,
    TabCloseResult,
    TabInfo,
    TabSwitchResult,
    WaitSelectorState,
    WebMCPInvocation,
    WebMCPTool,
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
    webmcp_invocation_from_data,
    webmcp_tools_from_data,
)

DEFAULT_SCREENSHOT_WAIT_MS = 100
T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class _AsyncScopedBrowser:
    controller: Any
    target_id: str | None
    frame_id: str | None

    async def _command(self, action: str, **params: Any) -> Any:
        if self.target_id is not None:
            params["_targetId"] = self.target_id
        params["_frameId"] = self.frame_id or ""
        return await self.controller._command(action, **params)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.controller, name)


class AsyncCommandTarget(Protocol):
    """Protocol for objects that can execute async native commands."""

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


@dataclass(frozen=True, slots=True)
class AsyncPage:
    """Async operations bound to one browser page and its main document."""

    browser: Any
    target_id: str | None = None
    frame_id: str | None = None
    frame_name: str = ""
    frame_url: str = ""
    parent_frame_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.browser, _AsyncScopedBrowser):
            object.__setattr__(
                self,
                "browser",
                _AsyncScopedBrowser(self.browser, self.target_id, self.frame_id),
            )

    async def _command(self, action: str, **params: Any) -> Any:
        return await self.browser._command(action, **params)

    @property
    def scope(self) -> DocumentScope:
        """Return the browser target and frame identity for this handle."""
        return DocumentScope(self.target_id, self.frame_id, self.frame_url or None)

    @property
    def find(self) -> Any:
        """Return live queries bound to this document."""
        from agentbrowser.query_async import AsyncQueries

        return AsyncQueries(self)

    @property
    def capture(self) -> AsyncCapture:
        """Return capture operations bound to this document."""
        return AsyncCapture(self)

    @property
    def frames(self) -> AsyncFrames:
        """Return child-frame discovery bound to this document."""
        return AsyncFrames(self)

    @property
    def scroll(self) -> AsyncScroll:
        """Return measured document and container scrolling."""
        return AsyncScroll(self)

    async def observe(self, spec: Any = None) -> Any:
        """Capture an accessibility snapshot bound to this document."""
        from agentbrowser.agent_async import AsyncSnapshot
        from agentbrowser.models import SnapshotSpec, snapshot_from_data

        capture_spec = spec or SnapshotSpec()
        data = await self._command(
            "snapshot",
            _decode=lambda value: snapshot_from_data(value, spec=capture_spec),
            selector=optional(capture_spec.selector),
            interactive=capture_spec.interactive,
            compact=capture_spec.compact,
            maxDepth=optional(capture_spec.max_depth),
            urls=capture_spec.urls,
        )
        return AsyncSnapshot(self, data)

    async def open(
        self,
        url: str,
        *,
        wait_until: LoadState = "load",
    ) -> None:
        """Navigate the current page to a URL.

        Example:
            ```python
            await browser.open("https://example.com")
            print(await browser.title())
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
                await self.browser._launch_process()
            except ConfirmationRequired as error:
                if error.pending is not None:
                    error.pending = error.pending.map(
                        lambda _value: self.open(url, wait_until=wait_until)
                    )
                raise
        await self.browser._command(
            "navigate",
            _decode=_none,
            url=normalize_url(url),
            waitUntil=wait_until,
        )

    async def title(self) -> str:
        """Return the current page title."""
        return await self.browser._command(
            "title",
            _decode=lambda data: _required_string(data, "title", action="title"),
        )

    async def url(self) -> str:
        """Return the current page URL."""
        return await self.browser._command(
            "url",
            _decode=lambda data: _required_string(data, "url", action="url"),
        )

    async def content(self) -> str:
        """Return the current page HTML."""
        return await self.browser._command(
            "content",
            _decode=lambda data: _required_string(data, "html", action="content"),
        )

    async def set_content(self, html: str) -> None:
        """Replace the current page document with HTML."""
        await self.browser._command("setcontent", _decode=_none, html=html)

    async def evaluate(self, script: str) -> Any:
        """Evaluate JavaScript in the current page context."""
        return await self.browser._command(
            "evaluate",
            _decode=lambda data: data.get("result"),
            script=script,
        )

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
        """Return agent-readable content for a URL or the active page.

        Example:
            ```python
            result = await browser.read(
                "https://example.com",
                mode=ReadMode.markdown(require=True),
            )
            print(result.content)
            ```
        """
        if url is None and not self.browser.is_launched:
            try:
                await self.browser._launch_process()
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
        return await self.browser._command(
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

    async def ready(
        self,
        *,
        timeout_ms: int | None = None,
        min_text_length: int = 1,
    ) -> None:
        """Wait until the page has readable body text."""
        if min_text_length < 0:
            raise ValueError("min_text_length must be non-negative")
        await self.wait_for_function(
            f"document.body && document.body.innerText.length >= {min_text_length}",
            timeout_ms=timeout_ms,
        )

    async def back(self) -> None:
        """Navigate back in history."""
        await self.browser._command("back", _decode=_none)

    async def forward(self) -> None:
        """Navigate forward in history."""
        await self.browser._command("forward", _decode=_none)

    async def reload(self) -> None:
        """Reload the current page."""
        await self.browser._command("reload", _decode=_none)

    async def wait_for_text(self, text: str, *, timeout_ms: int | None = None) -> None:
        """Wait until text appears."""
        await self.browser._command(
            "wait",
            _decode=_none,
            **wait_params(None, text=text, timeout_ms=timeout_ms),
        )

    async def wait_for_selector(
        self,
        selector: str,
        *,
        state: WaitSelectorState = "visible",
        timeout_ms: int | None = None,
    ) -> None:
        """Wait for a selector to reach a state."""
        await self.browser._command(
            "wait",
            _decode=_none,
            **wait_params(None, selector=selector, state=state, timeout_ms=timeout_ms),
        )

    async def wait_for_url(self, pattern: str, *, timeout_ms: int | None = None) -> None:
        """Wait for the page URL to match a pattern."""
        await self.browser._command(
            "wait",
            _decode=_none,
            **wait_params(None, url=pattern, timeout_ms=timeout_ms),
        )

    async def wait_for_function(self, predicate: str, *, timeout_ms: int | None = None) -> None:
        """Wait for a JavaScript predicate to become truthy."""
        await self.browser._command(
            "wait",
            _decode=_none,
            **wait_params(None, predicate=predicate, timeout_ms=timeout_ms),
        )

    async def wait_for_load_state(self, state: LoadState = "load") -> None:
        """Wait for a page load state."""
        await self.browser._command(
            "wait",
            _decode=_none,
            **wait_params(None, load_state=state),
        )


class AsyncFrame(AsyncPage):
    """Async operations bound to one child browsing context."""

    async def open(self, url: str, *, wait_until: LoadState = "load") -> None:
        del url, wait_until
        raise TypeError("AsyncFrame.open() cannot navigate a child browsing context")

    async def title(self) -> str:
        """Return this frame document's title."""
        return str(await self.evaluate("document.title"))

    async def url(self) -> str:
        """Return this frame document's current URL."""
        return str(await self.evaluate("location.href"))

    async def content(self) -> str:
        """Return this frame document's HTML."""
        return str(await self.evaluate("document.documentElement.outerHTML"))


@dataclass(frozen=True, slots=True)
class AsyncFrames:
    """Discover child browsing contexts from one async page or frame."""

    page: AsyncPage

    async def tree(self) -> tuple[AsyncFrame, ...]:
        """Return descendant frames with stable browser frame identities."""
        from agentbrowser.domains import _collect_frame_records

        data = await self.page._command("frame", _decode=lambda value: value, list=True)
        records: list[tuple[Mapping[str, Any], str | None]] = []
        _collect_frame_records(data.get("frameTree"), None, records)
        parent_scope = self.page.frame_id
        oopif_frames = data.get("oopifFrames")
        if isinstance(oopif_frames, list):
            for raw in oopif_frames:
                if isinstance(raw, Mapping) and isinstance(raw.get("id"), str):
                    parent_id = raw.get("parentId")
                    records.append(
                        (
                            raw,
                            str(parent_id) if isinstance(parent_id, str) else parent_scope,
                        )
                    )
        records = list({str(raw["id"]): (raw, parent_id) for raw, parent_id in records}.values())
        return tuple(
            AsyncFrame(
                self.page.browser.controller,
                target_id=self.page.target_id,
                frame_id=str(raw["id"]),
                frame_name=str(raw.get("name", "")),
                frame_url=str(raw.get("url", "")),
                parent_frame_id=parent_id,
            )
            for raw, parent_id in records
            if parent_id is not None and (parent_scope is None or parent_id == parent_scope)
        )

    async def get(
        self,
        *,
        selector: str | None = None,
        name: str | None = None,
        url: str | None = None,
    ) -> AsyncFrame:
        """Return one exact child frame selected by element, name, or URL."""
        selected = [value is not None for value in (selector, name, url)]
        if sum(selected) != 1:
            raise ValueError("pass exactly one of selector, name, or url")
        candidates = await self.tree()
        if selector is not None:
            if selector.startswith("@"):
                data = await self.page._command(
                    "frame", selector=selector, _decode=lambda value: value
                )
                frame_id = data.get("frameId")
                matches = [frame for frame in candidates if frame.frame_id == frame_id]
            else:
                from agentbrowser.domains import _frames_for_owner

                selector_json = json.dumps(selector)
                owner = await self.page.evaluate(
                    f"""(() => {{
                        const element = document.querySelector({selector_json});
                        if (!element || !['IFRAME', 'FRAME'].includes(element.tagName)) return null;
                        return {{name: element.name || element.id || '', url: element.src || ''}};
                    }})()"""
                )
                matches = list(_frames_for_owner(candidates, owner))
                if not matches and isinstance(owner, Mapping):
                    data = await self.page._command(
                        "frame", selector=selector, _decode=lambda value: value
                    )
                    frame_id = data.get("frameId")
                    if isinstance(frame_id, str):
                        matches = [
                            AsyncFrame(
                                self.page.browser.controller,
                                target_id=self.page.target_id,
                                frame_id=frame_id,
                                frame_name=str(owner.get("name", "")),
                                frame_url=str(owner.get("url", "")),
                                parent_frame_id=self.page.frame_id,
                            )
                        ]
        elif name is not None:
            matches = [frame for frame in candidates if frame.frame_name == name]
        else:
            matches = [frame for frame in candidates if frame.frame_url == url]
        criteria = selector if selector is not None else name if name is not None else url
        if not matches:
            available = ", ".join(
                f"{frame.frame_id}:{frame.frame_name or frame.frame_url or '<blank>'}"
                for frame in candidates[:8]
            )
            raise LookupError(
                f"no child frame matched {criteria!r}; available frames: {available or '<none>'}"
            )
        if len(matches) > 1:
            ids = ", ".join(frame.frame_id or "" for frame in matches)
            raise LookupError(f"multiple child frames matched {criteria!r}: {ids}")
        return matches[0]


@dataclass(frozen=True, slots=True)
class AsyncScroll:
    """Measured scrolling bound to one async page or frame document."""

    page: AsyncPage

    async def by(
        self,
        *,
        x: float = 0,
        y: float = 0,
        selector: str | None = None,
    ) -> ScrollResult:
        """Scroll a document or container and return its offsets before and after."""
        from agentbrowser.domains import _scroll_position

        selector_json = json.dumps(selector)
        result = await self.page.evaluate(
            f"""(() => {{
                const element = {selector_json} === null
                    ? document.scrollingElement
                    : document.querySelector({selector_json});
                if (!element) throw new Error('scroll container not found');
                const before = {{x: element.scrollLeft, y: element.scrollTop}};
                element.scrollBy({{left: {x!r}, top: {y!r}, behavior: 'instant'}});
                return {{before, after: {{x: element.scrollLeft, y: element.scrollTop}}}};
            }})()"""
        )
        if not isinstance(result, Mapping):
            from agentbrowser.models import NativeParseError

            raise NativeParseError("scroll evaluation must return an object")
        return ScrollResult(
            self.page.scope,
            selector or "document",
            _scroll_position(result.get("before")),
            _scroll_position(result.get("after")),
        )


@dataclass(frozen=True, slots=True)
class AsyncCapture:
    """Async screenshot and PDF capture helpers."""

    browser: AsyncCommandTarget

    async def screenshot(
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
        await _wait_before_screenshot(wait_ms)
        if path is not None:
            Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        if output_dir is not None:
            Path(output_dir).expanduser().mkdir(parents=True, exist_ok=True)
        screenshot = await self.browser._command(
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
        scope = getattr(self.browser, "scope", None)
        return replace(screenshot, scope=scope if isinstance(scope, DocumentScope) else None)

    async def pdf(
        self,
        path: str | Path | None = None,
        *,
        print_background: bool = True,
        landscape: bool = False,
        prefer_css_page_size: bool = False,
    ) -> Path:
        """Print the current page to PDF."""
        return await self.browser._command(
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
class AsyncScripts:
    """Async JavaScript and stylesheet injection helpers."""

    browser: Any

    async def add_init(
        self,
        script: str | None = None,
        *,
        path: str | Path | None = None,
    ) -> str:
        """Add a script that runs before future page scripts."""
        source = exclusive_source("scripts.add_init", inline=script, path=path)
        if not self.browser.is_launched:
            try:
                await self.browser._launch_process()
            except ConfirmationRequired as error:
                if error.pending is not None:
                    error.pending = error.pending.map(lambda _value: self._register_init(source))
                raise
        return await self._register_init(source)

    async def _register_init(self, source: str) -> str:
        return await self.browser._command(
            "addinitscript",
            _decode=lambda data: _required_string(data, "identifier", action="addinitscript"),
            script=source,
        )

    async def remove_init(self, identifier: str) -> None:
        """Remove a previously registered init script."""
        await self.browser._command("removeinitscript", _decode=_none, identifier=identifier)

    async def add(
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
        await self.browser._command(
            "addscript",
            _decode=_none,
            script=optional(script),
            url=optional(url),
        )

    async def add_style(
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
        await self.browser._command(
            "addstyle",
            _decode=_none,
            content=optional(content),
            url=optional(url),
        )


@dataclass(frozen=True, slots=True)
class AsyncTabs:
    """Async tab listing, creation, switching, and closing helpers."""

    browser: AsyncCommandTarget

    async def list(self) -> tuple[TabInfo, ...]:
        """Return open tabs."""
        return await self.browser._command("tab_list", _decode=tabs_from_data)

    async def get(
        self,
        *,
        id: str | None = None,
        label: str | None = None,
        index: int | None = None,
    ) -> AsyncPage:
        """Return a page handle bound to one exact browser target."""
        selected = [value is not None for value in (id, label, index)]
        if sum(selected) != 1:
            raise ValueError("pass exactly one of id, label, or index")
        tabs = await self.list()
        if index is not None:
            matches = [tabs[index]] if 0 <= index < len(tabs) else []
        elif label is not None:
            matches = [tab for tab in tabs if tab.label == label]
        else:
            matches = [tab for tab in tabs if id in {tab.id, tab.target_id}]
        if not matches:
            raise LookupError("no browser page matched the requested tab")
        if len(matches) > 1:
            raise LookupError("multiple browser pages matched the requested tab")
        tab = matches[0]
        return AsyncPage(self.browser, target_id=tab.target_id or tab.id)

    async def new(self, url: str | None = None, *, label: str | None = None) -> TabInfo:
        """Open a new tab and return its metadata."""
        return await self.browser._command(
            "tab_new",
            url=optional(url),
            label=optional(label),
            _decode=tab_from_data,
        )

    async def open(
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
            return await self.new(normalized_url, label=label)

        try:
            tabs = await self.list()
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
        return await self._open_from_tabs(normalized_url, label, tabs, wait_until)

    async def _open_from_tabs(
        self,
        normalized_url: str,
        label: str,
        tabs: Sequence[TabInfo],
        wait_until: LoadState,
    ) -> TabInfo:
        existing = _tab_with_label(tabs, label)
        if existing is None:
            return await self.new(normalized_url, label=label)

        try:
            await self.switch(id=existing.id)
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
        return await self._navigate_reused(existing, normalized_url, wait_until)

    async def _navigate_reused(
        self,
        existing: TabInfo,
        normalized_url: str,
        wait_until: LoadState,
    ) -> TabInfo:
        return await self.browser._command(
            "navigate",
            _decode=lambda _data: replace(existing, url=normalized_url, active=True),
            url=normalized_url,
            waitUntil=wait_until,
        )

    async def switch(
        self,
        *,
        id: str | None = None,
        label: str | None = None,
        index: int | None = None,
    ) -> TabSwitchResult:
        """Switch to a tab and return observed renderer state."""
        return await self.browser._command(
            "tab_switch",
            _decode=tab_switch_from_data,
            tabId=await self._resolve_selector(id=id, label=label, index=index, required=True),
        )

    async def close(
        self,
        *,
        id: str | None = None,
        label: str | None = None,
        index: int | None = None,
    ) -> TabCloseResult:
        """Close a tab and return observed successor reactivation."""
        return await self.browser._command(
            "tab_close",
            _decode=tab_close_result_from_data,
            tabId=await self._resolve_selector(id=id, label=label, index=index),
        )

    async def _resolve_selector(
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
class AsyncCookies:
    """Async cookie import, export, and clearing helpers."""

    browser: AsyncCommandTarget

    async def get(
        self,
        urls: Sequence[str] | None = None,
        *,
        unsafe_export_all: bool = False,
    ) -> tuple[Cookie, ...]:
        """Return cookies visible to the selected URLs."""
        return await self.browser._command(
            "cookies_get",
            _decode=cookies_from_data,
            **cookies_get_params(urls, unsafe_export_all=unsafe_export_all),
        )

    async def set(
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
        await self.browser._command(
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

    async def clear(self, *, unsafe_clear_all: bool = False) -> None:
        """Clear browser cookies."""
        await self.browser._command(
            "cookies_clear",
            _decode=_none,
            **cookies_clear_params(unsafe_clear_all=unsafe_clear_all),
        )


@dataclass(frozen=True, slots=True)
class AsyncStorage:
    """Async local and session storage helpers."""

    browser: AsyncCommandTarget

    async def get(self, key: str | None = None, *, area: StorageArea = "local") -> Any:
        """Return one storage value or the whole storage area."""
        return await self.browser._command(
            "storage_get",
            _decode=lambda data: data.get("value") if key is not None else data.get("data", {}),
            **storage_get_params(key, area=area),
        )

    async def set(self, key: str, value: str, *, area: StorageArea = "local") -> None:
        """Set one storage value."""
        await self.browser._command(
            "storage_set",
            _decode=_none,
            **storage_set_params(key, value, area=area),
        )

    async def clear(self, *, area: StorageArea = "local") -> None:
        """Clear a storage area."""
        await self.browser._command(
            "storage_clear",
            _decode=_none,
            **storage_clear_params(area=area),
        )


@dataclass(frozen=True, slots=True)
class AsyncNetwork:
    """Async request routing, capture, HAR, and credential helpers."""

    browser: AsyncCommandTarget

    async def route(
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
        await self.browser._command(
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

    async def unroute(self, url: str | None = None) -> None:
        """Remove one route or all routes."""
        await self.browser._command("unroute", _decode=_none, url=optional(url))

    async def requests(
        self,
        *,
        clear: bool = False,
        url_pattern: str | None = None,
        resource_type: str | None = None,
        method: str | None = None,
        status: str | int | None = None,
    ) -> tuple[NetworkRequest, ...]:
        """Return captured network requests."""
        return await self.browser._command(
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

    async def request_detail(self, request_id: str) -> RequestDetail:
        """Return detailed request data for a captured request id."""
        return await self.browser._command(
            "request_detail",
            requestId=request_id,
            _decode=request_detail_from_data,
        )

    async def har_start(self, *, content: HarContentMode = "text") -> None:
        """Start HAR capture with the selected response-body content."""
        await self.browser._command("har_start", _decode=_none, **har_start_params(content))

    async def har_stop(self, path: str | Path | None = None) -> Path:
        """Stop HAR capture and return the written file path."""
        return await self.browser._command(
            "har_stop",
            _decode=lambda data: _required_path(data, action="har_stop"),
            path=optional(path_value(path)),
        )

    async def credentials(self, username: str, password: str) -> None:
        """Set HTTP authentication credentials."""
        await self.browser._command(
            "credentials",
            _decode=_none,
            username=username,
            password=password,
        )


@dataclass(frozen=True, slots=True)
class AsyncKeyboard:
    """Async keyboard typing, key press, and dispatch helpers."""

    browser: AsyncCommandTarget

    async def type(self, text: str) -> None:
        """Type text with the keyboard."""
        await self.browser._command("keyboard", _decode=_none, subaction="type", text=text)

    async def insert_text(self, text: str) -> None:
        """Insert text without key events when supported."""
        await self.browser._command(
            "keyboard",
            _decode=_none,
            subaction="insertText",
            text=text,
        )

    async def press(self, key: str) -> None:
        """Press a key such as `Enter` or `Meta+K`."""
        await self.browser._command("press", _decode=_none, key=key)

    async def down(self, key: str, *, code: str | None = None, text: str | None = None) -> None:
        """Dispatch a key-down event."""
        await self.dispatch("keyDown", key=key, code=code, text=text)

    async def up(self, key: str, *, code: str | None = None) -> None:
        """Dispatch a key-up event."""
        await self.dispatch("keyUp", key=key, code=code)

    async def dispatch(
        self,
        event_type: str,
        *,
        key: str | None = None,
        code: str | None = None,
        text: str | None = None,
    ) -> None:
        """Dispatch a low-level keyboard event."""
        await self.browser._command(
            "keyboard",
            _decode=_none,
            **keyboard_params(event_type, key=key, code=code, text=text),
        )


@dataclass(frozen=True, slots=True)
class AsyncMouse:
    """Async mouse movement, button, wheel, and dispatch helpers."""

    browser: AsyncCommandTarget

    async def move(self, x: float, y: float) -> None:
        """Move the mouse to page coordinates."""
        await self.browser._command("mousemove", _decode=_none, x=x, y=y)

    async def down(self, *, button: MouseButton = "left") -> None:
        """Press a mouse button."""
        await self.browser._command("mousedown", _decode=_none, button=button)

    async def up(self, *, button: MouseButton = "left") -> None:
        """Release a mouse button."""
        await self.browser._command("mouseup", _decode=_none, button=button)

    async def wheel(
        self,
        delta_y: float = 100,
        *,
        delta_x: float = 0,
        x: float = 0,
        y: float = 0,
    ) -> None:
        """Scroll with the mouse wheel."""
        await self.browser._command(
            "wheel",
            _decode=_none,
            **wheel_params(delta_y, delta_x=delta_x, x=x, y=y),
        )

    async def dispatch(
        self,
        event_type: MouseEventType,
        *,
        x: float = 0,
        y: float = 0,
        button: str = "none",
        click_count: int = 0,
    ) -> None:
        """Dispatch a low-level mouse event."""
        await self.browser._command(
            "mouse",
            _decode=_none,
            **mouse_params(event_type, x=x, y=y, button=button, click_count=click_count),
        )


@dataclass(frozen=True, slots=True)
class AsyncSession:
    """Async native session and restore lifecycle."""

    browser: AsyncCommandTarget

    async def status(self) -> SessionStatus:
        """Return current session, browser, restore, and save state."""
        return await self.browser._command("session_info", _decode=session_status_from_data)


@dataclass(frozen=True, slots=True)
class AsyncState:
    """Async browser storage-state save, load, and maintenance helpers."""

    browser: AsyncCommandTarget

    async def save(
        self,
        path: str | Path | None = None,
        *,
        unsafe_export_all: bool = False,
    ) -> Path:
        """Save browser storage state and return the written file path."""
        return await self.browser._command(
            "state_save",
            _decode=lambda data: _required_path(data, action="state_save"),
            **state_path_params(path, unsafeExportAll=unsafe_export_all),
        )

    async def load(self, path: str | Path, *, unsafe_import_all: bool = False) -> None:
        """Load browser storage state from a file.

        Raises `BrowserError` when the session uses `allowed_domains`.
        """
        await self.browser._command(
            "state_load",
            _decode=_none,
            **state_path_params(path, unsafeImportAll=unsafe_import_all),
        )

    async def list(self) -> Mapping[str, Any]:
        """List saved storage states."""
        return await self.browser._command("state_list")

    async def show(self, path: str | Path) -> Mapping[str, Any]:
        """Show metadata for a saved storage state."""
        return await self.browser._command("state_show", **state_path_params(path))

    async def clear(self, path: str | Path | None = None) -> None:
        """Clear one saved state or all saved states."""
        await self.browser._command("state_clear", _decode=_none, **state_path_params(path))

    async def clean(self, *, days: int = 30) -> None:
        """Delete saved states older than a number of days."""
        await self.browser._command("state_clean", _decode=_none, days=days)

    async def rename(self, path: str | Path, name: str) -> None:
        """Rename a saved storage state."""
        await self.browser._command(
            "state_rename",
            _decode=_none,
            **state_path_params(path, name=name),
        )


@dataclass(frozen=True, slots=True)
class AsyncClipboard:
    """Async system clipboard helpers for the active browser context."""

    browser: AsyncCommandTarget

    async def read(self) -> str:
        """Read text from the clipboard."""
        return await self.browser._command(
            "clipboard",
            _decode=lambda data: _required_string(data, "text", action="clipboard"),
            subAction="read",
        )

    async def write(self, text: str) -> None:
        """Write text to the clipboard."""
        await self.browser._command(
            "clipboard",
            _decode=_none,
            subAction="write",
            text=text,
        )

    async def copy(self) -> None:
        """Copy the current selection."""
        await self.browser._command("clipboard", _decode=_none, subAction="copy")

    async def paste(self) -> None:
        """Paste clipboard content."""
        await self.browser._command("clipboard", _decode=_none, subAction="paste")


@dataclass(frozen=True, slots=True)
class AsyncDialogs:
    """Async JavaScript dialog status and response helpers."""

    browser: AsyncCommandTarget

    async def status(self) -> Mapping[str, Any]:
        """Return current dialog status."""
        return await self.browser._command("dialog", response="status")

    async def accept(self, prompt_text: str | None = None) -> None:
        """Accept the active dialog, optionally with prompt text."""
        await self.browser._command(
            "dialog",
            _decode=_none,
            response="accept",
            promptText=optional(prompt_text),
        )

    async def dismiss(self) -> None:
        """Dismiss the active dialog."""
        await self.browser._command("dialog", _decode=_none, response="dismiss")


@dataclass(frozen=True, slots=True)
class AsyncDownloads:
    """Async download triggering and waiting helpers."""

    browser: AsyncCommandTarget

    async def download(self, selector: str, path: str | Path) -> Path:
        """Click a selector that starts a download and return the path."""
        return await self.browser._command(
            "download",
            _decode=lambda data: _required_path(data, action="download"),
            selector=selector,
            path=path_value(path),
        )

    async def wait(self, path: str | Path | None = None, *, timeout_ms: int | None = None) -> Path:
        """Wait for the next download and return the path."""
        return await self.browser._command(
            "waitfordownload",
            _decode=lambda data: _required_path(data, action="waitfordownload"),
            path=optional(path_value(path)),
            timeout=optional(timeout_ms),
        )


@dataclass(frozen=True, slots=True)
class AsyncCDPFrames:
    """Async CDP frame discovery helpers."""

    browser: Any

    async def list(self) -> Sequence[Any]:
        """Return frames for the active CDP page target."""
        return await self.browser._cdp().frames()

    async def get(
        self,
        *,
        selector: str | None = None,
        name: str | None = None,
        url: str | None = None,
    ) -> Any:
        """Return one CDP frame selected by iframe selector, name, or URL."""
        return await self.browser._cdp().frame(selector=selector, name=name, url=url)


@dataclass(frozen=True, slots=True)
class AsyncCDP:
    """Async high-level Chrome DevTools Protocol helpers."""

    browser: Any
    frames: AsyncCDPFrames = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "frames", AsyncCDPFrames(self.browser))

    async def evaluate(
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
        return await self.browser._cdp().evaluate(
            script,
            frame=frame,
            extension_id=extension_id,
            context=context,
            await_promise=await_promise,
            return_by_value=return_by_value,
        )

    async def send(
        self,
        method: str,
        params: Mapping[str, Any] | None = None,
        *,
        session_id: str | None = None,
    ) -> Mapping[str, Any]:
        """Send one raw Chrome DevTools Protocol method."""
        return await self.browser._cdp().send(method, params, session_id=session_id)

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
class AsyncDiff:
    """Async snapshot diff helpers."""

    browser: AsyncCommandTarget

    async def snapshot(
        self,
        baseline: str | Path | None = None,
        *,
        selector: str | None = None,
        compact: bool = False,
        max_depth: int | None = None,
    ) -> SnapshotDiff:
        """Compare the current snapshot with a baseline."""
        return await self.browser._command(
            "diff_snapshot",
            _decode=_snapshot_diff,
            baseline=optional(path_value(baseline) if isinstance(baseline, Path) else baseline),
            selector=optional(selector),
            compact=compact,
            maxDepth=optional(max_depth),
        )


@dataclass(frozen=True, slots=True)
class AsyncDiagnostics:
    """Async accessibility, console, error, vitals, and framework diagnostics."""

    browser: AsyncCommandTarget

    async def console(self, *, clear: bool = False) -> tuple[ConsoleMessage, ...]:
        """Return captured console messages."""
        return await self.browser._command(
            "console", clear=clear, _decode=console_messages_from_data
        )

    async def errors(self) -> Mapping[str, Any]:
        """Return captured page errors."""
        return await self.browser._command("errors")

    async def vitals(self) -> Mapping[str, Any]:
        """Return page vitals when supported by the native engine."""
        return await self.browser._command("vitals")

    async def accessibility(
        self,
        url: str | None = None,
        *,
        tags: Sequence[str] = (),
        selector: str | None = None,
    ) -> AccessibilityAudit:
        """Run an axe-core accessibility audit for a URL or the active page."""
        normalized_url = normalize_url(url) if url is not None else None
        return await self.browser._command(
            "a11y",
            _decode=accessibility_audit_from_data,
            **accessibility_audit_params(
                normalized_url,
                tags=tags,
                selector=selector,
            ),
        )

    async def react_tree(self, *, selector: str | None = None) -> Mapping[str, Any]:
        """Return React tree diagnostics, optionally scoped by selector."""
        return await self.browser._command("react_tree", selector=optional(selector))


@dataclass(frozen=True, slots=True)
class AsyncWebMCP:
    """Async discovery and invocation for tools exposed by the active page."""

    browser: AsyncCommandTarget

    async def list(self) -> tuple[WebMCPTool, ...]:
        """Return WebMCP tools exposed by the active page and its frames."""
        return await self.browser._command("webmcp_list", _decode=webmcp_tools_from_data)

    async def invoke(
        self,
        tool: str,
        params: Mapping[str, Any] | None = None,
        *,
        frame_id: str | None = None,
        detach: bool = False,
        timeout_ms: int | None = None,
    ) -> WebMCPInvocation:
        """Invoke a page tool and return its current lifecycle state."""
        return await self.browser._command(
            "webmcp_invoke",
            _decode=webmcp_invocation_from_data,
            **webmcp_invoke_params(
                tool,
                params,
                frame_id=frame_id,
                detach=detach,
                timeout_ms=timeout_ms,
            ),
        )

    async def result(
        self, invocation_id: str, *, timeout_ms: int | None = None
    ) -> WebMCPInvocation:
        """Wait for a detached invocation and return its current state."""
        return await self.browser._command(
            "webmcp_result",
            _decode=webmcp_invocation_from_data,
            **webmcp_result_params(invocation_id, timeout_ms=timeout_ms),
        )

    async def cancel(self, invocation_id: str) -> WebMCPInvocation:
        """Cancel an active invocation and return its terminal state."""
        return await self.browser._command(
            "webmcp_cancel",
            _decode=webmcp_invocation_from_data,
            **webmcp_cancel_params(invocation_id),
        )


def _snapshot_diff(data: Mapping[str, Any]) -> SnapshotDiff:
    return snapshot_diff_from_data(data)


async def _wait_before_screenshot(wait_ms: int) -> None:
    validate_screenshot_wait_ms(wait_ms)
    if wait_ms:
        await async_sleep(wait_ms / 1000)
