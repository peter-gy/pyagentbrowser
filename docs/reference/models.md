---
title: Models and errors
description: Typed results, evidence records, browser state, network data, WebMCP results, and error contracts.
---

# Models and errors

Public result models are frozen dataclasses unless this page states otherwise. Most preserve the complete native mapping in a `raw` field.

## Evidence models

| Model | Fields and contract |
| --- | --- |
| `SnapshotSpec` | `selector`, `interactive`, `compact`, `max_depth`, and `urls` define one accessibility capture. |
| `Snapshot` | `text`, `origin`, `url`, `spec`, `refs`, `generation`, and `raw`, plus ref lookup, refresh, and diff operations. |
| `Ref` | Snapshot-scoped `id`, selector, role, name, source snapshot, browser, and native metadata. |
| `ActionResult` | `action`, `target`, `before`, `after`, and `diff` for one completed ref mutation. |
| `SnapshotDiff` | Unified `text`, addition, removal, and unchanged counts, `changed`, and raw source values. |
| `Wait` | One post-action text, URL, load, or ordered combined condition. |

`Snapshot.one()` raises `LookupError` with the failed criteria and bounded
candidate refs when criteria match zero or several refs. `Snapshot.ref()` raises
`KeyError` for an unknown ID.

`SnapshotSpec(selector=None, interactive=True, compact=False, max_depth=None, urls=False)` accepts a non-negative maximum depth. A negative value raises `ValueError`.

### `Snapshot`

| Member | Contract |
| --- | --- |
| `text` | Human-readable accessibility tree. |
| `origin` | Page URL or origin reported by the native engine. |
| `url` | Alias for `origin`. |
| `spec` | `SnapshotSpec` reused by refresh and ref mutations. |
| `refs` | Mapping of ref IDs to bound `Ref` objects. |
| `raw` | Native snapshot response mapping. |
| `ref(ref_id)` | Resolve an exact ID such as `e1` or `@e1`. |
| `one(*, role=None, name=None, contains=None, exact=False)` | Return exactly one ref or raise `LookupError`. |
| `all(*, role=None, name=None, contains=None, exact=False)` | Return every matching ref as a tuple. |
| `refresh()` | Capture the same `SnapshotSpec` again. |
| `diff()` | Capture the same document scope and compare it with this snapshot, returning `SnapshotDiff`. |

Interactive representations keep snapshots, refs, action results, diffs, browser
controllers, and close results bounded. Read `.text`, `.raw`, or the explicit
fields when a code-mode task needs their complete content.

### `Ref`

Every mutation returns `ActionResult` and accepts an optional `wait` condition.

| Method | Contract |
| --- | --- |
| `click(*, button="left", click_count=1, new_tab=False, wait=None)` | Click with a mouse button and count. |
| `fill(value, *, wait=None)` | Replace a form value. |
| `type(text, *, wait=None)` | Type text with input events. |
| `select(value, *, wait=None)` | Select an option value. |
| `check(*, wait=None)`, `uncheck(*, wait=None)` | Change checked state. |
| `hover(*, wait=None)`, `tap(*, wait=None)`, `focus(*, wait=None)` | Move or focus interaction. |
| `clear(*, wait=None)`, `scroll_into_view(*, wait=None)` | Clear a control or reveal the target. |
| `text()` | Return text content. |
| `inner_text()` | Return rendered text. |
| `input_value()` | Return the current form value. |
| `attribute(name)` | Return an attribute value or `None`. |
| `is_visible()`, `is_enabled()`, `is_checked()` | Return one boolean element state. |
| `content_frame()` | Resolve the child `Frame` owned by this observed iframe element. |
| `refresh(*, role=None, name=None, contains=None, exact=True)` | Resolve accessible metadata against a fresh snapshot. |

`Ref` also exposes its source `snapshot`, `browser`, ID without `@`, native selector, accessible role, accessible name, and raw metadata. Native `stale_ref` and `unknown_ref` failures become `StaleRefError`.

### `Wait`

| Constructor | Contract |
| --- | --- |
| `Wait.text(text, *, timeout_ms=None)` | Wait for page text after the action. |
| `Wait.url(url, *, timeout_ms=None)` | Wait for an active URL pattern. |
| `Wait.loaded(state="load", *, timeout_ms=None)` | Wait for a load state. |
| `Wait.all(*conditions, timeout_ms=None)` | Apply one or more conditions in order within an optional shared timeout. |

Timeouts must be non-negative and use milliseconds. `Wait.all()` requires at least one condition.

### `ActionResult` and `ActionTransitionError`

`ActionResult(action, target, before, after, diff)` records a completed ref mutation and its evidence.

`ActionTransitionError` means the mutation completed before the `wait`, `snapshot`, or `diff` stage failed. It exposes `action`, `target`, `stage`, `before`, optional `after`, and `cause`.

## Page and artifact models

| Model | Fields and contract |
| --- | --- |
| `ReadResult` | Requested `url`, `final_url`, status, content type, source, truncation state, content, and raw data. |
| `ReadMode` | Selects Markdown negotiation, raw response body, outline, `llms.txt`, or `llms-full.txt` behavior. |
| `DocumentScope` | Page target, frame, URL, and evidence generation attached to a document operation. |
| `ElementGeometry` | Document scope, selector, bounds, client size, scroll size, and overflow flags. |
| `FrameLookupError` | `not_found`, `ambiguous`, `detached`, or `scope_mismatch` reason plus criteria and bounded frame candidates. |
| `ScrollResult` | Document scope, container, before and after offsets, and derived movement state. |
| `Screenshot` | File path, format, scope, annotations, raw capture data, bytes, host content, copying, image loading, and notebook display. |
| `ConsoleMessage` | Console type, text, level, URL, line, column, and raw data. |

### `Screenshot`

| Member | Contract |
| --- | --- |
| `bytes()` | Read the captured file bytes. |
| `content()` | Return `ImageContent` for an agent host. |
| `save(path)` | Copy the file and return a new `Screenshot` for the target path. |
| `pil(*, mode=None)` | Load a Pillow image and optionally convert its mode. |
| `image` | Lazily load and cache the Pillow image. |
| `annotations` | Ref number, role, accessible name, and bounding box for annotated elements. |

`pil()` and `image` require the `images` extra. PNG and JPEG captures expose
notebook display data from their file bytes.

`EvidenceManifest.record()` associates a snapshot, action result, screenshot,
scroll result, or element geometry with optional `ImageDelivery`, agent assessment, and named
`EvidenceAssertion` values. `to_dict()` returns a JSON-compatible report. A
delivery receipt records the host boundary. An assessment records what the
agent concluded after receiving the evidence.

## Code-mode models

| Model | Contract |
| --- | --- |
| `OpenTarget(url)` | Application URL to open in an owned browser. |
| `AttachedTarget(connection, target_id)` | `CDPTarget` connection and exact existing page identity. |
| `ImageContent(data, media_type, source=None)` | Non-empty image bytes, image MIME type, and optional source path. |
| `ImageDelivery(status, id=None)` | Host acknowledgement with status `accepted`, `queued`, or `submitted`. |
| `ExecutionContext(timeout_ms=None, cancellation=False, managed_tasks=False)` | Execution budget and host capabilities. `limit(requested_ms=None, cleanup_ms=1000)` returns the remaining operation budget. |
| `AgentConnectionStatus` | Registry name, process ID, ownership, session ID, lifecycle, target ID, and URL. |
| `ManagedTaskStatus` | Task ID, lifecycle state, optional progress, and detail. |

`AgentHost.current_target()`, `emit_image(content)`, and `execution_context()`
provide these values to executed code. `AgentHost.image_delivery` reports
whether the current execution accepts image content. `CallbackHost(target, image_emitter=None,
execution=...)` accepts application callbacks. Bind a host with `bind_host()`
and restore the previous binding with `reset_host(token)`. `current_host()`
raises `RuntimeError` when called outside a binding.

### `CodeSession`

`CodeSession(target, *, namespace=None)` creates persistent Python globals and
a task registry. `target` accepts a `BrowserTarget` value or a callback.

| Method | Contract |
| --- | --- |
| `execute_code(code, *, timeout_ms=None)` | Execute trusted Python and return ordered text/image `content` plus `isError`. |
| `await aexecute_code(code, *, timeout_ms=None)` | Execute Python with top-level `await`. |
| `await close()` | Settle task cancellation and mark the session closed. |

Calls on one session must run sequentially. Exceptions preserve emitted output
and existing globals and set `isError=True`. Concurrent calls and calls after
close raise `RuntimeError`. Synchronous execution with no tasks allocates no
event-loop resources and reports `managed_tasks=False`. Asynchronous execution
reports `managed_tasks=True` and provides `current_host().start_task()`.
The application owns injected objects and interruption
of arbitrary Python work. See [Code-mode integration](/guides/code-mode) for
the model-facing transport boundary.

### `Tasks` and `Task`

`Tasks(target)` owns tasks on the event loop that starts its first operation.
`CodeSession.tasks` provides the registry used by `current_host().start_task()`.

| Method | Contract |
| --- | --- |
| `tasks.start(name, operation, *, timeout_ms=None)` | Start an async callable and return a retained `Task`. |
| `tasks.get(task_id)` | Return one retained task or raise `KeyError`. |
| `tasks.list()` | Return retained handles in creation order. |
| `await tasks.close()` | Cancel running tasks, await cleanup, and close the registry. |
| `task.status()` | Return `ManagedTaskStatus`. |
| `task.report(progress=None, detail=None)` | Update a running task's progress from 0 through 1 and detail. Omitted values retain their current values. |
| `await task.result(*, timeout_ms=None)` | Retrieve the value or exception. A retrieval timeout leaves the task running. |
| `await task.cancel()` | Request cancellation, await cleanup, and return terminal status. |

Task handles expose `id` and `name`. Await operations and close on the owning
event loop. Cancellation is cooperative and an operation that catches it can
complete or fail. Background tasks return screenshots for emission during an
active code call. Each task captures its application target when it starts and
receives an independent execution budget.

## Session, tab, and storage models

| Model | Fields and contract |
| --- | --- |
| `CloseResult` | `closed`, restore status, save status, state path, save error, and raw terminal data. |
| `SessionStatus` | Native identity, socket path, background PID, browser launch state, page count, engine, compatibility, restore checks, save state, and raw data. |
| `SessionId` | Derived session string, scope, source path, and hash. |
| `TabInfo` | Native ID, URL, title, label, active state, optional stable target ID, and raw data. |
| `TabSwitchResult` | Selected tab fields plus `revived` and `dialog_blocked`. |
| `TabCloseResult` | Closed tab fields plus `closed` and `active_tab_revived`. |
| `Cookie` | Name, value, domain, path, expiry, security flags, same-site value, and raw data. |

Restore status values are `load_failed`, `loaded`, `loaded_but_invalid`, `missing`, `not_configured`, and `pending`.

Save status values are `disabled`, `error`, `invalid_policy`, `no_browser`, `not_attempted`, `not_configured`, `saved`, and `skipped_restore_failed`.

## Network models

| Model | Fields and contract |
| --- | --- |
| `NetworkRequest` | ID, URL, method, resource type, status, and raw summary. |
| `RequestDetail` | ID, URL, method, status, request headers, response headers, optional body, and raw data. |
| `RouteResponse` | Optional status, body, content type, and headers for one registered response. |
| `ProxyConfig` | Proxy server, bypass rules, username, and password. |

HTTP Archive content modes are `text`, `all`, and `none`.

## Accessibility models

An accessibility audit runs axe-core rules. It is separate from the accessibility snapshot used for refs.

| Model | Fields and contract |
| --- | --- |
| `AccessibilityAudit` | Audited URL, axe-core version, counts, violations, incomplete checks, and raw data. |
| `AccessibilityCounts` | Violation, incomplete, pass, and inapplicable rule counts. |
| `AccessibilityIssue` | `id`, `impact`, `help`, `help_url`, `tags`, `node_count`, `nodes`, and `raw`. |
| `AccessibilityNode` | Nested selector target, HTML excerpt, failure summary, and raw data. |

## WebMCP models

| Model | Fields and contract |
| --- | --- |
| `WebMCPTool` | Name, description, input schema, annotations, origin, frame identity, optional backend node ID, and raw data. |
| `WebMCPInvocation` | `invocation_id`, `tool_name`, `frame_id`, `origin`, `status`, `duration_ms`, `raw_status`, `output`, `output_truncated`, `original_output_bytes`, `error`, and `raw`. |

Invocation status is `pending`, `completed`, `canceled`, `failed`, or `timed_out`.

## Native response model

`BrowserResponse` is the complete envelope returned by `browser.native.execute()`:

| Field | Contract |
| --- | --- |
| `id` | Native JSON command ID. |
| `action` | Native action name. |
| `success` | Whether the action succeeded. |
| `data` | Raw response data. |
| `warning` | Optional native warning. |
| `raw` | Complete response mapping. |

## Pending confirmation

`PendingAction[T]` exposes `confirmation_id`, native `action`, and confirmation-response `details` for one paused operation.

| Method | Contract |
| --- | --- |
| `confirm() -> T` | Recheck current policy and domain containment, replay the action, and finish typed higher-level work. Another confirmation can raise `ConfirmationRequired` again. |
| `deny() -> None` | Reject and consume the pending action. |
| `map(callback) -> PendingAction[U]` | Return a continuation that applies `callback` after the previous typed completion. Callbacks compose in registration order. |

`AsyncPendingAction` exposes the same fields. Its `confirm()` and `deny()` methods are awaitable, while `map()` is synchronous.

A pending confirmation is tied to its ID and native session. A mismatched, consumed, or missing ID raises `BrowserError`. Policy replay also raises `BrowserError` when the file changed to deny the action, became invalid, or disappeared.

## Errors

Catch SDK-owned failures through `AgentBrowserError`.

| Error | Contract |
| --- | --- |
| `AgentBrowserError` | Catchable base for SDK-owned browser, evidence, installation, persistence, and direct CDP failures. |
| `BrowserError` | Native failure or Python safety rejection. Exposes `action`, `response`, and structured `code`. |
| `ConfirmationRequired` | Paused typed or checked action with a typed `pending` continuation. |
| `StaleRefError` | Expired synchronous ref with `refresh()`. |
| `AsyncStaleRefError` | Expired asynchronous ref with awaitable `refresh()`. |
| `ActionTransitionError` | Mutation completed, then its wait, snapshot, or diff stage failed. |
| `NativeParseError` | A native payload missed a field or shape required by a typed model. |
| `BrowserInstallError` | Browser discovery or installation failed. |
| `RestoreSaveError` | Cleanup completed and persistence failed. Exposes terminal `result`. |

Direct protocol errors live in `agentbrowser.cdp`:

| Error | Contract |
| --- | --- |
| `CDPError` | Base error for Python-owned direct protocol workflows. |
| `CDPClosedError` | Client or controller is closed. |
| `CDPProtocolError` | A protocol method returned an error. |
| `CDPTimeoutError` | A method did not receive a response in time. |
| `CDPTargetNotFoundError`, `CDPFrameNotFoundError`, `CDPContextNotFoundError` | No object matched strict criteria. |
| `CDPTargetAmbiguityError`, `CDPFrameAmbiguityError`, `CDPContextAmbiguityError` | Several objects matched strict criteria. |
| `CDPStaleObjectError` | A cached frame or execution context expired after a page transition. |
| `CDPEvaluationError` | JavaScript threw in the selected context. |

Standard Python exceptions also define public contracts. Invalid options raise `TypeError` or `ValueError`. Operations after close raise `RuntimeError`. Missing optional image or WebSocket dependencies raise `ImportError`. Async close can raise `TimeoutError`.

`BrowserError`, `NativeParseError`, `ActionTransitionError`, `BrowserInstallError`, `RestoreSaveError`, and `CDPError` inherit from `AgentBrowserError`. `ConfirmationRequired` inherits from `BrowserError`. Stale ref errors also inherit from `BrowserError`.

## Embedded skill models

`agentbrowser.skills` returns `Skill`, `SkillPart`, and `SkillFile` dataclasses. A skill records its name, frontmatter description, main content, part metadata, loaded files, and hidden status. A skill file records its relative path and text content.
