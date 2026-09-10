# Direct CDP

The optional `agentbrowser.cdp` package opens a direct
[Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/)
WebSocket beside the native action path. It serves frame, execution-context,
extension, and raw protocol workflows that need a persistent protocol session.

## Two command paths

```text
Browser controller
  | native action                 | direct CDP method
  v                               v
NativeSession JSON protocol       CDPController WebSocket
  |                               |
  +---------- same browser -------+
```

The native path remains authoritative for launch, policy, session state,
high-level actions, and close. The direct CDP path asks the native engine for
the current browser WebSocket URL, attaches to a page target, and owns its
protocol connection until invalidation or close.

Direct CDP forms a second command plane within the same browser session. New
behavior must identify which plane owns navigation, target selection, cached
handles, policy enforcement, and teardown.

## Safety boundary

`browser.cdp.send()` writes protocol methods directly to Chrome. It does not
cross `NativeSession`, so Python command preparation, action-policy rules, and
confirmation do not inspect its method or parameters. The browser-level network
filter remains installed on a locally launched contained context, but arbitrary
protocol methods can change browser state that the controller does not track.

Prefer typed namespaces or `browser.native` for navigation, target creation,
state changes, and browser lifecycle. Those paths apply the session policy and
update controller state. Treat raw CDP methods as an escape hatch whose caller
owns their protocol and lifecycle consequences.

## Connection and target selection

The controller launches the browser lazily when needed, reads `cdp_url` through
the checked native path, and constructs one synchronous or asynchronous client.
The `websockets` dependency is imported at first connection so the base package
can operate without the `cdp` extra.

A page session resolves one target by explicit target ID, exact URL, tab label,
or the browser's current URL. Ambiguous matches raise a typed error. The
controller attaches with flattened sessions, enables page and runtime events,
then builds its frame tree and execution-context index.

## Generations and stale handles

Frames and execution contexts are generation-bound values. Controller
invalidation increments the affected page-session generation. A handle from an
older generation raises `CDPStaleObjectError` before it sends a method against
a new document.

Native actions that navigate, switch tabs, close tabs, create windows, or
replace content invalidate the cached direct CDP page session. Launch and close
reset the controller connection. Keep
`src/agentbrowser/contracts/actions.py` aligned when a native action changes
document or target identity.

## Events and responses

CDP clients assign monotonically increasing IDs and read messages until the
matching response arrives. Unmatched event messages remain queued for the page
session. Protocol errors, timeout, closed transport, missing target, ambiguous
target, evaluation failure, and stale handles map to distinct Python errors.

Both synchronous and asynchronous clients implement the same protocol
semantics. The async client serializes reads with a lock so concurrent callers
cannot consume each other's responses.

## Review checklist

1. Choose native action or direct CDP ownership explicitly.
2. Preserve lazy launch and controller close behavior.
3. Define how the operation selects a target, frame, and execution context.
4. Invalidate generation-bound state after document or target changes.
5. Keep synchronous and asynchronous contracts aligned.
6. Keep the optional dependency diagnostic at the connection boundary.
7. Review whether a raw method bypasses required policy or controller state.
8. Add real-browser evidence for target, frame, or lifecycle behavior.

Use `make test-sdk` for protocol parsing, resolution, stale-handle, and parity
contracts. Add `make test-integration` for browser-backed behavior.
