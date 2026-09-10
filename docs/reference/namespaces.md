---
title: Capability namespace reference
description: Exact method contracts for page, query, capture, tabs, state, network, input, diagnostics, WebMCP, CDP, and native namespaces.
---

# Capability namespace reference

`Browser` and `AsyncBrowser` expose the same capability namespaces. Asynchronous methods await the same operation and return the same model unless this page states a difference.

| Namespace | Job |
| --- | --- |
| `page` | Page identity, navigation, frames, content, reading, queries, capture, and waits |
| `page.find` | Live element queries for one page or frame |
| `page.capture`, `diff`, `downloads` | Files and page evidence |
| `tabs`, `session` | Browser targets and session status |
| `cookies`, `storage`, `state` | Live and serialized browser data |
| `network` | Routing, requests, credentials, and HAR capture |
| `keyboard`, `mouse`, `clipboard` | User input |
| `emulation` | Device and environment settings |
| `scripts` | Page code and initialization scripts |
| `diagnostics`, `dialogs` | Runtime inspection and JavaScript dialogs |
| `webmcp`, `dashboard` | Agent tools and session observability |
| `cdp` | Direct Chrome DevTools Protocol access |
| `native` | Complete pinned engine protocol |

## `browser.page`

`browser.page` returns a handle for the configured or currently active target.
Retain that handle when subsequent commands must use the same page.
`browser.tabs.get()` selects an exact browser target. `page.frames.get()` returns a `Frame` whose
observation, queries, evaluation, waits, capture, and ref actions share one
frame scope.

| Method | Contract |
| --- | --- |
| `open(url, *, wait_until="load")` | Normalize a host-like URL and navigate. Returns `None`. |
| `title()` | Return this document's title. |
| `url()` | Return this document's URL. |
| `content()` | Return this document's HTML. |
| `set_content(html)` | Replace this page's document. |
| `evaluate(script)` | Evaluate JavaScript in this document's default execution context and await promises. |
| `read(url=None, *, mode=None, filter=None, timeout_ms=None, headers=None, allowed_domains=None)` | Return `ReadResult` for an explicit URL or this page's rendered document. |
| `ready(*, timeout_ms=None, min_text_length=1)` | Wait for minimum body text. |
| `back()`, `forward()`, `reload()` | Navigate history and invalidate direct CDP frame and execution-context handles. |
| `wait_for_text(text, *, timeout_ms=None)` | Wait for text. |
| `wait_for_selector(selector, *, state="visible", timeout_ms=None)` | Wait for attached, detached, hidden, or visible selector state. |
| `wait_for_url(pattern, *, timeout_ms=None)` | Wait for a URL pattern. |
| `wait_for_function(predicate, *, timeout_ms=None)` | Wait for a JavaScript predicate. |
| `wait_for_load_state(state="load")` | Wait for a load state. |
| `observe(spec=None)` | Capture a `Snapshot` bound to this page or frame. |
| `geometry(selector=None)` | Measure bounds, client size, scroll size, and overflow for a document or element. |
| `frames.tree()` | Return descendant frame handles with browser frame IDs, names, URLs, and parent IDs. |
| `frames.get(*, id=None, selector=None, name=None, url=None)` | Resolve exactly one frame. ID, name, and URL search descendants. A selector resolves an owning element in this document. |

`frames.get()` supplies the frame identity from the browser. Direct `Frame`
and `AsyncFrame` construction requires a non-empty `frame_id` keyword argument.

Frame load waits accept `none`, `domcontentloaded`, and `load`. Network-idle
tracking belongs to the page target.
`Page` adds navigation, document replacement, history, and `read()` to the
document operations shared with `Frame`. Use the owning `Page` for those
operations.

## `page.find`

| Factory | Match |
| --- | --- |
| `css(selector)` | CSS selector |
| `xpath(expression)` | XPath expression |
| `role(role, *, name=None, exact=False)` | Accessible role and optional name |
| `text(text, *, exact=False)` | Visible text |
| `label(label, *, exact=False)` | Associated label |
| `placeholder(placeholder, *, exact=False)` | Input placeholder |
| `alt_text(text, *, exact=False)` | Image alternative text |
| `title(text, *, exact=False)` | Title attribute |
| `test_id(test_id)` | `data-testid` attribute |

`Query.click()`, `fill(value)`, `check()`, and `hover()` return the query. `Query.text()` returns a string.

## `page.capture`, `browser.diff`, and `browser.downloads`

| Method | Contract |
| --- | --- |
| `capture.screenshot(path=None, *, selector=None, full_page=False, annotate=False, output_dir=None, format="png", quality=None, wait_ms=100)` | Write a PNG or JPEG screenshot and return `Screenshot`. JPEG quality ranges from 0 through 100. |
| `capture.pdf(path=None, *, print_background=True, landscape=False, prefer_css_page_size=False)` | Write a PDF and return its `Path`. |
| `frame.capture.screenshot(path=None, *, output_dir=None, format="png", quality=None, wait_ms=100)` | Capture the visible frame rectangle, clipped by enclosing frames and overflow containers. |
| `diff.snapshot(baseline=None, *, selector=None, compact=False, max_depth=None)` | Compare the active snapshot with text, a path, or a prior baseline. |
| `downloads.download(selector, path)` | Click a selector and return the completed download path. |
| `downloads.wait(path=None, *, timeout_ms=None)` | Wait for the next download. |

`wait_ms` must be non-negative. Pillow-backed screenshot members require the `images` extra.

Screenshot paths expand `~` and create parent directories. A frame screenshot
captures the rendered frame rectangle. Selector, full-page, annotated, and
PDF capture belong to the owning page.

## `browser.tabs`

| Method | Contract |
| --- | --- |
| `list()` | Return open tabs as `tuple[TabInfo, ...]`. |
| `get(*, id=None, label=None, index=None)` | Return a `Page` bound to one exact browser target. |
| `new(url=None, *, label=None)` | Create a tab. The optional URL is forwarded as given. |
| `open(url, *, label=None, reuse=True, wait_until="load")` | Normalize and open a URL. Reuse a matching label by default. `wait_until` applies to reused-tab navigation, while new-tab creation requires an explicit readiness wait. |
| `switch(*, id=None, label=None, index=None)` | Switch by exactly one selector and return `TabSwitchResult`. `index=1` maps to stable ID `t1` and is not positional. |
| `close(*, id=None, label=None, index=None)` | Close a selected or active tab and return `TabCloseResult`. Numeric `index` maps to the stable `tN` suffix. |

Labels are unique within one session. They start with an ASCII letter and contain letters, digits, hyphens, or underscores.

New tabs inherit configured session headers, credentials, user agent, locale,
timezone, geolocation, offline mode, routes, color scheme, and init scripts
before their first navigation. The native `click` action with `newTab=True`
uses the same setup path.

## `browser.session`

`session.status() -> SessionStatus` reports native session identity, process state, browser state, restore validation, and the latest persistence result. It can inspect a lazy session before Chrome launches.

## `browser.cookies`

| Method | Contract |
| --- | --- |
| `get(urls=None, *, unsafe_export_all=False)` | Return cookies visible to selected URLs. |
| `set(name=None, value=None, *, cookies=None, url=None, domain=None, path=None, expires=None, http_only=None, secure=None, same_site=None)` | Set one cookie or a sequence of cookie mappings. |
| `clear(*, unsafe_clear_all=False)` | Clear cookies. A restricted session requires explicit unscoped authorization. |

When `cookies=` is present, it supplies the batch input. Use scalar fields for one cookie.

## `browser.storage` and `browser.state`

| Method | Contract |
| --- | --- |
| `storage.get(key=None, *, area="local")` | Read one key or an entire local or session Web Storage area. |
| `storage.set(key, value, *, area="local")` | Write one storage value. |
| `storage.clear(*, area="local")` | Clear one storage area. |
| `state.save(path=None, *, unsafe_export_all=False)` | Write cookies and origin storage to a state file. |
| `state.load(path, *, unsafe_import_all=False)` | Load a state file. Domain-restricted sessions reject this operation. |
| `state.list()` | List saved native state records. |
| `state.show(path)` | Read one saved-state record. |
| `state.clear(path=None)` | Clear selected saved state. |
| `state.clean(*, days=30)` | Remove saved state older than the requested age. |
| `state.rename(path, name)` | Rename one saved-state record. |

## `browser.network`

| Method | Contract |
| --- | --- |
| `route(url, *, abort=False, response=None, status=None, body=None, content_type=None, headers=None, resource_type=None, resource_types=None)` | Register request abort or response behavior. |
| `unroute(url=None)` | Remove one route or every route. |
| `requests(*, clear=False, url_pattern=None, resource_type=None, method=None, status=None)` | Return captured request summaries. |
| `request_detail(request_id)` | Return request and response details. |
| `har_start(*, content="text")` | Start HTTP Archive capture. Content is `text`, `all`, or `none`. |
| `har_stop(path=None)` | Stop capture and return the written path. |
| `credentials(username, password)` | Set HTTP authentication credentials. |

If `response=` is present, it takes precedence over response shorthand fields.

## `browser.keyboard`

| Method | Contract |
| --- | --- |
| `type(text)` | Type text with keyboard events. |
| `insert_text(text)` | Insert text directly. |
| `press(key)` | Press a key or chord. |
| `down(key, *, code=None, text=None)` | Dispatch key-down. |
| `up(key, *, code=None)` | Dispatch key-up. |
| `dispatch(event_type, *, key=None, code=None, text=None)` | Dispatch a low-level keyboard event. |

## `browser.mouse`

| Method | Contract |
| --- | --- |
| `move(x, y)` | Move to CSS pixel coordinates. |
| `down(*, button="left")`, `up(*, button="left")` | Dispatch a mouse button transition. |
| `wheel(delta_y=100, *, delta_x=0, x=0, y=0)` | Dispatch wheel input. |
| `dispatch(event_type, *, x=0, y=0, button="none", click_count=0)` | Dispatch a low-level mouse event. |

## `browser.clipboard`

`read()` returns text. `write(text)`, `copy()`, and `paste()` mutate clipboard or page selection state and return `None`.

## `browser.emulation`

| Method | Contract |
| --- | --- |
| `viewport(width, height, *, device_scale_factor=1.0, mobile=False)` | Set CSS viewport and device scale. |
| `device(name)` | Apply a named device preset. |
| `headers(headers)` | Set extra HTTP headers. |
| `offline(enabled=True)` | Set network offline emulation. |
| `user_agent(value)` | Set the browser user agent. |
| `media(*, media=None, color_scheme=None, reduced_motion=None, features=None)` | Set CSS media features. |
| `timezone(timezone_id)` | Set the emulated timezone. |
| `locale(locale)` | Set the emulated locale. |
| `geolocation(latitude, longitude, *, accuracy=None)` | Set coordinates. |
| `permissions(permissions, *, origin=None)` | Grant permissions for an optional origin. |

## `browser.scripts`

| Method | Contract |
| --- | --- |
| `add_init(script=None, *, path=None)` | Register inline or file-backed JavaScript for future documents and return its identifier. |
| `remove_init(identifier)` | Remove one init script. |
| `add(script=None, *, url=None)` | Inject JavaScript into the current document. |
| `add_style(content=None, *, url=None)` | Inject CSS into the current document. |

Supply one inline value or URL according to the method signature.

## `browser.dialogs` and `browser.dashboard`

| Method | Contract |
| --- | --- |
| `dialogs.status()` | Return current JavaScript dialog state. |
| `dialogs.accept(prompt_text=None)` | Accept a dialog and optionally provide prompt text. |
| `dialogs.dismiss()` | Dismiss a dialog. |
| `dashboard.status()` | Return configured dashboard stream status. |
| `dashboard.stop()` | Stop streaming and release the dashboard helper. |

## `browser.diagnostics`

| Method | Contract |
| --- | --- |
| `console(*, clear=False)` | Return `ConsoleMessage` records. |
| `errors()` | Return page error data. |
| `vitals()` | Reload the active page, wait three seconds, and return Core Web Vitals plus navigation and React hydration timing. |
| `accessibility(url=None, *, tags=(), selector=None)` | Run axe-core and return `AccessibilityAudit`. |
| `react_tree(*, selector=None)` | Return React tree data. Launch with `AGENT_BROWSER_ENABLE=react-devtools`. |

## `browser.webmcp`

| Method | Contract |
| --- | --- |
| `list()` | Return page-provided tools as `WebMCPTool` models. |
| `invoke(tool, params=None, *, frame_id=None, detach=False, timeout_ms=None)` | Start a tool call and return `WebMCPInvocation`. |
| `result(invocation_id, *, timeout_ms=None)` | Wait for a detached invocation. |
| `cancel(invocation_id)` | Cancel an active invocation. |

## `browser.cdp`

| Method | Contract |
| --- | --- |
| `frames.list()` | Return frames for the active page target. |
| `frames.get(*, selector=None, name=None, url=None)` | Return exactly one frame. |
| `evaluate(script, *, frame=None, extension_id=None, context=None, await_promise=True, return_by_value=True)` | Evaluate in a frame or execution context. |
| `send(method, params=None, *, session_id=None)` | Send one raw protocol method. |
| `target(*, label=None, url=None, target_id=None)` | Return a direct page-target handle. |

The optional `cdp` package is required. Frame and execution-context handles expire after navigation-like transitions. Target handles resolve their selected page target when an operation runs.

## `browser.native`

| Method | Contract |
| --- | --- |
| `execute(action, **params)` | Return the complete `BrowserResponse` envelope. |
| `data(action, *, expect="object", **params)` | Check success and return data. Use `expect="any"` for arbitrary JSON. |

Typed and raw calls share browser preparation, policy, confirmation, lifecycle, and invalidation behavior. Raw `execute()` preserves unsuccessful and confirmation-required envelopes.
