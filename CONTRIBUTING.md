# Contributing

## Setup

```bash
make install
```

## Command map

| Change type                | Target                      |
| -------------------------- | --------------------------- |
| Upstream engine pin        | `make update-upstream`      |
| Python SDK contract        | `make test-sdk`             |
| PyO3 or adapter boundary   | `make test-native`          |
| Package contract           | `make test-package`         |
| Normal Python/Rust handoff | `make check`                |
| Documentation site        | `make docs-check`           |
| Real browser behavior      | `make test-integration`     |
| Rust-only work             | `make rust-check rust-test` |
| Wheel/sdist boundaries     | `make package`              |
| Release readiness          | `make check-release`        |

## Repository boundaries

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

Read [the contributor documentation index](development_docs/index.md) for the
runtime, safety, adapter, testing, docs, packaging, and release contracts.

## Docs and examples

When changing public API:

1. Update the relevant example in `examples/`.
2. Update the closest docs page in `docs/`.
3. Run `make docs-check` for public documentation changes.
4. Use the smallest implementation gate from the command map while iterating.
5. Run `make check` before handoff. Add `make test-integration` or `make package`
   when the changed boundary requires it.

Start the VitePress site with:

```bash
make docs-install
make docs-dev
```

Portless prints the stable HTTPS URL for the checkout. The main checkout uses
`https://docs.pyagentbrowser.localhost/`. Linked worktrees receive a
branch-prefixed subdomain so their development servers can run concurrently.

Read [the documentation guide](development_docs/documentation.md) for the page
structure, terminology, metadata, asset, and browser-validation contracts.
