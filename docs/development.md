# Development

## Setup

```bash
make install
```

This initializes the upstream submodule, installs Python dependencies, and
builds the native extension in editable mode.

## Repository Map

- `src/agentbrowser/`: Python SDK.
- `crates/pyagentbrowser/`: PyO3 Rust crate for the native extension.
- `crates/agent-browser-adapter/`: first-party Rust adapter and generated
  upstream source shims.
- `third_party/agent-browser/`: clean upstream submodule.
- `examples/`: maintained public API examples.
- `scripts/`: structured helper checks used by Make targets.

## Gates

Use the Makefile as the source of truth:

```bash
make help
make check
```

Do not duplicate the full gate list in docs. If a gate changes, update
the Makefile first.

## Public API Changes

When changing public API:

1. Update or add an example in `examples/`.
2. Update the closest docs page.
3. Add tests for both sync and async surfaces when both exist.
4. Run `make check`. Add `make test-integration` for real browser behavior and
   `make package` for artifact or packaging changes.

Keep the public surface namespaced. Prefer `browser.page`, `browser.find`,
`browser.capture`, `browser.active_frame`, `browser.cdp`, `browser.scripts`,
and domain namespaces over new direct `Browser` helpers.

## Upstream Submodule

Do not edit `third_party/agent-browser`. Upstream integration belongs in
`crates/agent-browser-adapter`, `crates/pyagentbrowser`, and the Python
wrapper. See [internals/upstream.md](internals/upstream.md).
