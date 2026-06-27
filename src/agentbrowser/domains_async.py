from __future__ import annotations

from asyncio import sleep as async_sleep
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from typing_extensions import Self

from agentbrowser._browser_common import (
    exclusive_source,
    normalize_url,
    snapshot_diff_from_data,
    validate_screenshot_wait_ms,
)
from agentbrowser.command_params import (
    click_params,
    cookies_clear_params,
    cookies_get_params,
    cookies_set_params,
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
from agentbrowser.domains import (
    _active_tab,
    _tab_selector,
    _tab_with_label,
    _xpath_selector,
)
from agentbrowser.models import (
    BoundingBox,
    BrowserError,
    ConsoleMessage,
    Cookie,
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
    SnapshotDiff,
    StorageArea,
    TabInfo,
    WaitSelectorState,
    bounding_box_from_data,
    console_messages_from_data,
    cookies_from_data,
    network_requests_from_data,
    path_value,
    read_result_from_data,
    ref_selector,
    request_detail_from_data,
    screenshot_from_data,
    tab_from_data,
    tabs_from_data,
)

DEFAULT_SCREENSHOT_WAIT_MS = 100


class AsyncCommandTarget(Protocol):
    """Protocol for objects that can execute async native commands."""

    async def _command(self, action: str, **params: Any) -> JSONMapping:
        """Execute one native command."""
        ...


@dataclass(frozen=True, slots=True)
class AsyncPage:
    """Async page navigation, document, and wait helpers."""

    browser: Any

    async def open(
        self,
        url: str,
        *,
        wait_until: LoadState = "load",
    ) -> Mapping[str, Any]:
        """Navigate the current page to a URL.

        Parameters
        ----------
        url
            Absolute URL or host-like value. Host-like values are normalized to
            `https://...`.
        wait_until
            Load state the native engine should wait for.

        Returns
        -------
        Mapping[str, object]
            Native navigation response data.
        """
        if not self.browser.is_launched:
            await self.browser.launch_process()
        return await self.browser._command(
            "navigate",
            url=normalize_url(url),
            waitUntil=wait_until,
        )

    async def title(self) -> str:
        """Return the current page title."""
        return str((await self.browser._command("title")).get("title", ""))

    async def url(self) -> str:
        """Return the current page URL."""
        return str((await self.browser._command("url")).get("url", ""))

    async def content(self) -> str:
        """Return the current page HTML."""
        return str((await self.browser._command("content")).get("html", ""))

    async def set_content(self, html: str) -> Mapping[str, Any]:
        """Replace the current page document with HTML."""
        return await self.browser._command("setcontent", html=html)

    async def evaluate(self, script: str) -> Any:
        """Evaluate JavaScript in the current page context."""
        return (await self.browser._command("evaluate", script=script)).get("result")

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
        if url is None and not self.browser.is_launched:
            await self.browser.launch_process()
        normalized_url = normalize_url(url) if url is not None else None
        data = await self.browser._command(
            "read",
            **read_params(
                normalized_url,
                mode=mode,
                filter=filter,
                timeout_ms=timeout_ms,
                headers=headers,
                allowed_domains=allowed_domains,
            ),
        )
        return read_result_from_data(data)

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

    async def back(self) -> Mapping[str, Any]:
        """Navigate back in history."""
        return await self.browser._command("back")

    async def forward(self) -> Mapping[str, Any]:
        """Navigate forward in history."""
        return await self.browser._command("forward")

    async def reload(self) -> Mapping[str, Any]:
        """Reload the current page."""
        return await self.browser._command("reload")

    async def wait_for_text(self, text: str, *, timeout_ms: int | None = None) -> None:
        """Wait until text appears."""
        await self.browser._command("wait", **wait_params(None, text=text, timeout_ms=timeout_ms))

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
            **wait_params(None, selector=selector, state=state, timeout_ms=timeout_ms),
        )

    async def wait_for_url(self, pattern: str, *, timeout_ms: int | None = None) -> None:
        """Wait for the page URL to match a pattern."""
        await self.browser._command("wait", **wait_params(None, url=pattern, timeout_ms=timeout_ms))

    async def wait_for_function(self, predicate: str, *, timeout_ms: int | None = None) -> None:
        """Wait for a JavaScript predicate to become truthy."""
        await self.browser._command(
            "wait",
            **wait_params(None, predicate=predicate, timeout_ms=timeout_ms),
        )

    async def wait_for_load_state(self, state: LoadState = "load") -> None:
        """Wait for a page load state."""
        await self.browser._command("wait", **wait_params(None, load_state=state))


@dataclass(frozen=True, slots=True)
class AsyncFind:
    """Async factory for CSS, ref, and semantic locators."""

    browser: Any

    def css(self, selector: str) -> AsyncLocator:
        """Return a CSS selector locator."""
        return AsyncLocator(self.browser, selector)

    def xpath(self, expression: str) -> AsyncLocator:
        """Return a locator for an XPath expression.

        Parameters
        ----------
        expression
            XPath expression, with or without the native `xpath=` prefix.
        """
        return AsyncLocator(self.browser, _xpath_selector(expression))

    def ref(self, ref_id: str) -> AsyncLocator:
        """Return a locator for a snapshot ref such as `@r1`."""
        return AsyncLocator(self.browser, ref_selector(ref_id))

    def role(
        self,
        role: str,
        *,
        name: str | None = None,
        exact: bool = False,
    ) -> AsyncSemanticLocator:
        """Return a semantic locator for an accessible role."""
        return AsyncSemanticLocator(
            self.browser,
            "getbyrole",
            {"role": role, "name": optional(name), "exact": exact},
        )

    def text(self, text: str, *, exact: bool = False) -> AsyncSemanticLocator:
        """Return a semantic locator for visible text."""
        return AsyncSemanticLocator(self.browser, "getbytext", {"text": text, "exact": exact})

    def label(self, label: str, *, exact: bool = False) -> AsyncSemanticLocator:
        """Return a semantic locator for a form label."""
        return AsyncSemanticLocator(self.browser, "getbylabel", {"label": label, "exact": exact})

    def placeholder(self, placeholder: str, *, exact: bool = False) -> AsyncSemanticLocator:
        """Return a semantic locator for placeholder text."""
        return AsyncSemanticLocator(
            self.browser,
            "getbyplaceholder",
            {"placeholder": placeholder, "exact": exact},
        )

    def alt_text(self, text: str, *, exact: bool = False) -> AsyncSemanticLocator:
        """Return a semantic locator for image alt text."""
        return AsyncSemanticLocator(self.browser, "getbyalttext", {"text": text, "exact": exact})

    def title(self, text: str, *, exact: bool = False) -> AsyncSemanticLocator:
        """Return a semantic locator for title text."""
        return AsyncSemanticLocator(self.browser, "getbytitle", {"text": text, "exact": exact})

    def test_id(self, test_id: str) -> AsyncSemanticLocator:
        """Return a semantic locator for a test id."""
        return AsyncSemanticLocator(self.browser, "getbytestid", {"testId": test_id})


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
        data = await self.browser._command(
            "screenshot",
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
        return screenshot_from_data(data, format=format)

    async def pdf(
        self,
        path: str | Path | None = None,
        *,
        print_background: bool = True,
        landscape: bool = False,
        prefer_css_page_size: bool = False,
    ) -> Path:
        """Print the current page to PDF."""
        data = await self.browser._command(
            "pdf",
            **pdf_params(
                path=path,
                print_background=print_background,
                landscape=landscape,
                prefer_css_page_size=prefer_css_page_size,
            ),
        )
        return Path(str(data["path"]))


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
            await self.browser.launch_process()

        data = await self.browser._command("addinitscript", script=source)
        return str(data["identifier"])

    async def remove_init(self, identifier: str) -> Mapping[str, Any]:
        """Remove a previously registered init script."""
        return await self.browser._command("removeinitscript", identifier=identifier)

    async def add(
        self,
        script: str | None = None,
        *,
        url: str | None = None,
    ) -> Mapping[str, Any]:
        """Inject JavaScript into the current page from source or URL."""
        if script is None and url is None:
            raise ValueError("scripts.add requires either script=... or url=...")
        if script is not None and url is not None:
            raise ValueError("scripts.add accepts script=... or url=..., not both")
        return await self.browser._command("addscript", script=optional(script), url=optional(url))

    async def add_style(
        self,
        content: str | None = None,
        *,
        url: str | None = None,
    ) -> Mapping[str, Any]:
        """Inject CSS into the current page from source or URL."""
        if content is None and url is None:
            raise ValueError("scripts.add_style requires either content=... or url=...")
        if content is not None and url is not None:
            raise ValueError("scripts.add_style accepts content=... or url=..., not both")
        return await self.browser._command("addstyle", content=optional(content), url=optional(url))


@dataclass(frozen=True, slots=True)
class AsyncLocator:
    """Async action handle for one CSS selector or snapshot ref selector."""

    browser: Any
    selector: str

    async def click(self, *, button: MouseButton = "left", click_count: int = 1) -> Self:
        """Click the located element and return this locator."""
        await self.browser._command(
            "click",
            **click_params(self.selector, button=button, click_count=click_count),
        )
        return self

    async def fill(self, value: str) -> Self:
        """Fill the located form control."""
        await self.browser._command("fill", selector=self.selector, value=value)
        return self

    async def select(self, value: str) -> Self:
        """Select an option value."""
        await self.browser._command("select", selector=self.selector, value=value)
        return self

    async def check(self) -> Self:
        """Check the located checkbox or radio control."""
        await self.browser._command("check", selector=self.selector)
        return self

    async def uncheck(self) -> Self:
        """Uncheck the located checkbox control."""
        await self.browser._command("uncheck", selector=self.selector)
        return self

    async def type(self, text: str) -> Self:
        """Type text into the located element."""
        await self.browser._command("type", selector=self.selector, text=text)
        return self

    async def press(self, key: str) -> Self:
        """Focus the element and press a key."""
        await self.browser._command("click", selector=self.selector)
        await self.browser.keyboard.press(key)
        return self

    def nth(self, index: int) -> AsyncSemanticLocator:
        """Return a locator for the nth match."""
        return AsyncSemanticLocator(
            self.browser, "nth", {"selector": self.selector, "index": index}
        )

    def first(self) -> AsyncSemanticLocator:
        """Return a locator for the first match."""
        return self.nth(0)

    async def hover(self) -> Self:
        """Hover the located element."""
        await self.browser._command("hover", selector=self.selector)
        return self

    async def focus(self) -> Self:
        """Focus the located element."""
        await self.browser._command("focus", selector=self.selector)
        return self

    async def clear(self) -> Self:
        """Clear the located form control."""
        await self.browser._command("clear", selector=self.selector)
        return self

    async def select_all(self) -> Self:
        """Select all text in the located control."""
        await self.browser._command("selectall", selector=self.selector)
        return self

    async def scroll_into_view(self) -> Self:
        """Scroll the located element into view."""
        await self.browser._command("scrollintoview", selector=self.selector)
        return self

    async def wait(
        self,
        *,
        state: WaitSelectorState = "visible",
        timeout_ms: int | None = None,
    ) -> Self:
        """Wait for the located element to reach a state."""
        await self.browser._command(
            "wait",
            **wait_params(None, selector=self.selector, state=state, timeout_ms=timeout_ms),
        )
        return self

    async def highlight(self) -> Self:
        """Highlight the located element."""
        await self.browser._command("highlight", selector=self.selector)
        return self

    async def tap(self) -> Self:
        """Tap the located element."""
        await self.browser._command("tap", selector=self.selector)
        return self

    async def text(self) -> str:
        """Return text content for the located element."""
        return str((await self.browser._command("gettext", selector=self.selector)).get("text", ""))

    async def inner_text(self) -> str:
        """Return rendered inner text."""
        return str(
            (await self.browser._command("innertext", selector=self.selector)).get("text", "")
        )

    async def inner_html(self) -> str:
        """Return inner HTML."""
        return str(
            (await self.browser._command("innerhtml", selector=self.selector)).get("html", "")
        )

    async def input_value(self) -> str:
        """Return the value of an input-like element."""
        return str(
            (await self.browser._command("inputvalue", selector=self.selector)).get("value", "")
        )

    async def set_value(self, value: str) -> Self:
        """Set the value of an input-like element."""
        await self.browser._command("setvalue", selector=self.selector, value=value)
        return self

    async def attribute(self, name: str) -> str | None:
        """Return one element attribute."""
        value = (
            await self.browser._command(
                "getattribute",
                selector=self.selector,
                attribute=name,
            )
        ).get("value")
        return str(value) if value is not None else None

    async def bounding_box(self) -> BoundingBox | None:
        """Return the element bounding box, if available."""
        return bounding_box_from_data(
            await self.browser._command("boundingbox", selector=self.selector)
        )

    async def count(self) -> int:
        """Return the number of elements matching this selector."""
        return int((await self.browser._command("count", selector=self.selector)).get("count", 0))

    async def styles(self, *properties: str) -> Mapping[str, Any]:
        """Return computed styles for selected properties."""
        return await self.browser._command(
            "styles",
            selector=self.selector,
            properties=list(properties) or optional(None),
        )

    async def is_visible(self) -> bool:
        """Return whether the element is visible."""
        return bool(
            (await self.browser._command("isvisible", selector=self.selector)).get("visible")
        )

    async def is_enabled(self) -> bool:
        """Return whether the element is enabled."""
        return bool(
            (await self.browser._command("isenabled", selector=self.selector)).get("enabled")
        )

    async def is_checked(self) -> bool:
        """Return whether the element is checked."""
        return bool(
            (await self.browser._command("ischecked", selector=self.selector)).get("checked")
        )

    async def screenshot(
        self,
        path: str | Path | None = None,
        *,
        full_page: bool = False,
        annotate: bool = False,
        output_dir: str | Path | None = None,
        format: str = "png",
        quality: int | None = None,
        wait_ms: int = DEFAULT_SCREENSHOT_WAIT_MS,
    ) -> Screenshot:
        """Capture a screenshot scoped to this locator."""
        return await self.browser.capture.screenshot(
            path=path,
            selector=self.selector,
            full_page=full_page,
            annotate=annotate,
            output_dir=output_dir,
            format=format,
            quality=quality,
            wait_ms=wait_ms,
        )


@dataclass(frozen=True, slots=True)
class AsyncSemanticLocator:
    """Async action handle for native `getby*` semantic lookup results."""

    browser: Any
    action: str
    params: Mapping[str, Any]

    async def click(self) -> Self:
        """Click the semantic match."""
        await self.browser._command(self.action, **self.params, subaction="click")
        return self

    async def fill(self, value: str) -> Self:
        """Fill the semantic match."""
        await self.browser._command(self.action, **self.params, subaction="fill", value=value)
        return self

    async def check(self) -> Self:
        """Check the semantic match."""
        await self.browser._command(self.action, **self.params, subaction="check")
        return self

    async def hover(self) -> Self:
        """Hover the semantic match."""
        await self.browser._command(self.action, **self.params, subaction="hover")
        return self

    async def tap(self) -> Self:
        """Tap the semantic match."""
        return await self.click()

    async def type(self, text: str) -> Self:
        """Click the semantic match, then type text."""
        await self.click()
        await self.browser.keyboard.type(text)
        return self

    async def press(self, key: str) -> Self:
        """Click the semantic match, then press a key."""
        await self.click()
        await self.browser.keyboard.press(key)
        return self

    async def text(self) -> str:
        """Return text for the semantic match."""
        data = await self.browser._command(self.action, **self.params, subaction="text")
        return str(data.get("text", ""))


@dataclass(frozen=True, slots=True)
class AsyncTabs:
    """Async tab listing, creation, switching, and closing helpers."""

    browser: AsyncCommandTarget

    async def list(self) -> tuple[TabInfo, ...]:
        """Return open tabs."""
        return tabs_from_data(await self.browser._command("tab_list"))

    async def new(self, url: str | None = None, *, label: str | None = None) -> TabInfo:
        """Open a new tab and return its metadata."""
        return tab_from_data(
            await self.browser._command("tab_new", url=optional(url), label=optional(label))
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

        existing = _tab_with_label(await self.list(), label)
        if existing is None:
            return await self.new(normalized_url, label=label)

        await self.switch(label=label)
        await self.browser._command("navigate", url=normalized_url, waitUntil=wait_until)
        current_tabs = await self.list()
        return _active_tab(current_tabs) or _tab_with_label(current_tabs, label) or existing

    async def switch(
        self,
        *,
        id: str | None = None,
        label: str | None = None,
        index: int | None = None,
    ) -> Mapping[str, Any]:
        """Switch to a tab by id, label, or zero-based index."""
        return await self.browser._command(
            "tab_switch",
            tabId=await self._resolve_selector(id=id, label=label, index=index, required=True),
        )

    async def close(
        self,
        *,
        id: str | None = None,
        label: str | None = None,
        index: int | None = None,
    ) -> Mapping[str, Any]:
        """Close a tab or the current tab."""
        return await self.browser._command(
            "tab_close",
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
            tab = _tab_with_label(await self.list(), label)
            if tab is None:
                raise ValueError(f"no tab with label {label!r}")
            return tab.id
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
        data = await self.browser._command(
            "cookies_get",
            **cookies_get_params(urls, unsafe_export_all=unsafe_export_all),
        )
        return cookies_from_data(data)

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
    ) -> Mapping[str, Any]:
        """Set one cookie or a sequence of cookie dictionaries."""
        return await self.browser._command(
            "cookies_set",
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

    async def clear(self, *, unsafe_clear_all: bool = False) -> Mapping[str, Any]:
        """Clear browser cookies."""
        return await self.browser._command(
            "cookies_clear",
            **cookies_clear_params(unsafe_clear_all=unsafe_clear_all),
        )


@dataclass(frozen=True, slots=True)
class AsyncStorage:
    """Async local and session storage helpers."""

    browser: AsyncCommandTarget

    async def get(self, key: str | None = None, *, area: StorageArea = "local") -> Any:
        """Return one storage value or the whole storage area."""
        data = await self.browser._command("storage_get", **storage_get_params(key, area=area))
        return data.get("value") if key is not None else data.get("data", {})

    async def set(self, key: str, value: str, *, area: StorageArea = "local") -> Mapping[str, Any]:
        """Set one storage value."""
        return await self.browser._command(
            "storage_set", **storage_set_params(key, value, area=area)
        )

    async def clear(self, *, area: StorageArea = "local") -> Mapping[str, Any]:
        """Clear a storage area."""
        return await self.browser._command("storage_clear", **storage_clear_params(area=area))


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
    ) -> Mapping[str, Any]:
        """Register a request route."""
        return await self.browser._command(
            "route",
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

    async def unroute(self, url: str | None = None) -> Mapping[str, Any]:
        """Remove one route or all routes."""
        return await self.browser._command("unroute", url=optional(url))

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
        data = await self.browser._command(
            "requests",
            **requests_params(
                clear=clear,
                url_pattern=url_pattern,
                resource_type=resource_type,
                method=method,
                status=status,
            ),
        )
        return network_requests_from_data(data)

    async def request_detail(self, request_id: str) -> RequestDetail:
        """Return detailed request data for a captured request id."""
        return request_detail_from_data(
            await self.browser._command("request_detail", requestId=request_id)
        )

    async def har_start(self) -> Mapping[str, Any]:
        """Start HAR capture."""
        return await self.browser._command("har_start")

    async def har_stop(self, path: str | Path | None = None) -> Path:
        """Stop HAR capture and return the written file path."""
        data = await self.browser._command("har_stop", path=optional(path_value(path)))
        if "path" not in data:
            raise BrowserError("har_stop", "native response did not include a path", data)
        return Path(str(data["path"]))

    async def credentials(self, username: str, password: str) -> Mapping[str, Any]:
        """Set HTTP authentication credentials."""
        return await self.browser._command("credentials", username=username, password=password)


@dataclass(frozen=True, slots=True)
class AsyncKeyboard:
    """Async keyboard typing, key press, and dispatch helpers."""

    browser: AsyncCommandTarget

    async def type(self, text: str) -> Mapping[str, Any]:
        """Type text with the keyboard."""
        return await self.browser._command("keyboard", subaction="type", text=text)

    async def insert_text(self, text: str) -> Mapping[str, Any]:
        """Insert text without key events when supported."""
        return await self.browser._command("keyboard", subaction="insertText", text=text)

    async def press(self, key: str) -> Mapping[str, Any]:
        """Press a key such as `Enter` or `Meta+K`."""
        return await self.browser._command("press", key=key)

    async def down(
        self, key: str, *, code: str | None = None, text: str | None = None
    ) -> Mapping[str, Any]:
        """Dispatch a key-down event."""
        return await self.dispatch("keyDown", key=key, code=code, text=text)

    async def up(self, key: str, *, code: str | None = None) -> Mapping[str, Any]:
        """Dispatch a key-up event."""
        return await self.dispatch("keyUp", key=key, code=code)

    async def dispatch(
        self,
        event_type: str,
        *,
        key: str | None = None,
        code: str | None = None,
        text: str | None = None,
    ) -> Mapping[str, Any]:
        """Dispatch a low-level keyboard event."""
        return await self.browser._command(
            "keyboard",
            **keyboard_params(event_type, key=key, code=code, text=text),
        )


@dataclass(frozen=True, slots=True)
class AsyncMouse:
    """Async mouse movement, button, wheel, and dispatch helpers."""

    browser: AsyncCommandTarget

    async def move(self, x: float, y: float) -> Mapping[str, Any]:
        """Move the mouse to page coordinates."""
        return await self.browser._command("mousemove", x=x, y=y)

    async def down(self, *, button: MouseButton = "left") -> Mapping[str, Any]:
        """Press a mouse button."""
        return await self.browser._command("mousedown", button=button)

    async def up(self, *, button: MouseButton = "left") -> Mapping[str, Any]:
        """Release a mouse button."""
        return await self.browser._command("mouseup", button=button)

    async def wheel(
        self,
        delta_y: float = 100,
        *,
        delta_x: float = 0,
        x: float = 0,
        y: float = 0,
    ) -> Mapping[str, Any]:
        """Scroll with the mouse wheel."""
        return await self.browser._command(
            "wheel",
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
    ) -> Mapping[str, Any]:
        """Dispatch a low-level mouse event."""
        return await self.browser._command(
            "mouse",
            **mouse_params(event_type, x=x, y=y, button=button, click_count=click_count),
        )


@dataclass(frozen=True, slots=True)
class AsyncRuntime:
    """Async native runtime diagnostics."""

    browser: AsyncCommandTarget

    async def info(self) -> Mapping[str, Any]:
        """Return native session and launch diagnostics."""
        return await self.browser._command("session_info")


@dataclass(frozen=True, slots=True)
class AsyncRestore:
    """Async native restore diagnostics."""

    browser: AsyncCommandTarget

    async def info(self) -> Mapping[str, Any]:
        """Return native restore diagnostics."""
        return await self.browser._command("session_info")


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
        data = await self.browser._command(
            "state_save",
            **state_path_params(path, unsafeExportAll=unsafe_export_all),
        )
        return Path(str(data["path"]))

    async def load(self, path: str | Path, *, unsafe_import_all: bool = False) -> Mapping[str, Any]:
        """Load browser storage state from a file."""
        return await self.browser._command(
            "state_load",
            **state_path_params(path, unsafeImportAll=unsafe_import_all),
        )

    async def list(self) -> Mapping[str, Any]:
        """List saved storage states."""
        return await self.browser._command("state_list")

    async def show(self, path: str | Path) -> Mapping[str, Any]:
        """Show metadata for a saved storage state."""
        return await self.browser._command("state_show", **state_path_params(path))

    async def clear(self, path: str | Path | None = None) -> Mapping[str, Any]:
        """Clear one saved state or all saved states."""
        return await self.browser._command("state_clear", **state_path_params(path))

    async def clean(self, *, days: int = 30) -> Mapping[str, Any]:
        """Delete saved states older than a number of days."""
        return await self.browser._command("state_clean", days=days)

    async def rename(self, path: str | Path, name: str) -> Mapping[str, Any]:
        """Rename a saved storage state."""
        return await self.browser._command("state_rename", **state_path_params(path, name=name))


@dataclass(frozen=True, slots=True)
class AsyncClipboard:
    """Async system clipboard helpers for the active browser context."""

    browser: AsyncCommandTarget

    async def read(self) -> str:
        """Read text from the clipboard."""
        return str((await self.browser._command("clipboard", subAction="read")).get("text", ""))

    async def write(self, text: str) -> Mapping[str, Any]:
        """Write text to the clipboard."""
        return await self.browser._command("clipboard", subAction="write", text=text)

    async def copy(self) -> Mapping[str, Any]:
        """Copy the current selection."""
        return await self.browser._command("clipboard", subAction="copy")

    async def paste(self) -> Mapping[str, Any]:
        """Paste clipboard content."""
        return await self.browser._command("clipboard", subAction="paste")


@dataclass(frozen=True, slots=True)
class AsyncDialogs:
    """Async JavaScript dialog status and response helpers."""

    browser: AsyncCommandTarget

    async def status(self) -> Mapping[str, Any]:
        """Return current dialog status."""
        return await self.browser._command("dialog", response="status")

    async def accept(self, prompt_text: str | None = None) -> Mapping[str, Any]:
        """Accept the active dialog, optionally with prompt text."""
        return await self.browser._command(
            "dialog",
            response="accept",
            promptText=optional(prompt_text),
        )

    async def dismiss(self) -> Mapping[str, Any]:
        """Dismiss the active dialog."""
        return await self.browser._command("dialog", response="dismiss")


@dataclass(frozen=True, slots=True)
class AsyncDownloads:
    """Async download triggering and waiting helpers."""

    browser: AsyncCommandTarget

    async def download(self, selector: str, path: str | Path) -> Path:
        """Click a selector that starts a download and return the path."""
        data = await self.browser._command("download", selector=selector, path=path_value(path))
        return Path(str(data["path"]))

    async def wait(self, path: str | Path | None = None, *, timeout_ms: int | None = None) -> Path:
        """Wait for the next download and return the path."""
        data = await self.browser._command(
            "waitfordownload",
            path=optional(path_value(path)),
            timeout=optional(timeout_ms),
        )
        return Path(str(data["path"]))


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
class AsyncActiveFrame:
    """Async native active-frame selection helpers."""

    browser: Any

    async def select(
        self,
        *,
        selector: str | None = None,
        name: str | None = None,
        url: str | None = None,
    ) -> Mapping[str, Any]:
        """Select the active native frame."""
        return await self.browser._command(
            "frame",
            selector=optional(selector),
            name=optional(name),
            url=optional(url),
        )

    async def main(self) -> Mapping[str, Any]:
        """Select the main native frame."""
        return await self.browser._command("mainframe")


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
        data = await self.browser._command(
            "diff_snapshot",
            baseline=optional(path_value(baseline) if isinstance(baseline, Path) else baseline),
            selector=optional(selector),
            compact=compact,
            maxDepth=optional(max_depth),
        )
        return _snapshot_diff(data)


@dataclass(frozen=True, slots=True)
class AsyncDiagnostics:
    """Async console, error, vitals, and framework diagnostic helpers."""

    browser: AsyncCommandTarget

    async def console(self, *, clear: bool = False) -> tuple[ConsoleMessage, ...]:
        """Return captured console messages."""
        return console_messages_from_data(await self.browser._command("console", clear=clear))

    async def errors(self) -> Mapping[str, Any]:
        """Return captured page errors."""
        return await self.browser._command("errors")

    async def vitals(self) -> Mapping[str, Any]:
        """Return page vitals when supported by the native engine."""
        return await self.browser._command("vitals")

    async def react_tree(self, *, selector: str | None = None) -> Mapping[str, Any]:
        """Return React tree diagnostics, optionally scoped by selector."""
        return await self.browser._command("react_tree", selector=optional(selector))


def _snapshot_diff(data: Mapping[str, Any]) -> SnapshotDiff:
    return snapshot_diff_from_data(data)


async def _wait_before_screenshot(wait_ms: int) -> None:
    validate_screenshot_wait_ms(wait_ms)
    if wait_ms:
        await async_sleep(wait_ms / 1000)
