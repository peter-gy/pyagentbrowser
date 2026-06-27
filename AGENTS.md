# pyagentbrowser

Python SDK for the native Rust `agent-browser` engine. The package name is
`pyagentbrowser`. Imports use `agentbrowser`.

## Commands

- Setup: `make install`
- Normal handoff: `make check`
- Browser coverage: `make test-integration`
- Wheel/sdist smoke: `make package`
- Release gate: `make check-release`

## Repo Map

- `src/agentbrowser/`: public Python SDK.
- `crates/pyagentbrowser/`: PyO3 Rust crate for the native extension.
- `crates/agent-browser-adapter/`: first-party Rust adapter and generated source shims.
- `third_party/agent-browser/`: upstream submodule. Do not edit it directly.
- `docs/`: essential user docs.
- `examples/`: maintained public-API examples.
- `scripts/package_smoke.py`: artifact boundary checks.

## Rules

- Keep `browser.native.execute(action, **params)` and
  `browser.native.data(action, **params)` as the raw native escape hatches.
- Prefer namespaced public API: `browser.page`, `browser.find`, `browser.capture`,
  `browser.active_frame`, `browser.cdp.frames`, `browser.scripts`, and matching
  async surfaces.
- Do not patch `third_party/agent-browser`. Native behavior differences must be
  generated in `OUT_DIR` and covered by tests.
- Update examples and docs in the same change as public API changes.
- Run `make check` for normal handoff changes. Add `make test-integration` for
  browser behavior, `make package` for artifact changes, and `make check-release`
  before release-level changes.
