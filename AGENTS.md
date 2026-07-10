# pyagentbrowser

Python SDK for the native Rust `agent-browser` engine. The distribution is
`pyagentbrowser`, while Python imports use `agentbrowser`.

The project owns the typed Python API, agent-oriented evidence, safety policy,
resource lifecycle, native embedding, and binary distribution around a pinned
upstream engine.

## Commands

| Task | Command |
| --- | --- |
| Bootstrap or rebuild the extension | `make install` |
| Pin upstream `origin/main` | `make update-upstream` |
| Python SDK contracts | `make test-sdk` |
| PyO3 and adapter boundary | `make test-native` |
| Wheel, sdist, and release contracts | `make test-package` |
| Normal handoff | `make check` |
| Real Chrome seams | `make test-integration` |
| Build and install artifacts | `make package` |
| Full release gate | `make check-release` |

`make check` is the normal completion gate. Add the boundary-specific command
for the surface you changed.

## Runtime shape

```text
Browser / AsyncBrowser
  -> Python policy, lifecycle, namespaces, models, and evidence
  -> PyO3 native session
  -> first-party Rust adapter and generated compatibility shims
  -> pinned upstream agent-browser submodule
```

Read [the architecture guide](development_docs/architecture.md) before moving
behavior across these layers.

## Work by ownership

- Python API work: read [the SDK instructions](src/agentbrowser/AGENTS.md).
- PyO3, adapter, or upstream work: read [the Rust instructions](crates/AGENTS.md)
  and [the maintenance guide](development_docs/maintenance.md).
- Tests: read [the test instructions](tests/AGENTS.md).
- Packaging, versioning, CI, and releases: read
  [the maintenance guide](development_docs/maintenance.md).

## Invariants

- Keep `browser.native.execute(action, **params)` and
  `browser.native.data(action, **params)` as complete raw escape hatches.
- Keep synchronous and asynchronous public surfaces semantically aligned.
- Treat `third_party/agent-browser` as immutable pinned input. Generate
  adaptations of upstream source in `OUT_DIR`, and make every rewrite fail
  closed.
- Update public examples and docs with public API changes. Use relative links.
- Test SDK, PyO3, adapter, lifecycle, browser-seam, and artifact behavior owned
  here. Leave generic engine behavior to upstream.

## Keep instructions current

Record stable, non-obvious discoveries at the narrowest applicable scope.
Exclude session history, obvious code facts, and rules already enforced by the
toolchain.
