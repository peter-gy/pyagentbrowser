# Native extension

`crates/pyagentbrowser` builds the PyO3 module imported as
`agentbrowser._native`. It turns one Python native session into an in-process
Rust engine with owned runtime, maintenance, dashboard, and cleanup resources.

## Boundary contract

The Python-facing surface is deliberately small:

| Entry point                   | Contract                                                                 |
| ----------------------------- | ------------------------------------------------------------------------ |
| `NativeBrowser(options_json)` | Construct native state and its Tokio runtime from validated JSON options |
| `execute_json(command_json)`  | Execute one ordered JSON command and return one JSON response envelope   |
| `browser_cache_dir()`         | Report the upstream browser cache location                               |
| `find_chrome_executable()`    | Run native browser discovery                                             |
| `_run_browser_install()`      | Invoke the bundled upstream installer                                    |
| `skill_data_json()`           | Return build-time embedded skill data                                    |

Keep Python workflow semantics above this boundary. Add native entry points
when the value depends on Rust-owned engine state, build-time data, process
ownership, or platform integration.

## Runtime ownership

Each `NativeBrowser` owns:

- One multithreaded Tokio runtime.
- One mutex-protected upstream `DaemonState`.
- One periodic maintenance task.
- Optional dashboard stream and sidecar resources.

`execute_json()` parses the command, releases the Python interpreter lock while
Rust blocks on the async engine, annotates owned error codes, and serializes the
complete response. The native mutex serializes access to state inside that
object. The Python async layer adds one owner thread and an ordered command
queue, so an event loop never directly enters the synchronous native object.

## Maintenance loop

The maintenance task calls the upstream browser-state maintainer on a short
tick. That maintainer observes browser exit, drains process events, and applies
automatic saved-state behavior at the configured interval.

The task belongs to the native object because it must continue while Python is
idle. Shutdown signals and joins it before native state is released.

## Browser discovery and installation

`agentbrowser.install.ensure_installed()` resolves a local executable in this
order:

1. `AGENT_BROWSER_EXECUTABLE_PATH` when it names an existing file.
2. A browser in the upstream cache or supported system locations.
3. Chrome for Testing downloaded by the bundled native installer.

The installer runs in a child Python process. This isolates the installer-owned
Rust runtime from a live controller and lets Python preserve terminal output or
capture a concise failure diagnostic. `AsyncBrowser` sends installation work to
a worker thread so browser preparation does not block its event loop.

Explicit CDP attachment and other launches that select an externally owned
browser skip automatic installation. Controller code decides this before the
first native launch.

## Dashboard and helper resources

Dashboard mode starts the upstream stream server while retaining browser
control in Python. The native extension publishes discovery metadata and an
observation-only control bridge for the external dashboard CLI.

Unix uses a local socket. Windows uses loopback TCP plus port metadata. A child
watchdog watches the Python parent and removes sidecar files after abrupt exit.
Normal shutdown stops the stream, wakes and joins the bridge, terminates the
watchdog, and removes discovery files.

## Teardown order

Explicit Python close sends the internal native shutdown action and records its
terminal result. Dropping the native object is a final cleanup path:

1. Stop and join maintenance.
2. Stop dashboard streaming and sidecars.
3. Send the internal native shutdown action.
4. Drop the Rust runtime and state.

Cleanup remains idempotent because explicit close, context-manager exit,
garbage collection, and abrupt browser exit can converge on the same resources.

## Validation

- Use `make test-native` for construction, JSON execution, embedded data,
  dashboard metadata, and helper cleanup.
- Use `make rust-check rust-test` for runtime and platform implementation.
- Use `make test-integration` when behavior depends on Chrome or process state.
- Use `make package` when the extension ABI, build inputs, or bundled resources
  change.

[Sessions and lifecycle](sessions-and-lifecycle.md) describes the Python and
async state machines around this object. [Generated adapter](generated-adapter.md)
describes how the linked upstream library is produced.
