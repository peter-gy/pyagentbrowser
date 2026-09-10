# Python SDK

This package owns the public Python contract around the embedded engine.

## Place behavior

- `browser.py` and `browser_async.py` compose public capabilities and expose
  lifecycle operations through owned resource controllers.
- `features/<capability>/` owns its API, local models, parameter validation,
  decoders, and composed workflows. Use `Executor` and `AsyncExecutor` for
  checked commands and document identity.
- `execution/` owns resource controllers, confirmation, command effects,
  policy, and lifecycle. `transport/` owns JSON serialization and ordered native
  sessions. `contracts/` holds errors and values shared across features.
- `integrations/` owns host binding, Python code
  execution, image tool content, managed tasks, and packaged guidance.
  `agent.py` owns the process-local controller registry and exposes the
  code-mode capability entry point.
- `cdp/` owns the optional direct Chrome DevTools Protocol path.

Keep high-level workflow semantics in Python. Put native process integration or
upstream source adaptation in the Rust crates.

## Public API rules

- Design the smallest realistic call first. Keep common notebook and REPL use
  flat, with explicit `close()` available and lazy startup predictable.
- Add a typed namespace when Python owns stable semantics, validation, return
  types, or lifecycle. Route uncommon native actions through `browser.native`
  so the typed surface stays focused on stable workflows.
- Preserve method names, parameter meaning, return types, errors, cancellation,
  and close behavior across sync and async surfaces.
- Keep lifecycle terminal. `close()` is idempotent, commands after close fail,
  and async shutdown settles queued work before the owner thread exits.
- Decode required native fields strictly. Surface protocol drift as a typed SDK
  error with the action and failing field.
- Export new public objects from `agentbrowser.__init__` and keep the API docs
  and nearest runnable example aligned.

## Validation

- Use `make test-sdk` for Python contract changes.
- Add `make test-native` when behavior crosses the PyO3 or adapter boundary.
- Add `make test-integration` when the contract depends on a real browser, CDP,
  process lifetime, or page transition.
- Run `make check` before handoff.
