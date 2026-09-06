# Architecture

pyagentbrowser is a downstream wrapper that embeds a pinned `agent-browser`
engine inside a Python process and gives Python callers a typed, agent-oriented
browser contract. The [downstream wrapper model](repository-model.md) defines
the upstream pin, independent versions, and ownership rules.
[PyO3](https://pyo3.rs/) provides the Rust bindings that expose the native
extension to Python.

The Python SDK adds four owned behaviors above the native command set:

1. `Snapshot`, `Ref`, and `ActionResult` bind browser actions to reproducible
   before-and-after evidence.
2. Namespaces such as `browser.page`, `browser.find`, `browser.capture`, and
   `browser.cdp` expose Python types, validation, and lifecycle semantics.
3. Domain containment, typed confirmation continuations, session status, async
   ownership, and terminal close evidence stay attached to every checked native
   action.
4. Wheels built against [Python's stable application binary interface](https://docs.python.org/3/c-api/stable.html)
   embed one pinned engine with recorded provenance and installed artifact
   verification.

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
agentbrowser._native (PyO3 Rust bindings for Python)
  |  native resource ownership and Python boundary
  v
agent-browser-adapter
  |  fail-closed source adaptation generated in Cargo OUT_DIR
  v
third_party/agent-browser
     pinned upstream source and native command behavior
```

Dependencies and behavior move downward through this path. Checked results move
upward as validated models or typed SDK errors. `browser.native.execute()` keeps
the complete `BrowserResponse` envelope, including unsuccessful and
confirmation-required responses. `browser.native.data()` follows the checked
path and returns data or raises the matching SDK error.

The direct [Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/)
path branches from `Browser` into `agentbrowser.cdp`. It resolves the active
native target, then uses a persistent WebSocket protocol connection for frames,
execution contexts, evaluation, and raw methods. Navigation and tab changes
invalidate cached direct CDP frame and execution-context handles. Read
[Direct CDP](direct-cdp.md) for that second command plane.

## Ownership map

| Surface               | Owner                                                                          | Responsibility                                                                      |
| --------------------- | ------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------- |
| Public controller     | `browser.py`, `browser_async.py`                                               | Startup, close, namespaces, confirmation continuations, result decoding             |
| Agent evidence        | `_evidence.py`, `agent_async.py`, `models.py`                                  | Snapshots, refs, waits, diffs, transition results, typed errors                     |
| Code-mode capability  | `agent.py`, Agent Plugin resources                                             | Durable scratchpad connections, dynamic help, and version-matched Python guidance  |
| Capability namespaces | `domains.py`, `domains_async.py`, `query.py`, `query_async.py`                 | Stable Python workflows over native actions                                         |
| Browser installation  | `install.py`                                                                   | Executable discovery and isolated Chrome for Testing preparation                    |
| Safety boundary       | `launch.py`, `_allowlist.py`, `session.py`, `session_async.py`, native adapter | Launch constraints, domain containment, confirmation replay, and response filtering |
| Embedded skills       | `skills.py`, `crates/pyagentbrowser/build.rs`                                  | Package the pinned upstream skill tree and expose its files to Python               |
| Native extension      | `crates/pyagentbrowser`                                                        | PyO3 module, native sessions, embedded skills, and sidecar lifecycle                |
| Upstream adaptation   | `crates/agent-browser-adapter`                                                 | Build-time module registry and narrow compatibility rewrites                        |
| Native engine         | `third_party/agent-browser`                                                    | Pinned upstream implementation                                                      |
| Artifact proof        | `scripts/package_smoke.py`, `scripts/verify-install-artifacts.py`              | Payload, metadata, ABI, Agent Plugin, extras, and clean-install contracts           |

[Native extension](native-extension.md) expands the Rust runtime and helper
resource ownership. [Embedded resources](embedded-resources.md) traces skill
data, protocol inputs, provenance, and notices into release artifacts.

## A high-level operation through the stack

Three terms keep this path precise:

- A high-level operation is one public Python method call.
- A native action is one engine behavior such as `launch` or `navigate`.
- A JSON command is one serialized invocation of a native action.

`Browser().open("example.com")` can contain two native actions:

1. `Browser.open()` delegates to `Page.open()`, which normalizes the URL.
2. A lazy controller first sends a `launch` action. Confirmation can pause this
   action before navigation begins.
3. The controller then sends a `navigate` action. An already-launched controller
   begins at this step.
4. `NativeSession.execute()` applies the allowlist, assigns a command ID, and
   serializes each JSON command.
5. `NativeBrowser.execute_json()` crosses PyO3 while allowing native work to
   run outside the Python interpreter lock.
6. The generated adapter invokes the pinned engine.
7. Python updates lifecycle state, then preserves the raw envelope or checks and
   decodes the declared return type.

A snapshot ref action adds evidence around the same path. It keeps the source
snapshot, executes the mutation, applies the requested waits, captures the next
snapshot with the same `SnapshotSpec`, and returns their diff. If a later stage
fails, `ActionTransitionError` records that the mutation already completed.

[Evidence and refs](evidence-and-refs.md) defines snapshot scope, transition
ordering, stale-ref recovery, and partial-failure semantics.

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

Read [Sessions and lifecycle](sessions-and-lifecycle.md) for the controller,
native session, process, identity, async owner, and sidecar state machines. Read
[Safety](safety.md) for the ordered containment and confirmation path.

## Where a change belongs

| Change                             | Primary location                       | Co-change                                                 |
| ---------------------------------- | -------------------------------------- | --------------------------------------------------------- |
| Python workflow or return type     | `src/agentbrowser/`                    | Sync and async counterpart, SDK tests, docs, example      |
| Native payload construction        | `command_params.py` or session layer   | SDK contract test and allowlist review                    |
| New stable native capability       | Python namespace                       | Raw-native compatibility, sync and async parity           |
| PyO3 process or resource behavior  | `crates/pyagentbrowser/`               | Native smoke and integration tests                        |
| Upstream embedding incompatibility | Adapter `build.rs` rewrite             | Anchor failure, Rust smoke, pinned upstream inspection    |
| Upstream feature or bug            | Upstream submodule update              | Provenance, adapter, locks, Python surface when warranted |
| Wheel or sdist content             | `pyproject.toml` and packaging scripts | Package contract and clean-install proof                  |

Keep one Python distribution and one public import package. Release one wheel
for each supported platform target. The layers separate ownership and testing
concerns while shipping as one coherent SDK.

The [contributor documentation index](index.md) routes each implementation
boundary to its design contract and validation evidence.
