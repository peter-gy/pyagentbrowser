# Contributing

## Setup

```bash
make install
```

Use `make help` for the maintained command list.

## Command Map

| Change type                | Target                    |
| -------------------------- | ------------------------- |
| Normal Python/docs handoff | `make check`              |
| Real browser behavior      | `make test-integration`   |
| Python version support     | `make test-python-matrix` |
| Rust-only work             | `make rust`               |
| Wheel/sdist boundaries     | `make package`            |
| Release readiness          | `make check-release`      |

## Repository Boundaries

- `third_party/agent-browser` is a clean upstream submodule. Do not edit files
  inside it.
- `crates/pyagentbrowser` owns the PyO3 native extension crate.
- `crates/agent-browser-adapter` owns adapter shims and generated source
  rewrites.
- `src/pyagentbrowser` owns the Python public API.
- `examples` and `docs` must track the actual public API, not planned helpers.

Native behavior changes are allowed only as documented Native Safety Patches.
See [docs/adr/0001-native-safety-patches.md](docs/adr/0001-native-safety-patches.md)
and [docs/internals/upstream.md](docs/internals/upstream.md).

## Docs And Examples

When changing public API:

1. Update the relevant example in `examples/`.
2. Update the closest docs page in `docs/`.
3. Run `make docs`, `make examples`, and the smallest relevant gate from the
   command map.

Do not duplicate long quality-gate lists in docs. Link to `make help` or this
file instead.
