# Contributing

## Setup

```bash
make install
```

## Command Map

| Change type                | Target                    |
| -------------------------- | ------------------------- |
| Normal Python/docs handoff | `make check`              |
| Real browser behavior      | `make test-integration`   |
| Rust-only work             | `make rust-check`         |
| Wheel/sdist boundaries     | `make package`            |
| Release readiness          | `make check-release`      |

## Repository Boundaries

- `third_party/agent-browser` is a clean upstream submodule. Do not edit files
  inside it.
- `crates/pyagentbrowser` owns the PyO3 native extension crate.
- `crates/agent-browser-adapter` owns adapter shims and generated source
  rewrites.
- `src/agentbrowser` owns the Python public API.
- `examples` and `docs` must track the actual public API, not planned helpers.

Native behavior changes must be generated in `OUT_DIR`, covered by tests, and
kept out of `third_party/agent-browser`.

## Docs And Examples

When changing public API:

1. Update the relevant example in `examples/`.
2. Update the closest docs page in `docs/`.
3. Run `make check` or the smallest relevant gate from the command map.
