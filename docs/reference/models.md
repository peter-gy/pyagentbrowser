---
title: Models and errors
description: Typed results, evidence records, browser state, network data, WebMCP results, saved flows, and error contracts.
---

# Models and errors

Public result models are frozen dataclasses unless this page states otherwise. Most preserve the complete native mapping in a `raw` field.

## Evidence models

| Model | Fields and contract |
| --- | --- |
| `SnapshotSpec` | `selector`, `interactive`, `compact`, `max_depth`, and `urls` define one accessibility capture. |
| `Snapshot` | `text`, `origin`, `url`, `spec`, `refs`, `generation`, and `raw`, plus ref lookup, refresh, and diff operations. |
| `Ref` | Snapshot-scoped `id`, selector, role, name, hint, source snapshot, document, and native metadata. |
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
| `document` | The producing `Page` or `Frame`, retained for scoped actions and refresh. |
| `refs` | Mapping of ref IDs to bound `Ref` objects. |
| `raw` | Native snapshot response mapping. |
| `ref(ref_id)` | Resolve an exact ID such as `e1` or `@e1`. |
| `one(*, role=None, name=None, contains=None, hint=None, exact=False)` | Return exactly one ref or raise `LookupError`. `hint` matches a substring of `Ref.hint`. |
| `all(*, role=None, name=None, contains=None, hint=None, exact=False)` | Return every matching ref as a tuple. |
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
| `refresh(*, role=None, name=None, contains=None, exact=True)` | Resolve accessible metadata against a fresh snapshot. Among several matches, select the one that carries this ref's hint. |

`Ref` also exposes its source `snapshot`, `document`, ID without `@`, native selector, accessible role, accessible name, and raw metadata. Native `stale_ref` and `unknown_ref` failures become `StaleRefError`.

`Ref.hint` is the engine's text for a control whose accessible name is empty or shared with another ref in the snapshot, such as `icon:lucide-trash; in:Invoice 42`. It is `None` for every other ref.

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
| `Screenshot` | File path, format, scope, annotations, raw capture data, bytes, image content, copying, image loading, and notebook display. |
| `ScreenshotObservation` | Change state, revision, changed-pixel ratio, threshold, document scope, raw data, and an optional written `Screenshot`. |
| `ConsoleMessage` | Console method type, rendered text, and JSON-serializable call arguments. |
| `PageError` | Uncaught exception text with optional source URL, line, and column. |

### `Screenshot`

| Member | Contract |
| --- | --- |
| `bytes()` | Read the captured file bytes. |
| `content()` | Return image bytes, MIME type, and source path. |
| `save(path)` | Copy the file and return a new `Screenshot` for the target path. |
| `pil(*, mode=None)` | Load a Pillow image and optionally convert its mode. |
| `image` | Lazily load and cache the Pillow image. |
| `annotations` | Ref number, role, accessible name, and bounding box for annotated elements. |

`pil()` and `image` require the `images` extra. PNG and JPEG captures expose
notebook display data from their file bytes.

`ImageContent(data, media_type, source=None)` carries non-empty image bytes,
an image MIME type, and an optional source path. `Screenshot.content()`
constructs it from the captured file.

`ScreenshotObservation.path` returns the written image path for a changed
capture and `None` for an unchanged revision. Its `screenshot` field provides
the complete `Screenshot` when an image was written.

## Session, tab, and storage models

| Model | Fields and contract |
| --- | --- |
| `CloseResult` | `closed`, restore status, save status, state path, save error, `unsaved_flow_steps`, and raw terminal data. |
| `SessionStatus` | Native identity, socket path, background PID, browser launch state, page count, engine, compatibility, restore status, skipped restore origins, restore checks, save state, and raw data. |
| `SessionId` | Derived session string, scope, source path, and hash. |
| `TabInfo` | Native ID, URL, title, label, active state, stable target ID, and raw data. A tab from `tabs.new()` has an empty title when the engine creates it without navigating. |
| `TabSwitchResult` | Selected tab fields plus `revived` and `dialog_blocked`. |
| `TabCloseResult` | Closed tab fields plus `closed` and `active_tab_revived`. |
| `Cookie` | Name, value, domain, path, expiry in epoch seconds (`-1` for a session cookie), `http_only`, `secure`, `session`, optional same-site value, and raw data. |
| `StateLoadResult` | Loaded state path and the saved origins whose Web Storage was skipped. |

Restore status values are `load_failed`, `loaded`, `loaded_but_invalid`, `missing`, `not_configured`, and `pending`.

Save status values are `disabled`, `error`, `invalid_policy`, `no_browser`, `not_attempted`, `not_configured`, `saved`, and `skipped_restore_failed`.

## Network models

| Model | Fields and contract |
| --- | --- |
| `NetworkRequest` | ID, URL, method, resource type, timestamp, request headers, optional status, response headers, MIME type, post data, response body, and raw data. `response_body` is set by `network.request()`. |
| `RouteResponse` | Optional status, body, content type, headers, and CORS `allow_origin` for one registered response. |
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

## Flow models

| Model | Fields and contract |
| --- | --- |
| `FlowRecording` | `steps`, `last_save` (the last step sequence a save covered, `0` before the first), `unsaved` step count, and raw data. |
| `FlowStep` | `seq`, `command` text, page `url` after the command, tagged `requests` count, `ok`, `saved`, and raw data. |
| `SavedFlow` | `name`, `origin` host, `step_count`, `requests`, `output` request ID, `params`, `detected_params`, `references`, `writes`, `gaps`, `dropped_headers`, `verified`, file `path`, `from_step`, `to_step`, optional `reach_note`, and raw data. |
| `FlowRequest` | Request `id` such as `s1r1`, `method`, `url` with `{{name}}` parameter slots, recorded response `bytes`, and raw data. |
| `FlowWrite` | Write `id`, `method`, `url`, `kind` (`explicit` or `suspected`), `step`, and raw data. |
| `FlowGap` | `step`, `command`, and the `reason` the command produced no saved request. |
| `FlowRun` | `name`, `origin`, `verified`, `duration_ms`, `steps`, JSON `data`, `empty`, optional `drift`, optional `save_error`, and raw data. |
| `FlowRunStep` | Request `id`, `step`, answering `tier`, HTTP `status`, `duration_ms`, `fell_back` attempts, and raw data. |
| `FlowFallback` | `tier` and `error` of an attempt that an earlier tier failed. |
| `FlowDrift` | `tier`, `step`, and `reason` for a response whose shape differs from the recording. |
| `FlowSummary` | `name`, `origin`, `valid`, `params`, recorded `examples`, `description`, JSON `input_schema`, `param_sources`, `item_fields`, `recorded_on` URL, `provenance`, `verified_at` timestamp or `None`, and raw data. |

A flow tier is `http`, `page`, or `replay`. `FlowRun.data` is the output request's JSON body, or `{"list", "total", "matched", "items"}` when `where`, `fields`, or `limit` shaped a list.

`FlowRunError` is a `BrowserError` raised by `flows.run()` when the site stops a run. It exposes `status`, `flow`, `step`, optional `http_status`, optional `retry_after`, and `save_error` when the engine could not update the flow file. `status` is one of `auth_expired`, `credential_not_sendable`, `request_signed`, `rate_limited`, `blocked`, `outcome_unknown`, `write_applied`, `address_refused`, and `drifted`.

## Native response model

`BrowserResponse` is the complete envelope returned by `browser.native.execute()`:

| Field | Contract |
| --- | --- |
| `id` | Native JSON command ID. |
| `action` | Native action name. |
| `success` | Whether the action succeeded. |
| `data` | Raw response data. |
| `warning` | Optional native warning. Typed methods and `native.data()` emit it as an `EngineWarning`. |
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
| `FlowRunError` | The site stopped a saved-flow run. Exposes `status`, `flow`, `step`, `http_status`, and `retry_after`. |
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

`EngineWarning` is a `UserWarning` subclass. Typed methods and `browser.native.data()` emit it with `warnings.warn` when a response carries a native warning, before they return or raise. See [The engine reports a warning](/troubleshooting#the-engine-reports-a-warning).

Standard Python exceptions also define public contracts. Invalid options raise `TypeError` or `ValueError`. Operations after close raise `RuntimeError`. Missing optional image or WebSocket dependencies raise `ImportError`. Async close can raise `TimeoutError`.

`BrowserError`, `NativeParseError`, `ActionTransitionError`, `BrowserInstallError`, `RestoreSaveError`, and `CDPError` inherit from `AgentBrowserError`. `ConfirmationRequired` and `FlowRunError` inherit from `BrowserError`. Stale ref errors also inherit from `BrowserError`.

## Embedded skill models

`agentbrowser.skills.get()` returns a frozen `Skill` dataclass with its name, frontmatter description, hidden flag, and relative part paths. `Skill.references` lists the parts directly inside `references/` and `templates/`. `Skill.read(path)` returns one part's text, where a reference also answers to its file name or stem, and `Skill.markdown(full=False)` renders the skill.
