# pyagentbrowser

Python SDK for the native Rust `agent-browser` engine. The package name is
`pyagentbrowser`. Imports use `pyagentbrowser`.

## Commands

- Setup: `make install`
- Normal handoff: `make check`
- Browser coverage: `make test-integration`
- Wheel/sdist smoke: `make package`
- Release gate: `make check-release`

Use `make help` for the supported target list.

## Repo Map

- `src/pyagentbrowser/`: public Python SDK.
- `crates/pyagentbrowser/`: PyO3 Rust crate for the native extension.
- `crates/agent-browser-adapter/`: first-party Rust adapter and generated source shims.
- `third_party/agent-browser/`: upstream submodule. Do not edit it directly.
- `docs/`: user docs, with maintainer boundary docs under `docs/internals/`.
- `examples/`: maintained public-API examples.
- `scripts/package_smoke.py`: artifact boundary checks.

## Rules

- Keep `Browser.command(action, **params)` as the raw native escape hatch.
- Prefer namespaced public API: `browser.page`, `browser.find`, `browser.capture`,
  `browser.frames`, `browser.cdp`, `browser.scripts`, and matching async surfaces.
- Do not patch `third_party/agent-browser`. Native behavior differences must be
  generated in `OUT_DIR`, documented in `docs/adr/0001-native-safety-patches.md`,
  and covered by tests.
- Update examples and docs in the same change as public API changes.
- Run `make check` for normal handoff changes. Add `make test-integration` for
  browser behavior, `make package` for artifact changes, and `make check-release`
  before release-level changes.
