# Sessions and lifecycle

A `Browser` controller owns one native session. The native session owns ordered commands, policy, optional restore state, and the [PyO3](https://pyo3.rs/) Rust-to-Python browser object. The native object owns its Rust runtime and helper resources.

## Identity model

| Identity          | Owner                       | Scope                                                          |
| ----------------- | --------------------------- | -------------------------------------------------------------- |
| `Browser` object  | Python application          | One controller lifetime                                        |
| Native session ID | `SessionOptions.session_id` | Native discovery and optional pinned tab binding               |
| Namespace         | `SessionOptions.namespace`  | Control socket or port, restore records, and tab-binding paths |
| Restore key       | `RestoreOptions.key`        | One automatic persistence record                               |
| Tab label         | Application                 | Readable selector inside the session                           |
| CDP target ID     | Browser                     | Stable page-target identity when the browser preserves it      |

A namespace separates native paths. It does not create a separate process or network boundary.

## Synchronous lifecycle

```text
constructed lazy
  -> native session constructed on demand
  -> browser launched or attached
  -> actions ordered
  -> closing
  -> terminal CloseResult or RestoreSaveError
```

Explicit-URL reads can complete before browser launch. `Browser.launch()` and `Browser.attach()` complete their startup path before returning.

`close()` is idempotent and terminal. It releases direct CDP state, retained confirmation input, browser ownership, stream and dashboard resources, and native sidecars. Restore-save failure surfaces after cleanup.

## Asynchronous lifecycle

`AsyncNativeSession` sends calls to one owner thread. The owner holds the synchronous native session and executes commands in queue order.

```text
constructed
  -> owner started
  -> command queued
  -> command active
  -> closing rejects queued work
  -> internal shutdown on owner
  -> owner joined
  -> shared terminal result
```

Cancellation skips queued work that has not started. Active native work completes on the owner. `AsyncBrowser.close()` is single-flight and shields shared shutdown from caller cancellation. The first close call fixes the timeout used by every caller.

A native shutdown timeout raises `TimeoutError`. A worker that remains alive after the join raises `RuntimeError`.

## Restore and abrupt exit

Keyed restore loads during startup, validates through optional URL, text, or JavaScript checks, and saves according to its policy. Native maintenance detects browser exit, drains events, and applies autosave behavior. An explicit Python close returns the final restore and save statuses.

## Dashboard resources

The PyO3 layer owns the stream server, discovery metadata, control metadata, and parent watchdog needed for an external dashboard to observe a Python-owned session.

The dashboard observes. Python retains the browser control channel. The adapter excludes upstream dashboard asset and session-creation ownership from the embedded stream module.

Unix uses a local control socket. Windows uses loopback TCP. The watchdog removes helpers after an abrupt parent exit.
