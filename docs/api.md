# API reference

The distribution is named `pyagentbrowser`. Import the public API from `agentbrowser`.

```python
from agentbrowser import Browser, SessionOptions, Snapshot, Wait
```

`AsyncBrowser`, `AsyncSnapshot`, `AsyncRef`, `AsyncQuery`, and `AsyncPendingAction` mirror their synchronous counterparts with awaitable operations.

## Browser

### Construction

| API | Contract |
| --- | --- |
| `Browser.launch(options=None, *, session=None) -> Browser` | Starts a local browser and returns an active controller. |
| `Browser.attach(target, *, launch=None, session=None) -> Browser` | Connects to one CDP target and returns an active controller. |
| `Browser(*, session=None) -> Browser` | Creates a lazy controller. The first browser-dependent command starts the configured local browser. An explicit-URL `read()` completes through HTTP and leaves browser startup deferred. |
| `AsyncBrowser.launch(...) -> AsyncBrowser` | Awaitable local launch. |
| `AsyncBrowser.attach(...) -> AsyncBrowser` | Awaitable CDP attachment. |

`Browser.launch()` raises `BrowserInstallError` when it cannot prepare a local browser and `BrowserError` when native launch fails. `Browser.attach()` accepts a `CDPTarget` with exactly one port or URL.

### Lifecycle

`Browser.close() -> CloseResult` is idempotent and terminal. Repeated calls return
the same result. `CloseResult` reports `restore_status`, `save_status`, the
optional `state_path`, and the raw native close data. A restore persistence
failure completes cleanup, then raises `RestoreSaveError` with the terminal
result on `error.result`.

`browser.closed` reports terminal state. `browser.is_launched` reports the
native browser lifecycle observed by this controller. Commands after close
raise `RuntimeError`.

`AsyncBrowser.close(*, timeout=5.0) -> CloseResult` is single-flight. Concurrent
and repeated callers observe the same result or terminal error. Queued calls
receive `RuntimeError`. A browser shutdown timeout raises `TimeoutError`. A
worker that remains alive after the join raises `RuntimeError`.

Both browser types support context managers.

### Browser installation

`ensure_installed(*, progress=True) -> InstallResult` finds a configured, cached, or system browser and prepares Chrome for Testing when needed. `progress=True` lets the native installer write progress to the terminal.

`InstallResult` exposes `executable_path`, optional `version`, `source`, and `installed`. `source` is `"environment"`, `"cache"`, `"system"`, or `"download"`. Installation failures raise `BrowserInstallError`.

### Active-page methods

| Method | Returns | Behavior |
| --- | --- | --- |
| `open(url, *, wait_until="load")` | `Browser` | Normalizes a host-like URL, starts the browser when needed, and navigates. |
| `observe(spec=None)` | `Snapshot` | Captures an accessibility snapshot and binds its refs to this browser. |
| `read(url=None, *, mode=None, filter=None, timeout_ms=None, headers=None, allowed_domains=None)` | `ReadResult` | Reads an explicit URL or the rendered active tab. |
| `title()` | `str` | Returns the active document title. |
| `url()` | `str` | Returns the active document URL. |
| `content()` | `str` | Returns the active document HTML. |
| `evaluate(script)` | JSON-compatible value | Evaluates JavaScript through the native engine. |
| `wait_for_text(text, *, timeout_ms=None)` | `None` | Waits for page text. |
| `wait_for_url(url, *, timeout_ms=None)` | `None` | Waits for a native URL pattern. |
| `wait_for_load(state="load")` | `None` | Waits for a load state. |
| `activate()` | `Browser` | Brings the browser window to the foreground. |

The `browser.page` namespace contains the full page surface, including history navigation, document replacement, selector waits, function waits, and readiness checks.

## Configuration

### `LaunchOptions`

`LaunchOptions` is a frozen dataclass passed to `Browser.launch()` or `AsyncBrowser.launch()`.

| Field | Default | Contract |
| --- | --- | --- |
| `headless` | `True` | Runs the browser headlessly. |
| `executable_path` | `None` | Selects a browser executable. |
| `engine` | `None` | Selects a native engine. |
| `profile` | `None` | Uses a browser profile path. |
| `storage_state` | `None` | Loads storage state during launch. |
| `extensions` | `()` | Loads extension paths. Pass a sequence. |
| `proxy` | `None` | Accepts a URL, `ProxyConfig`, or proxy mapping. |
| `provider` | `None` | Selects a native browser provider. |
| `color_scheme` | `None` | Sets the preferred color scheme. |
| `hide_scrollbars` | `None` | Controls native scrollbar visibility. |
| `webgpu` | `None` | Inherits the native setting. `True` enables the WebGPU preset for a local browser launch. `False` overrides `AGENT_BROWSER_WEBGPU`. |
| `no_xvfb` | `None` | Inherits the native setting. `True` disables automatic Xvfb startup for local headed launches on displayless Linux hosts. `False` overrides `AGENT_BROWSER_NO_XVFB`. |
| `args` | `()` | Adds browser arguments. Pass a sequence. |
| `allow_file_access` | `False` | Permits file URL access. |
| `ignore_https_errors` | `False` | Continues through certificate errors. |
| `user_agent` | `None` | Sets the launch user agent. |
| `download_path` | `None` | Sets the default download directory. |

Scalar strings raise `TypeError` for `extensions` and `args`.
`Browser.attach()` and provider launches raise `ValueError` when WebGPU is enabled. Pass `webgpu=False` to override `AGENT_BROWSER_WEBGPU` for those connection modes.

### `SessionOptions`

`SessionOptions` configures one native session.

| Field | Default | Contract |
| --- | --- | --- |
| `session_id` | `None` | Names the native session. |
| `restore` | `None` | Configures keyed restore persistence. |
| `namespace` | `None` | Separates native socket and session state. |
| `timeout` | `15.0` | Sets the default timeout in seconds. `None` disables it. |
| `allowed_domains` | `()` | Restricts exact hosts and wildcard suffixes. Pass a sequence. |
| `action_policy` | `None` | Loads an allow, deny, and confirm policy file. |
| `confirm_actions` | `()` | Requests confirmation for named native actions. Pass a sequence. |
| `auto_dialogs` | `True` | Enables automatic JavaScript dialog handling. |
| `dashboard` | `None` | Configures dashboard observability before startup. |

Empty domain and action entries raise `ValueError`. Scalar strings raise `TypeError` for `allowed_domains` and `confirm_actions`.

### Session IDs

`session_id(*, scope="worktree", prefix=None, path=None) -> SessionId` derives a stable identifier from a worktree, current directory, or Git root. `SessionId` exposes `session`, `scope`, `path`, and `hash`. Converting it to `str` returns the session string accepted by `SessionOptions.session_id`.

### `CDPTarget`

`CDPTarget(url=None, port=None, auto_connect=True)` selects an existing browser. Pass exactly one URL or port. Ports must be between 1 and 65535.

### `RestoreOptions`

`RestoreOptions(key, save=None, autosave_interval_ms=None, check_url=None, check_text=None, check_fn=None)` configures restore identity, save policy, persistence cadence, and optional restore validation.

`key` accepts letters, numbers, hyphens, and underscores. `save` accepts `"auto"`, `"always"`, or `"never"`. `autosave_interval_ms` accepts non-boolean integers from `0` through `18446744073709551615`.

### `DashboardOptions`

`DashboardOptions(port=None, cli_version=None)` configures the native dashboard stream. Port `0` requests an ephemeral port.

## Snapshots and refs

### `SnapshotSpec`

`SnapshotSpec(selector=None, interactive=True, compact=False, max_depth=None, urls=False)` defines a reproducible accessibility capture.

### `Snapshot`

| Member | Contract |
| --- | --- |
| `text` | Human-readable accessibility tree. |
| `origin` | Page URL reported by the native engine. |
| `spec` | `SnapshotSpec` reused by refreshes and ref actions. |
| `refs` | Mapping of ref ids to bound `Ref` objects. |
| `raw` | Native snapshot response mapping. |
| `ref(ref_id)` | Resolves an id such as `e1` or `@e1`. |
| `one(*, role=None, name=None, contains=None, exact=False)` | Returns one matching ref. Raises `LookupError` for zero or several matches. |
| `all(...)` | Returns every matching ref as a tuple. |
| `refresh()` | Captures the same snapshot specification again. |
| `diff()` | Compares this snapshot with the active page and returns `SnapshotDiff`. |

### `Ref`

`Ref` exposes `id`, `selector`, `role`, `name`, `raw`, `snapshot`, and `browser`.

Mutation methods return `ActionResult`:

- `click(*, button="left", click_count=1, new_tab=False, wait=None)`
- `fill(value, *, wait=None)`
- `type(text, *, wait=None)`
- `select(value, *, wait=None)`
- `check(*, wait=None)` and `uncheck(*, wait=None)`
- `hover(*, wait=None)`, `focus(*, wait=None)`, and `tap(*, wait=None)`
- `clear(*, wait=None)` and `scroll_into_view(*, wait=None)`

Read methods are `text()`, `inner_text()`, `input_value()`, `attribute(name)`, `is_visible()`, `is_enabled()`, and `is_checked()`.

`refresh(*, role=None, name=None, contains=None, exact=True)` captures a new snapshot and resolves the ref again. Native stale-ref failures raise `StaleRefError` or `AsyncStaleRefError`.

### `ActionResult`

`ActionResult(action, target, before, after, diff)` records a completed ref mutation and its page transition.

`ActionTransitionError` means the mutation completed and a later wait or evidence stage failed. Its `action`, `target`, `stage`, `before`, optional `after`, and `cause` fields describe the partial transition.

### `Wait`

| Constructor | Contract |
| --- | --- |
| `Wait.text(text, *, timeout_ms=None)` | Waits for page text after the action. |
| `Wait.url(url, *, timeout_ms=None)` | Waits for the active URL to match. |
| `Wait.loaded(state="load", *, timeout_ms=None)` | Waits for a load state. |
| `Wait.all(*conditions)` | Applies each condition in order. |

## Live queries

`browser.find` creates one `Query` type for every strategy.

| Factory | Contract |
| --- | --- |
| `css(selector)` | CSS selector. |
| `xpath(expression)` | XPath expression. |
| `role(role, *, name=None, exact=False)` | Accessible role and optional name. |
| `text(text, *, exact=False)` | Visible text. |
| `label(label, *, exact=False)` | Associated label text. |
| `placeholder(placeholder, *, exact=False)` | Input placeholder. |
| `alt_text(text, *, exact=False)` | Image alternative text. |
| `title(text, *, exact=False)` | Title attribute. |
| `test_id(test_id)` | `data-testid` value. |

`Query.click()`, `fill(value)`, `check()`, and `hover()` return the query. `Query.text()` returns a string. Queries resolve at operation time and return direct page results. Use snapshot refs when an operation needs transition evidence.

## Page and artifact namespaces

### `browser.page`

The root browser methods cover the common active-page operations. `browser.page.open`, `title`, `url`, `content`, `evaluate`, `read`, and `wait_for_text` accept the same arguments. The root `wait_for_url(url, ...)` and namespaced `page.wait_for_url(pattern, ...)` expose the same URL-pattern behavior under their declared parameter names. Namespace mutations return `None`. `browser.page` also adds these focused controls:

| Method | Contract |
| --- | --- |
| `set_content(html) -> None` | Replaces the active document. |
| `ready(*, timeout_ms=None, min_text_length=1) -> None` | Waits until the body contains the requested amount of text. |
| `wait_for_selector(selector, *, state="visible", timeout_ms=None) -> None` | Waits for attached, detached, hidden, or visible selector state. |
| `wait_for_function(predicate, *, timeout_ms=None) -> None` | Waits for a JavaScript predicate. |
| `wait_for_load_state(state="load") -> None` | Waits for a native load state. |
| `back() -> None`, `forward() -> None`, `reload() -> None` | Navigates browser history and invalidates cached CDP page handles. |

### `ReadMode`

| Constructor | Contract |
| --- | --- |
| `ReadMode.markdown(*, require=False)` | Requests Markdown and optionally requires a Markdown response. |
| `ReadMode.html()` | Returns the response body as HTML. |
| `ReadMode.outline_only()` | Returns a compact heading outline. |
| `ReadMode.llms_index(*, require_markdown=False)` | Reads the nearest `llms.txt` index. |
| `ReadMode.llms_full(*, require_markdown=False)` | Reads the nearest `llms-full.txt`. |

### `browser.capture`, `browser.diff`, and `browser.downloads`

| Method | Contract |
| --- | --- |
| `capture.screenshot(path=None, *, selector=None, full_page=False, annotate=False, output_dir=None, format="png", quality=None, wait_ms=100) -> Screenshot` | Writes a page or element screenshot. `wait_ms` must be non-negative. |
| `capture.pdf(path=None, *, print_background=True, landscape=False, prefer_css_page_size=False) -> Path` | Writes the active page as a PDF. |
| `diff.snapshot(baseline=None, *, selector=None, compact=False, max_depth=None) -> SnapshotDiff` | Compares the active snapshot with text, a path, or a prior baseline. |
| `downloads.download(selector, path) -> Path` | Clicks a selector and returns the completed download path. |
| `downloads.wait(path=None, *, timeout_ms=None) -> Path` | Waits for the next download. |

`Screenshot` exposes `path`, `format`, `annotations`, `raw`, `bytes()`, `save(path)`, and Pillow or notebook display helpers. Pillow-backed members require the `images` extra.

## Browser-state namespaces

### `browser.session`

`browser.session.status() -> SessionStatus` returns the current native session,
browser, restore, and persistence state. The async method returns the same model.
It can inspect a lazy session before Chrome launches.

| Field | Contract |
| --- | --- |
| `session_id`, `namespace`, `socket_dir`, `background_pid` | Identify the native session and its control boundary. |
| `browser_launched`, `page_count`, `engine`, `launch_hash` | Report the effective browser process and launch state. |
| `compatibility_status` | Reports native launch compatibility. |
| `restore_key`, `restore_status`, `restore_status_detail` | Report restore configuration and load outcome. |
| `restore_loaded_path`, `restore_validation_pending` | Report loaded state and pending validation. |
| `restore_save`, `save_status`, `restore_saved_path` | Report persistence policy and the latest save outcome. |
| `restore_check_url`, `restore_check_text`, `restore_check_fn` | Report configured restore validation. |
| `raw` | Preserves the complete native response mapping. |

### `browser.tabs`

| Method | Contract |
| --- | --- |
| `list() -> tuple[TabInfo, ...]` | Returns open tabs. |
| `new(url=None, *, label=None) -> TabInfo` | Creates a tab with an optional URL and label. |
| `open(url, *, label=None, reuse=True, wait_until="load") -> TabInfo` | Opens a URL and reuses a matching label when requested. |
| `switch(*, id=None, label=None, index=None) -> None` | Switches by exactly one id, label, or zero-based index. |
| `close(*, id=None, label=None, index=None) -> None` | Closes the selected tab or the active tab. |

### `browser.cookies`

| Method | Contract |
| --- | --- |
| `get(urls=None, *, unsafe_export_all=False) -> tuple[Cookie, ...]` | Returns cookies visible to selected URLs. Domain allowlists filter exported cookies. |
| `set(name=None, value=None, *, cookies=None, url=None, domain=None, path=None, expires=None, http_only=None, secure=None, same_site=None) -> None` | Sets one cookie or a cookie mapping sequence. |
| `clear(*, unsafe_clear_all=False) -> None` | Clears cookies. A domain-restricted session requires the explicit unscoped override. |

### `browser.storage` and `browser.state`

| Method | Contract |
| --- | --- |
| `storage.get(key=None, *, area="local")` | Reads one key or the full local or session storage area. |
| `storage.set(key, value, *, area="local") -> None` | Writes one storage value. |
| `storage.clear(*, area="local") -> None` | Clears one storage area. |
| `state.save(path=None, *, unsafe_export_all=False) -> Path` | Writes cookies and origin storage. Domain allowlists filter the saved state. |
| `state.load(path, *, unsafe_import_all=False) -> None` | Loads cookies and origin storage. Domain allowlists filter the input file. |
| `state.list() -> Mapping` | Lists saved native state. |
| `state.show(path) -> Mapping` | Reads one saved-state record. |
| `state.clear(path=None) -> None` | Clears selected saved state. |
| `state.clean(*, days=30) -> None` | Removes state older than the requested age. |
| `state.rename(path, name) -> None` | Renames one state record. |

### `browser.dialogs` and `browser.dashboard`

| Method | Contract |
| --- | --- |
| `dialogs.status() -> Mapping` | Returns active JavaScript dialog state. |
| `dialogs.accept(prompt_text=None) -> None` | Accepts the dialog and optionally supplies prompt text. |
| `dialogs.dismiss() -> None` | Dismisses the dialog. |
| `dashboard.status() -> Mapping` | Returns configured dashboard stream state. |
| `dashboard.stop() -> None` | Stops streaming and releases the dashboard sidecar. |

## Input and environment namespaces

| Namespace | Methods and defaults |
| --- | --- |
| `browser.keyboard` | `type(text)`, `insert_text(text)`, `press(key)`, `down(key, *, code=None, text=None)`, `up(key, *, code=None)`, `dispatch(event_type, *, key=None, code=None, text=None)` |
| `browser.mouse` | `move(x, y)`, `down(*, button="left")`, `up(*, button="left")`, `wheel(delta_y=100, *, delta_x=0, x=0, y=0)`, `dispatch(event_type, *, x=0, y=0, button="none", click_count=0)` |
| `browser.clipboard` | `read() -> str`, `write(text)`, `copy()`, `paste()` |
| `browser.emulation` | `viewport(width, height, *, device_scale_factor=1.0, mobile=False)`, `device(name)`, `headers(headers)`, `offline(enabled=True)`, `user_agent(value)`, `media(*, media=None, color_scheme=None, reduced_motion=None, features=None)`, `timezone(timezone_id)`, `locale(locale)`, `geolocation(latitude, longitude, *, accuracy=None)`, `permissions(permissions, *, origin=None)` |

Mutation methods return `None`. `clipboard.read()` returns a string.

## Network and script namespaces

### `browser.network`

| Method | Contract |
| --- | --- |
| `route(url, *, abort=False, response=None, status=None, body=None, content_type=None, headers=None, resource_type=None, resource_types=None) -> None` | Registers a request route. `response` accepts `RouteResponse` or a mapping. |
| `unroute(url=None) -> None` | Removes one route or all routes. |
| `requests(*, clear=False, url_pattern=None, resource_type=None, method=None, status=None) -> tuple[NetworkRequest, ...]` | Returns captured request summaries. |
| `request_detail(request_id) -> RequestDetail` | Returns request and response detail. |
| `har_start() -> None` | Starts HAR capture. |
| `har_stop(path=None) -> Path` | Stops HAR capture and returns the written path. |
| `credentials(username, password) -> None` | Sets HTTP authentication credentials. |

### `browser.scripts`, `browser.diagnostics`, and `browser.active_frame`

| Method | Contract |
| --- | --- |
| `scripts.add_init(script=None, *, path=None) -> str` | Registers one inline or file-backed init script and returns its identifier. |
| `scripts.remove_init(identifier) -> None` | Removes an init script. |
| `scripts.add(script=None, *, url=None) -> None` | Injects one inline or remote page script. |
| `scripts.add_style(content=None, *, url=None) -> None` | Injects one inline or remote stylesheet. |
| `diagnostics.console(*, clear=False) -> tuple[ConsoleMessage, ...]` | Returns captured console messages. |
| `diagnostics.errors() -> Mapping` | Returns page errors. |
| `diagnostics.vitals() -> Mapping` | Returns page vitals. |
| `diagnostics.react_tree(*, selector=None) -> Mapping` | Returns React tree diagnostics. |
| `active_frame.select(*, selector=None, name=None, url=None) -> None` | Selects one native frame. |
| `active_frame.main() -> None` | Restores the main native frame. |

Script and style methods accept exactly one inline source or URL or path. Invalid source combinations raise `ValueError`.

## CDP

The `cdp` extra supplies WebSocket transport for CDP operations.

| API | Contract |
| --- | --- |
| `browser.cdp.frames.list()` | Returns frames for the active target. |
| `browser.cdp.frames.get(*, selector=None, name=None, url=None)` | Resolves one frame. |
| `browser.cdp.target(*, label=None, url=None, target_id=None)` | Resolves one target. |
| `browser.cdp.evaluate(script, *, frame=None, extension_id=None, context=None, await_promise=True, return_by_value=True)` | Evaluates JavaScript in a selected CDP realm. |
| `browser.cdp.send(method, params=None, *, session_id=None)` | Sends one raw CDP command and returns its result mapping. |

Navigation, tab changes, and browser relaunch invalidate cached CDP handles. Resolve handles again after those lifecycle events.

## Native protocol

### `browser.native.execute(action, **params) -> BrowserResponse`

Executes one native action and returns its complete response envelope. An unsuccessful native response remains available through `success`, `data`, `raw`, and `warning`.

### `browser.native.data(action, *, expect="object", **params)`

Executes one native action and returns successful response data. `expect="object"` requires a mapping. `expect="any"` accepts every JSON value. Native failures raise `BrowserError`.

Domain allowlists, policy confirmation, and browser or CDP lifecycle tracking apply to both methods. See the [`agent-browser` command reference at the embedded commit](https://github.com/vercel-labs/agent-browser/blob/afae698a51242166170b6fe4809dd57fe9f75798/README.md#commands) for native action names and parameters.

## Confirmation

Typed operations raise `ConfirmationRequired` when the native policy pauses an action. `required.pending.confirm()` resumes the complete initiating operation and returns its declared type. `required.pending.deny()` rejects it and returns `None`.

`PendingAction.map(callback)` composes work after confirmation. Callbacks run in registration order and remain attached across repeated confirmation prompts. `AsyncPendingAction` provides awaitable `confirm()` and `deny()`.

## Public result models

| Model | Contract |
| --- | --- |
| `BrowserResponse` | Complete native response envelope. |
| `CloseResult` | Terminal browser close and restore-save result. |
| `ReadResult` | URL, final URL, status, content type, source, truncation state, content, and raw data. |
| `Screenshot` | Screenshot path, format, annotations, and image helpers. |
| `SnapshotDiff` | Text diff, line counts for additions, removals, and unchanged content, plus a changed flag. |
| `TabInfo` | Tab id, URL, title, label, and active state. |
| `Cookie` | Cookie value and browser metadata. |
| `NetworkRequest` | Captured request summary. |
| `RequestDetail` | Request, response, headers, status, and body details. |
| `ConsoleMessage` | Console type, text, level, and source location. |
| `ProxyConfig` | Proxy server, bypass rules, and optional credentials. |
| `RouteResponse` | Static response registered by `browser.network.route()`. |
| `SessionId` | Stable filesystem-derived session identity. |
| `SessionStatus` | Current browser, launch, restore, and restore-save lifecycle state. |

## Errors

| Error | Contract |
| --- | --- |
| `AgentBrowserError` | Base class for SDK-owned errors. |
| `BrowserError` | Native failure or Python safety rejection. Exposes `action`, `response`, and `code`. |
| `ConfirmationRequired` | Policy pause carrying a typed `pending` action. |
| `StaleRefError` | Expired synchronous ref with `refresh()`. |
| `AsyncStaleRefError` | Expired asynchronous ref with awaitable `refresh()`. |
| `ActionTransitionError` | Mutation succeeded, then its wait or evidence stage failed. |
| `NativeParseError` | A typed native payload missed a required field or shape. |
| `BrowserInstallError` | Browser discovery or installation failed. |
| `RestoreSaveError` | Browser cleanup completed, but restore persistence failed. Exposes the terminal `result`. |

CDP protocol, timeout, closed, stale-object, frame, context, target, and evaluation errors live in `agentbrowser.cdp`.

## Versions and embedded skills

`agentbrowser.__version__` is the Python SDK version. `agentbrowser.__agent_browser_version__` and `agentbrowser.__agent_browser_commit__` identify the embedded native engine.

Embedded upstream skill data is available through `agentbrowser.skills`:

```python
import agentbrowser.skills as skills

print(skills.available())
print(skills.read("core"))
```

See [Get started](getting-started.md) for the first browser session and [Guides](guides.md) for complete workflows.
