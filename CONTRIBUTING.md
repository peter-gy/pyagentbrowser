# Contributing

## Setup

```bash
make install
```

## Command Map

| Change type                | Target                      |
| -------------------------- | --------------------------- |
| Upstream engine pin        | `make update-upstream`      |
| Python SDK contract        | `make test-sdk`             |
| PyO3 or adapter boundary   | `make test-native`          |
| Package contract           | `make test-package`         |
| Normal Python/docs handoff | `make check`                |
| Real browser behavior      | `make test-integration`     |
| Rust-only work             | `make rust-check rust-test` |
| Wheel/sdist boundaries     | `make package`              |
| Release readiness          | `make check-release`        |

## Repository Boundaries

- `third_party/agent-browser` is a clean upstream submodule. Do not edit files
  inside it.
- `crates/pyagentbrowser` owns the PyO3 native extension crate.
- `crates/agent-browser-adapter` owns adapter shims and generated source
  rewrites.
- `src/agentbrowser` owns the Python public API.
- `examples` and `docs` must track the actual public API, not planned helpers.

Adaptations of upstream native source must be generated in `OUT_DIR`, covered by
tests, and kept out of `third_party/agent-browser`. First-party PyO3 behavior
lives in `crates/pyagentbrowser`.

Read [the architecture guide](development_docs/architecture.md) for the runtime
path and ownership boundaries. Read [the maintenance guide](development_docs/maintenance.md)
before changing the upstream pin, generated adapter, package metadata, CI, or
release flow.

## Docs And Examples

When changing public API:

1. Update the relevant example in `examples/`.
2. Update the closest docs page in `docs/`.
3. Use the smallest relevant gate from the command map while iterating.
4. Run `make check` before handoff. Add `make test-integration` or `make package`
   when the changed boundary requires it.
