# Architecture

pyagentbrowser embeds the native `agent-browser` engine inside a Python process
and gives Python callers a typed, agent-oriented browser contract.

The Python SDK adds four owned behaviors above the native command set:

1. `Snapshot`, `Ref`, and `ActionResult` bind browser actions to reproducible
   before-and-after evidence.
2. Namespaces such as `browser.page`, `browser.find`, `browser.capture`, and
   `browser.cdp` expose Python types, validation, and lifecycle semantics.
3. Domain allowlists, confirmation continuations, session status, async
   ownership, and terminal close evidence stay consistent across native actions.
4. ABI3 wheels embed one pinned engine with recorded provenance and installed
   artifact verification.

## Dependency direction

```text
User code
  |
  v
Browser / AsyncBrowser, Snapshot / Ref, Query
  |  typed inputs, policy, lifecycle, evidence, result decoding
  v
NativeSession / AsyncNativeSession
  |  ordered JSON command protocol
  v
agentbrowser._native (PyO3)
  |  native resource ownership and Python boundary
  v
agent-browser-adapter
  |  fail-closed source adaptation generated in OUT_DIR
  v
third_party/agent-browser
     pinned upstream source and native command behavior
```

Dependencies and behavior move downward through this path. Native results move
upward as validated models or typed SDK errors. The Python layer may use every
native action through `browser.native`, so a focused high-level API never blocks
advanced use.

The direct CDP path branches from `Browser` into `agentbrowser.cdp`. It resolves
the active native target, then uses a WebSocket connection for frames, execution
contexts, evaluation, and raw CDP commands. Navigation and tab changes
invalidate cached CDP handles.

## Ownership map

| Surface | Owner | Responsibility |
| --- | --- | --- |
| Public controller | `browser.py`, `browser_async.py` | Startup, close, namespaces, confirmation continuations, result decoding |
| Agent evidence | `agent.py`, `agent_async.py`, `models.py` | Snapshots, refs, waits, diffs, transition results, typed errors |
| Capability namespaces | `domains.py`, `domains_async.py`, `query.py`, `query_async.py` | Stable Python workflows over native actions |
| Safety boundary | `_allowlist.py`, `session.py`, `session_async.py` | Domain policy, command preparation, ordered execution, response envelopes |
| Native extension | `crates/pyagentbrowser` | PyO3 module, native sessions, embedded data, sidecar lifecycle |
| Upstream adaptation | `crates/agent-browser-adapter` | Build-time source copy and narrow compatibility rewrites |
| Native engine | `third_party/agent-browser` | Pinned upstream implementation |
| Artifact proof | `scripts/package_smoke.py`, `scripts/verify-install-artifacts.py` | Payload, metadata, ABI, extras, and clean-install contracts |

## One action through the stack

`browser.open("example.com")` follows this path:

1. `Browser.open()` delegates to `Page.open()`, which normalizes the URL and
   requests lazy launch when needed.
2. `Browser._command()` preserves continuation and lifecycle behavior.
3. `NativeSession.execute()` applies the allowlist, assigns a command id, and
   serializes one JSON command.
4. `NativeBrowser.execute_json()` crosses PyO3 while allowing the native work to
   run outside the Python interpreter lock.
5. The generated adapter invokes the pinned engine.
6. Python validates the response envelope, updates lifecycle state, and decodes
   the declared return type.

A snapshot ref action adds evidence around the same path. It keeps the source
snapshot, executes the mutation, applies the requested waits, captures the next
snapshot with the same `SnapshotSpec`, and returns their diff. If a later stage
fails, `ActionTransitionError` records that the mutation already completed.

## Lifecycle ownership

- `Browser()` is lazy. The first browser-dependent command launches the local
  browser process. Explicit-URL reads may complete before browser launch.
- `Browser.launch()` and `Browser.attach()` complete startup before returning.
- `AsyncBrowser` owns one ordered native worker thread. Cancellation and close
  settle queued calls through that owner.
- `browser.session.status()` decodes native launch, restore, and persistence
  state without launching Chrome.
- `close()` is idempotent and terminal. It releases browser, stream, dashboard,
  CDP, retained confirmation input, and sidecar resources, then returns the
  native save result. Async callers share one close operation.
- A restore-save failure surfaces after cleanup through `RestoreSaveError` and
  preserves the terminal `CloseResult`.
- Confirmation keeps the initiating operation's return type and remaining work.
  A confirmed ref action still performs its waits and evidence capture.

## Where a change belongs

| Change | Primary location | Co-change |
| --- | --- | --- |
| Python workflow or return type | `src/agentbrowser/` | Sync and async counterpart, SDK tests, docs, example |
| Native payload construction | `command_params.py` or session layer | SDK contract test and allowlist review |
| New stable native capability | Python namespace | Raw-native compatibility, sync and async parity |
| PyO3 process or resource behavior | `crates/pyagentbrowser/` | Native smoke and integration tests |
| Upstream embedding incompatibility | Adapter `build.rs` rewrite | Anchor failure, Rust smoke, pinned upstream inspection |
| Upstream feature or bug | Upstream submodule update | Provenance, adapter, locks, Python surface when warranted |
| Wheel or sdist content | `pyproject.toml` and packaging scripts | Package contract and clean-install proof |

Keep one Python distribution and one public import package. Release one wheel
for each supported platform target. The layers separate ownership and testing
concerns while shipping as one coherent SDK.
