# Python SDK

This package owns the public Python contract around the embedded engine.

## Place behavior

- `browser.py` and `browser_async.py` own controller lifecycle, confirmation
  continuations, typed decoding, and namespace composition.
- `agent.py` and `agent_async.py` own snapshots, refs, transition evidence, and
  stale-ref recovery.
- `domains.py` and `domains_async.py` own focused capability namespaces.
- `session.py` and `session_async.py` own ordered JSON protocol execution.
- `models.py` owns public values and errors. `command_params.py` owns native
  payload construction. `cdp/` owns the optional direct CDP path.

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
