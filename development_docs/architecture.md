# Architecture

pyagentbrowser composes Python capabilities over a checked command executor and
embeds a pinned [`agent-browser`](https://github.com/vercel-labs/agent-browser)
engine behind an owned Rust interface. [The downstream wrapper model](repository-model.md)
defines the source pin and release identities.

```text
Browser / AsyncBrowser
  | compose browser capabilities
  v
features/
  | Command[T], Executor, AsyncExecutor
  v
execution/   policy, confirmation, lifecycle, document identity
  |
  v
transport/   JSON protocol, native session, async queue
  |
  v
agentbrowser._native                 PyO3 resource ownership
  |
  v
agent-browser-adapter::Engine        owned embedded-engine interface
  |
  v
generated upstream modules           pinned source + agent-browser-build
```

[`PyO3`](https://pyo3.rs/) binds the Rust extension to Python. The generated
modules compile into the adapter. `agent-browser-build` runs during compilation
and keeps source transformations separate from runtime ownership.

## Python ownership

| Owner | Responsibility |
| --- | --- |
| `browser.py`, `browser_async.py` | Public construction, lifecycle access, and capability composition |
| `contracts/` | Shared errors, document identity, JSON response contracts, and decoding primitives |
| `execution/` | Checked dispatch, startup, policy, confirmation continuations, resource ownership, and command effects |
| `transport/` | Native protocol serialization, synchronous sessions, and ordered asynchronous work |
| `features/<capability>/` | Capability API, local models, parameter validation, decoding, and composition |
| `agent.py` | Process-local controller registry and code-mode capability entry point |
| `_agent/` | Installed Agent Plugin resources and guidance |
| `cdp/` | Optional direct Chrome DevTools Protocol connection and context lifetimes |
| `launch.py`, `install.py` | Public startup configuration and browser preparation |

Feature code consumes the internal `Executor` or `AsyncExecutor`. It describes a native
action with `Command[T]` and owns the result decoder. The executor preserves
policy, confirmation, lifecycle, and document identity across that call.
Feature modules keep their own result models and payload builders. Shared
contracts contain values needed across features.

`Browser` and `AsyncBrowser` expose capability factories. Their resource
controllers own native sessions and optional protocol connections. A retained
capability keeps its resource controller alive. Explicit close is terminal for
every capability sharing that controller.

Public types have canonical imports from `agentbrowser`. The package layout
expresses implementation ownership. Read [Python SDK design](python-sdk.md)
for feature placement. Application code composes the public browser, page, and
frame methods.

## One operation through the stack

`browser.page.open(url)` constructs a navigation command on a document executor.
The executor carries the page target into checked dispatch. A lazy controller
first prepares and launches Chrome, then sends navigation through its native
session. Confirmation can pause either action while retaining the return type
and remaining work.

The transport serializes each action into JSON. The PyO3 extension releases the
Python interpreter lock during native execution. `Engine` dispatches into the
generated upstream modules and returns a JSON response. Python records command
effects and applies the feature's decoder.

`browser.native.execute()` preserves the complete response envelope, including
failure and confirmation-required responses. `browser.native.data()` checks
success and returns data or raises the matching SDK error. Both share the
controller's lifecycle and policy.

A ref mutation composes this same execution path with postconditions and a new
snapshot. `Snapshot.document` and `Ref.document` retain the producing document.
The command also carries the captured ref generation. [Evidence and refs](evidence-and-refs.md)
defines partial failures and identity checks.

## Native ownership

| Owner | Responsibility |
| --- | --- |
| `crates/pyagentbrowser` | Python bindings, Tokio runtime, cancellation, maintenance scheduling, dashboard resources, and teardown |
| `crates/agent-browser-adapter` | `Engine`, engine configuration, confirmation, and document behavior required by the SDK |
| `crates/agent-browser-build` | Upstream module registry, feature transformations, protocol generation, and source audit reports |
| `third_party/agent-browser` | Immutable pinned engine implementation |

The extension depends on the adapter's owned `Engine` interface. Upstream
manager and daemon types stay inside the adapter. A changed upstream state
layout therefore reaches one runtime boundary before it reaches Python.

Source rewrites have names, expected anchor counts, and explicit dependencies
when they overlap earlier generated code. The build report records input files
and applied patches. These checks detect source drift. Compilation and browser
tests establish whether an upstream candidate still satisfies runtime contracts.
See [Generated adapter](generated-adapter.md) and [Maintenance](maintenance.md).

## Add a capability at its owner

| Change | Primary owner | Verification |
| --- | --- | --- |
| Typed workflow over existing actions | `features/<capability>/` | Public result, validation, confirmation, sync/async parity |
| Shared dispatch or lifecycle rule | `execution/` | Every affected entry path, cancellation, terminal close |
| Wire envelope or native queue | `transport/` | Protocol errors, ordering, interrupted and queued work |
| Rust-owned process or helper lifetime | `crates/pyagentbrowser` | Native boundary and platform cleanup |
| Embedded engine behavior | `crates/agent-browser-adapter` | Adapter contract and real-browser seam |
| Upstream source adaptation | `crates/agent-browser-build` | Anchor/dependency audit, compilation, affected runtime seam |
| Artifact inputs or provenance | `scripts/artifacts/` and packaging manifests | Wheel and source-distribution install proof |

Use `make check` for the normal handoff. Add the boundary-specific checks from
[Testing](testing.md) when a change crosses the native, browser, or artifact
boundary.
