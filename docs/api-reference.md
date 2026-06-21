# API Reference

The import package is `pyagentbrowser`. A `Browser` owns one native
`agent-browser` session and exposes namespaced helpers over the native command
protocol.

```python
from pyagentbrowser import Browser

with Browser(headless=True, allowed_domains="example.com") as browser:
    browser.page.open("https://example.com")
    page = browser.agent.observe()
    print(page.text)
```

## `Browser(...)`

```python
Browser(
    *,
    headless: bool = True,
    executable_path: str | Path | None = None,
    engine: str | None = None,
    session: str | None = None,
    session_name: str | None = None,
    default_timeout_ms: int | None = 15_000,
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
) -> None
```

Creates a synchronous browser controller. Construction is lazy: the native
browser launches on `launch()`, `connect()`, or the first helper that needs a
page.

`allowed_domains` accepts comma-separated exact hosts and wildcard suffixes such
as `example.com`, `*.example.com`, `localhost`, and `::1`. When set, the SDK
checks raw URL targets, host-qualified URL patterns, cookie targets, and
permission origins before native execution. Storage-state loads are filtered
before import. Storage-state saves and cookie reads are filtered before return
unless the unsafe export option is passed.

`hide_scrollbars=None` leaves the native default and
`AGENT_BROWSER_HIDE_SCROLLBARS` in control. `False` keeps native scrollbars
visible in headless screenshots.

Raises `BrowserError` when a command fails, `ActionConfirmationRequired` when a
policy requires confirmation, and `ValueError` for invalid SDK arguments.

### `allowed_domains`

The allowlist is a Python-side host guard around native commands that can cross
origins. Violations raise `BrowserError` with `code="allowed_domains"`.

| Input | Treatment |
| --- | --- |
| `example.com`, `*.example.com` | Constructor allowlist entries. Wildcard host patterns require a wildcard entry. |
| `https://example.com/path`, `example.com/path` | Raw URL targets are normalized and checked against the host allowlist. |
| `*://example.com/*`, `//example.com/path`, `*//example.com/*` | Host-qualified URL patterns are checked before native execution. |
| `/api`, `**/api`, `*api/message` | Relative URL patterns stay relative and do not name a host. |
| `*.example.com/*` | Requires `allowed_domains="*.example.com"`. `allowed_domains="example.com"` allows exact-host patterns only. |
| `*localhost/path` | Rejected because the leading wildcard can match outside the host. Use `*://localhost/...` or `//localhost/...`. |
| `[::1]/path`, `//[::1]/path` | Bracketed IPv6 hosts compare against the unbracketed allowlist host, such as `::1`. |

## `AsyncBrowser(...)`

`AsyncBrowser` accepts the same constructor options and exposes the same
namespaces with awaitable methods. Native commands run on one owner thread so
browser state remains ordered while the event loop stays responsive.

```python
from pyagentbrowser import AsyncBrowser

async with AsyncBrowser(headless=True) as browser:
    await browser.page.open("https://example.com")
    print(await browser.page.title())
```

## Core Methods

### `browser.command(action, **params)`

Runs one native command and returns object-shaped response data.
`Browser.command` is the raw native command surface. The SDK still applies
confirmation handling, allowlist checks, response validation, and lifecycle
bookkeeping.

```python
browser.command("dispatch", selector="#save", event="click")
```

### `browser.try_command(action, **params)`

Runs one native command and returns `BrowserResponse` without raising for a
native unsuccessful response. Local validation errors still raise before a
command reaches native code.

### `browser.execute_raw(action, **params)`

Runs one native command and returns raw response data without requiring an
object payload. Use it for native actions whose `data` is a scalar, array, or
`null`.

### `browser.launch(...)`

Launches or attaches the native browser using constructor defaults plus any
method overrides. Returns native launch response data. `connect()` is an alias
for an explicit launch or attach handshake that does not navigate.

### `browser.close()`

Closes the native browser session and any active CDP controller. Inside a
context manager, close errors surface only when the body completed without its
own exception. `AsyncBrowser.aclose()` closes the browser and stops the async
native worker.

### `browser.confirm(confirmation=None)` and `browser.deny(confirmation=None)`

Resolve a pending `ActionConfirmationRequired`. Passing `None` uses the last
pending confirmation tracked by the browser.

### `browser.is_launched`

Reports whether this Python controller has completed a launch or attach action
that is still considered open.

### `browser.observe(...)`, `browser.snapshot(...)`, and `browser.diff_snapshot(...)`

`observe(*, selector=None, interactive=True, compact=False, max_depth=None,
urls=False)` returns a browser-bound `AgentSnapshot`.

`snapshot(*, selector=None, interactive=False, compact=False, max_depth=None,
urls=False)` returns a raw `Snapshot`.

`diff_snapshot(baseline=None, *, selector=None, compact=False, max_depth=None)`
returns `SnapshotDiff`. `baseline` may be snapshot text, a path, a `Snapshot`,
or `None`.

### Browser Environment Methods

| Method | Behavior | Returns and raises |
| --- | --- | --- |
| `set_viewport(width, height, *, device_scale_factor=1.0, mobile=False)` | Sets viewport emulation in CSS pixels. | Returns native viewport data. |
| `set_device(name)` | Applies a named native device preset. | Returns native device data. |
| `set_headers(headers)` | Sets extra HTTP headers for subsequent requests. | Returns native header data. |
| `set_offline(enabled=True)` | Enables or disables offline network emulation. | Returns native offline data. |
| `set_user_agent(user_agent)` | Sets the browser user-agent string. | Returns native user-agent data. |
| `set_media(*, media=None, color_scheme=None, reduced_motion=None, features=None)` | Sets CSS media emulation. | Returns native media data. |
| `set_timezone(timezone_id)` | Sets browser timezone emulation, for example `Europe/Vienna`. | Returns native timezone data. |
| `set_locale(locale)` | Sets browser locale emulation, for example `en-US`. | Returns native locale data. |
| `set_geolocation(latitude, longitude, *, accuracy=None)` | Sets geolocation coordinates. | Returns native geolocation data. |
| `set_permissions(permissions, *, origin=None)` | Grants browser permissions, optionally scoped to an origin. The origin is checked against `allowed_domains` when configured. | Returns native permission data. |
| `bring_to_front()` | Brings the browser window to the foreground. | Returns native foregrounding data. |

## Namespaces

The method tables below use synchronous `Browser` namespace names. `AsyncBrowser`
keeps the same names and arguments, with awaitable methods and async models where
listed.

## Namespace methods

### `browser.page`

| Method | Behavior | Returns and raises |
| --- | --- | --- |
| `open(url, *, wait_until="load")` | Launches the browser if needed and navigates the active page. Host-like values are normalized to `https://...`. | Returns native navigation data. Raises `BrowserError` for native failures and allowlist violations. |
| `title()` | Reads the active page title. | Returns `str`. |
| `url()` | Reads the active page URL. | Returns `str`. |
| `content()` | Reads the active page HTML. | Returns `str`. |
| `set_content(html)` | Replaces the active page document. The browser must already be launched or attached. | Returns native set-content data. |
| `evaluate(script)` | Evaluates JavaScript in the active page context through the native command path. | Returns the native `result` value. |
| `ready(*, timeout_ms=None, min_text_length=1)` | Waits until the body contains at least `min_text_length` characters. | Returns `None`. Raises `ValueError` for negative `min_text_length`. |
| `wait_for_text(text, *, timeout_ms=None)` | Waits for visible text. | Returns `None`. Raises `BrowserError` on timeout. |
| `wait_for_selector(selector, *, state="visible", timeout_ms=None)` | Waits for selector state `attached`, `detached`, `hidden`, or `visible`. | Returns `None`. Raises `BrowserError` on timeout. |
| `wait_for_url(pattern, *, timeout_ms=None)` | Waits for the active URL to match a native URL pattern. With `allowed_domains`, host-qualified patterns are checked before native execution while relative wildcard patterns stay relative. | Returns `None`. Raises `BrowserError` on timeout or allowlist violations. |
| `wait_for_function(predicate, *, timeout_ms=None)` | Waits for a JavaScript predicate to become truthy. | Returns `None`. Raises `BrowserError` on timeout. |
| `wait_for_load_state(state="load")` | Waits for load state `load`, `domcontentloaded`, `networkidle`, or `none`. | Returns `None`. |
| `back()`, `forward()`, `reload()` | Runs browser history navigation. | Returns native navigation data. Invalidates cached CDP page handles. |

### `browser.agent`, `browser.find`, and locators

| Method | Behavior | Returns and raises |
| --- | --- | --- |
| `agent.observe(*, selector=None, interactive=True, compact=False, max_depth=None, urls=False)` | Captures an accessibility snapshot and binds native refs to this browser. | Returns `AgentSnapshot`. |
| `agent.ref(ref_id)` | Creates a locator from a snapshot ref id such as `r1` or `@r1`. | Returns `Locator`. The ref must still be valid in the current page. |
| `find.css(selector)`, `find.xpath(expression)`, `find.ref(ref_id)` | Creates a locator for CSS, XPath, or snapshot ref selectors. | Returns `Locator`. XPath values accept either raw XPath or `xpath=...`. |
| `find.role(role, *, name=None, exact=False)` | Creates a semantic locator for an accessible role. | Returns `SemanticLocator`. |
| `find.text(text, *, exact=False)`, `find.label(label, *, exact=False)`, `find.placeholder(placeholder, *, exact=False)` | Creates semantic locators for visible text, label text, or placeholder text. | Returns `SemanticLocator`. |
| `find.alt_text(text, *, exact=False)`, `find.title(text, *, exact=False)`, `find.test_id(test_id)` | Creates semantic locators for image alt text, title text, or test id. | Returns `SemanticLocator`. |
| `locator.nth(index)`, `first()` | Narrows a selector to one native match. | Returns `SemanticLocator`. |
| `locator.click(*, button="left", click_count=1)`, `fill(value)`, `select(value)`, `check()`, `uncheck()`, `type(text)`, `press(key)`, `hover()`, `focus()`, `clear()`, `select_all()`, `scroll_into_view()`, `wait(*, state="visible", timeout_ms=None)`, `highlight()`, `tap()`, `set_value(value)` | Runs element actions through the native selector. | Returns the locator for chaining. Raises `BrowserError` and `StaleAgentRefError` for stale refs. |
| `locator.text()`, `inner_text()`, `inner_html()`, `input_value()`, `attribute(name)`, `bounding_box()`, `count()`, `styles(*properties)`, `is_visible()`, `is_enabled()`, `is_checked()` | Reads element state through native commands. | Returns typed Python values such as `str`, `bool`, `int`, `BoundingBox`, or a mapping. |
| `locator.screenshot(path=None, *, full_page=False, annotate=False, output_dir=None, format="png", quality=None, wait_ms=100)` | Captures the located element. | Returns `Screenshot`. Raises `ValueError` for negative `wait_ms`. |
| `AgentRef.click_and_observe(..., wait_for_text=None, wait_for_url=None, wait_for_load_state=None, compact=True)` | Runs the action, waits for the requested condition, then captures before and after evidence. | Returns `ActionEvidence`. |
| `AgentRef.fill_and_observe(value, ..., compact=True)` | Fills the ref and captures before and after evidence. | Returns `ActionEvidence`. |

### `browser.capture`

| Method | Behavior | Returns and raises |
| --- | --- | --- |
| `screenshot(path=None, *, selector=None, full_page=False, annotate=False, output_dir=None, format="png", quality=None, wait_ms=100)` | Waits `wait_ms`, captures the page or selector, and parses annotation metadata when requested. | Returns `Screenshot`. Raises `ValueError` when `wait_ms < 0`. `Screenshot.pil()` raises `ImportError` without the `images` extra. |
| `pdf(path=None, *, print_background=True, landscape=False, prefer_css_page_size=False)` | Prints the current page to PDF. | Returns `Path` for the written PDF. |

### `browser.tabs`

| Method | Behavior | Returns and raises |
| --- | --- | --- |
| `list()` | Reads native tab metadata. | Returns `tuple[TabInfo, ...]`. |
| `new(url=None, *, label=None)` | Opens a new tab, optionally with a URL and label. URL targets are checked against `allowed_domains`. | Returns `TabInfo`. |
| `open(url, *, label=None, wait_until="load")` | Reuses an existing labelled tab when one exists, otherwise creates it. Then navigates to `url`. | Returns `TabInfo`. Invalidates cached CDP page handles. |
| `switch(tab)` | Switches to a tab id, label, or numeric tab reference. | Returns native switch data. |
| `close(tab=None)` | Closes one tab or the active tab. | Returns native close data. Invalidates cached CDP page handles. |

### `browser.cookies`, `browser.storage`, and `browser.state`

| Method | Behavior | Returns and raises |
| --- | --- | --- |
| `cookies.get(urls=None, *, unsafe_export_all=False)` | Reads cookies for explicit URLs or the current browser context. With `allowed_domains`, returned cookies are filtered to allowed domains unless `unsafe_export_all=True`. Explicit URL targets are checked before native execution. | Returns `tuple[Cookie, ...]`. |
| `cookies.set(name=None, value=None, *, cookies=None, url=None, domain=None, path=None, expires=None, http_only=None, secure=None, same_site=None)` | Sets one cookie or a sequence of cookie dictionaries. With `allowed_domains`, every cookie must provide an allowed `url` or `domain`. | Returns native cookie-set data. Raises `ValueError` when neither `cookies` nor `name` plus `value` is provided. |
| `cookies.clear(*, unsafe_clear_all=False)` | Clears browser cookies. With `allowed_domains`, the SDK rejects this command unless `unsafe_clear_all=True` because the native clear operation is not domain-scoped. | Returns native clear data. |
| `storage.get(key=None, *, area="local")` | Reads one local or session storage key, or the whole area when `key` is omitted. | Returns the stored value or `dict`. |
| `storage.set(key, value, *, area="local")` | Sets one local or session storage value. | Returns native storage data. |
| `storage.clear(*, area="local")` | Clears one storage area. | Returns native clear data. |
| `state.save(path=None, *, unsafe_export_all=False)` | Saves browser storage state. With `allowed_domains`, saved cookies and origins are filtered before the method returns unless `unsafe_export_all=True`. | Returns `Path`. Raises `BrowserError` when encrypted state cannot be filtered. |
| `state.load(path, *, unsafe_import_all=False)` | Loads browser storage state. With `allowed_domains`, the SDK filters cookies and origins into a temporary file before native import unless `unsafe_import_all=True`. | Returns native load data. Raises `BrowserError` for unreadable or invalid state files. |
| `state.list()`, `show(path)`, `clear(path=None)`, `clean(*, days=30)`, `rename(path, name)` | Manages native saved-state files. | Returns native state-management data. |

### `browser.network`

| Method | Behavior | Returns and raises |
| --- | --- | --- |
| `route(url, *, abort=False, response=None, status=None, body=None, content_type=None, headers=None, resource_type=None, resource_types=None)` | Registers a native request route. Pass either a `RouteResponse`, a mapping, or inline response fields. With `allowed_domains`, host-qualified URL patterns are checked before native execution. | Returns native route data. Raises `BrowserError` for allowlist violations. |
| `unroute(url=None)` | Removes one route or all routes. With `allowed_domains`, host-qualified URL patterns are checked before native execution. | Returns native unroute data. Raises `BrowserError` for allowlist violations. |
| `requests(*, clear=False, url_pattern=None, resource_type=None, method=None, status=None)` | Reads captured network requests and optionally clears the buffer. | Returns `tuple[NetworkRequest, ...]`. |
| `request_detail(request_id)` | Reads detailed request and response metadata. | Returns `RequestDetail`. |
| `har_start()` | Starts HAR capture. | Returns native HAR data. |
| `har_stop(path=None)` | Stops HAR capture and writes the HAR file. | Returns `Path`. Raises `BrowserError` when native response omits a path. |
| `credentials(username, password)` | Sets HTTP authentication credentials. | Returns native credential data. |

### `browser.scripts`, `browser.frames`, and `browser.cdp`

| Method | Behavior | Returns and raises |
| --- | --- | --- |
| `scripts.add_init(script=None, *, path=None)` | Adds a script that runs before future page scripts. Launches the browser if needed. | Returns the native script identifier. Raises `ValueError` unless exactly one source is provided. |
| `scripts.remove_init(identifier)` | Removes a registered init script. | Returns native remove data. |
| `scripts.add(script=None, *, url=None)` | Injects JavaScript into the current page from inline source or URL. URL targets are checked against `allowed_domains`. | Returns native add data. Raises `ValueError` unless exactly one source is provided. |
| `scripts.add_style(content=None, *, url=None)` | Injects CSS into the current page from inline content or URL. URL targets are checked against `allowed_domains`. | Returns native add data. Raises `ValueError` unless exactly one source is provided. |
| `frames.list()` | Lists frames for the active CDP page target. | Returns a sequence of `Frame` objects. Requires the `cdp` extra. |
| `frames.get(selector=None, *, name=None, url=None)` | Resolves one frame by selector, name, or URL. | Returns `Frame`. Raises CDP frame resolution errors. |
| `frames.switch(selector=None, *, name=None, url=None)` | Switches the active native frame. With `allowed_domains`, `url` patterns are checked before native execution. Protocol-relative and wildcard-prefixed protocol-relative patterns are host-qualified. | Returns native frame data. Raises `BrowserError` with `code="allowed_domains"` for allowlist violations. |
| `frames.main()` | Switches back to the main frame. | Returns native main-frame data. |
| `cdp.evaluate(script, *, frame=None, extension_id=None, context=None, await_promise=True, return_by_value=True)` | Evaluates JavaScript through CDP in a frame or execution context. | Returns the evaluated value or remote object data. Requires the `cdp` extra. |
| `cdp.target(*, label=None, url=None, target_id=None)` | Resolves a CDP target selected by SDK tab label, URL, or CDP target id. Label lookup uses labels assigned by `browser.tabs.new(...)` or `browser.tabs.open(...)`. | Returns a CDP target handle. Raises target resolution errors. |

### Input, dialogs, downloads, diffs, and diagnostics

| Method | Behavior | Returns and raises |
| --- | --- | --- |
| `keyboard.type(text)`, `insert_text(text)`, `press(key)`, `down(key, *, code=None, text=None)`, `up(key, *, code=None)`, `dispatch(event_type, *, key=None, code=None, text=None)` | Sends keyboard input through native commands. | Returns native keyboard data. |
| `mouse.move(x, y)`, `down(*, button="left")`, `up(*, button="left")`, `wheel(delta_y=100, *, delta_x=0, x=0, y=0)`, `dispatch(event_type, *, x=0, y=0, button="none", click_count=0)` | Sends mouse input through native commands. | Returns native mouse data. |
| `dialogs.status()`, `accept(prompt_text=None)`, `dismiss()` | Reads or resolves the active JavaScript dialog. | Returns native dialog data. |
| `downloads.download(selector, path)` | Clicks a selector that starts a download. | Returns `Path`. |
| `downloads.wait(path=None, *, timeout_ms=None)` | Waits for the next download. | Returns `Path`. |
| `clipboard.read()`, `write(text)`, `copy()`, `paste()` | Reads, writes, or operates on the system clipboard through the browser context. | Returns `str` for `read()` and native data for write/copy/paste. |
| `diff.snapshot(baseline=None, *, selector=None, compact=False, max_depth=None)` | Compares the current snapshot with a baseline file or snapshot text. | Returns `SnapshotDiff`. |
| `diagnostics.console(*, clear=False)`, `errors()`, `vitals()`, `react_tree(*, selector=None)` | Reads console entries, page errors, vitals, or React tree diagnostics. | Returns typed console messages or native diagnostic mappings. |

## Default Session

```python
import pyagentbrowser as ab

ab.configure(headless=True, allowed_domains="*.example.com")
ab.page.open("example.com")
print(ab.page.title())
ab.close()
```

### `pyagentbrowser.configure(force=False, **options)`

Replaces the process-local default browser configuration and returns the new
default `Browser`. Options are the `Browser(...)` constructor options.
`cdp_port`, `cdp_url`, and `auto_connect=True` connect immediately so tab,
state, and diagnostic helpers can run before navigation.

`force=True` discards the previous default browser reference even if native
close fails.

### `default_browser()`, `close(force=False)`, and `reset(force=False)`

`default_browser()` returns the process-local browser, creating it on first use.
`close()` closes and clears the current handle while keeping configured
defaults. `reset()` closes the handle and clears configured defaults.

The package root exposes proxies for every synchronous namespace: `page`,
`agent`, `capture`, `cdp`, `clipboard`, `cookies`, `dialogs`, `diagnostics`,
`diff`, `downloads`, `find`, `frames`, `keyboard`, `mouse`, `network`,
`scripts`, `state`, `storage`, and `tabs`.

## Models And Errors

The package root exports frozen, slot-backed dataclasses for stable SDK return
values. Each model keeps `raw` native data when the native response contains
fields outside the typed SDK model.

### Error Types

| Type | Contract |
| --- | --- |
| `AgentBrowserError` | Base class for SDK-owned exceptions. Catch this when native browser failures, CDP failures, confirmation failures, and stale ref failures should share one handler. |
| `BrowserError(action, message, response, *, code=None)` | Raised when native execution returns an unsuccessful response or when a Python preflight check rejects the command. Exposes `action: str`, `response: dict[str, Any]`, and `code: str | None`. |
| `ActionConfirmationRequired(action, data, response)` | Raised when a native policy requires approval before execution. Exposes `confirmation_id: str | None` and `data: dict[str, Any]`. Pass the exception, its id, or nothing to `browser.confirm(...)` or `browser.deny(...)`. |
| `StaleAgentRefError(ref, error)` | Raised when an `AgentRef` action targets a ref that no longer exists in the current page. Exposes `ref: AgentRef` and `refresh(**criteria) -> AgentRef`. |
| `AsyncStaleAgentRefError(ref, error)` | Async equivalent of `StaleAgentRefError`. Exposes `ref: AsyncAgentRef` and `await refresh(**criteria)`. |
| `CDPError` | Base class for Python-owned CDP errors. CDP helpers require the `cdp` extra and raise these errors before wrapping them in `BrowserError`. |
| `CDPProtocolError(method, error)` | Raised when CDP returns an error response. Exposes `method: str` and `error: object`. |
| `CDPTimeoutError(method, timeout)` | Raised when a CDP request does not receive a response before its timeout. Exposes `method: str` and `timeout: float | None`. |
| `CDPEvaluationError(details)` | Raised when JavaScript evaluation throws in the target context. Exposes `details: dict[str, Any]`. |
| `CDPStaleObjectError` | Raised when a cached `Frame` or `ExecutionContext` is used after navigation or target replacement. Take a fresh handle through `browser.frames` or `browser.cdp.target(...)`. |
| `CDPFrameNotFoundError`, `CDPFrameAmbiguityError` | Raised when frame lookup finds zero or multiple matches for selector, name, or URL criteria. |
| `CDPContextNotFoundError`, `CDPContextAmbiguityError` | Raised when execution-context lookup finds zero or multiple matches for frame, extension id, or predicate criteria. |
| `CDPTargetNotFoundError`, `CDPTargetAmbiguityError` | Raised when target lookup finds zero or multiple browser targets for label, URL, or target id criteria. |

### Configuration Models

| Type | Fields and behavior |
| --- | --- |
| `DashboardOptions(port=None, cli_version=None)` | Enables the upstream dashboard when passed as `dashboard=...`. `port` accepts `0` through `65535` and `0` requests an ephemeral port. `cli_version` must be non-empty when provided. |
| `ProxyConfig(server, bypass=None, username=None, password=None)` | Browser proxy configuration accepted by `Browser(proxy=...)` and `browser.launch(proxy=...)`. `as_command_value()` serializes only populated fields. |
| `RouteResponse(status=None, body=None, content_type=None, headers=None)` | Static route response accepted by `browser.network.route(response=...)`. `headers` is a mapping of response header names to strings. `as_command_value()` serializes `content_type` as `contentType` for native execution. |

### Response And Snapshot Models

| Type | Fields and methods |
| --- | --- |
| `BrowserResponse(id, action, success, data, raw, warning=None)` | Native response envelope returned by `try_command()`. `data` is the unwrapped native payload and `raw` is the full response mapping. |
| `Snapshot(text, origin, refs, raw)` | Accessibility snapshot returned by lower-level snapshot helpers. `refs` maps ref ids to role/name metadata. `ref(ref_id)` accepts `r1` and `@r1`. `find_refs(role=None, name=None, contains=None, exact=False)` returns matching `SnapshotRef` values. |
| `SnapshotRef(id, role, name, raw)` | One accessibility ref. `.selector` returns the native selector form such as `@r1`. |
| `AgentSnapshot(browser, snapshot)` | Browser-bound snapshot returned by `browser.agent.observe(...)`. Exposes `text`, `origin`, `raw`, and `refs`. `ref(ref_id)` returns `AgentRef`. `find(...)` returns one ref and raises `LookupError` on zero matches or strict multiple matches. `find_all(...)` returns all matches. |
| `AgentRef(browser, snapshot_ref, snapshot=None)` | Browser-bound ref with `id`, `selector`, `role`, `name`, and `raw` properties. Element actions return the same ref for chaining. Read methods return typed values. `refresh(...)` re-finds the ref in a fresh snapshot. |
| `AsyncAgentSnapshot`, `AsyncAgentRef` | Async equivalents of `AgentSnapshot` and `AgentRef`. Methods that touch the browser are awaitable. |
| `SnapshotDiff(text, additions, removals, unchanged, changed, raw)` | Parsed snapshot diff returned by `browser.diff.snapshot(...)` and evidence helpers. `changed` is true when additions or removals were reported. |
| `ActionEvidence(action, target, before, after, diff)` | Before/after evidence returned by `AgentRef.click_and_observe(...)` and `fill_and_observe(...)`. `before` and `after` are bound agent snapshots. |

### Page, Network, And Capture Models

| Type | Fields and methods |
| --- | --- |
| `Screenshot(path, format, annotations, raw)` | Screenshot file metadata returned by `browser.capture.screenshot(...)` and locator screenshots. `image` lazily loads a Pillow image. `pil(mode=None)` returns a Pillow image and raises `ImportError` unless Pillow is installed. `bytes()` reads file bytes. `save(path)` copies the file and returns a new `Screenshot`. `marimo(...)` returns a `marimo.image` view and raises `ImportError` unless marimo is installed. |
| `ScreenshotAnnotation(ref, number, role, name, box, raw)` | One interactable element annotation from an annotated screenshot. `box` is a `ScreenshotBox`. |
| `ScreenshotBox(x, y, width, height, raw)` | Annotation rectangle in screenshot pixels. |
| `BoundingBox(x, y, width, height, raw)` | Element rectangle in CSS pixels, returned by locator bounding-box helpers. |
| `TabInfo(id, url, title="", label=None, active=False, raw={})` | Browser tab metadata returned by `browser.tabs.list()`, `new()`, and `open()`. `label` is the SDK tab label when one was assigned. `raw` preserves native fields such as `targetId` from tab-list records. |
| `Cookie(name, value, domain=None, path=None, expires=None, http_only=None, secure=None, same_site=None, raw={})` | Cookie metadata returned by `browser.cookies.get(...)`. `expires` is the native expiry timestamp when available. |
| `ConsoleMessage(type, text, level=None, url=None, line=None, column=None, raw={})` | Browser console entry returned by `browser.diagnostics.console(...)`. |
| `NetworkRequest(id, url, method="", resource_type="", status=None, raw={})` | Captured request summary returned by `browser.network.requests(...)`. |
| `RequestDetail(id, url="", method="", status=None, request_headers={}, response_headers={}, body=None, raw={})` | Detailed request and response metadata returned by `browser.network.request_detail(...)`. Header mappings use native header names. |

### CDP Models

| Type | Fields and methods |
| --- | --- |
| `Frame(id, name, url, session_id, ...)` | Synchronous CDP frame handle returned by `browser.frames.list()`, `browser.frames.get(...)`, and target helpers. `contexts(extension_id=None, predicate=None)` returns execution contexts. `context(...)` returns one context. `evaluate(script, *, extension_id=None, await_promise=True, return_by_value=True)` evaluates JavaScript in the frame. Cached frame handles become stale after navigation or target replacement. |
| `ExecutionContext(id, unique_id, frame_id, origin, name, type, is_default, ...)` | Synchronous JavaScript execution context. `evaluate(script, *, await_promise=True, return_by_value=True)` evaluates JavaScript in this context. Cached context handles become stale after navigation or target replacement. |
| `AsyncFrame`, `AsyncExecutionContext` | Async equivalents of `Frame` and `ExecutionContext`. Browser-touching methods are awaitable and keep the same arguments. |

## Versions

`pyagentbrowser.__version__` is the Python package version.
`pyagentbrowser.__agent_browser_version__` and
`pyagentbrowser.__upstream_version__` report the upstream native engine version
compiled into the extension. `pyagentbrowser.__agent_browser_commit__` and
`pyagentbrowser.__upstream_commit__` report the short upstream commit pinned for
the package build. `DashboardOptions(cli_version=...)` sets the external
dashboard CLI version expected by the SDK-owned observable session.

## Skills

`pyagentbrowser.skills` exposes upstream skill data embedded in the native
extension. Public functions are `available`, `list`, `get`, `parts`, `part`,
`read`, and `markdown`. `Skill`, `SkillPart`, and `SkillFile` are exported from
the package root.
