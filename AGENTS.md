# pyagentbrowser

Python SDK for the native Rust `agent-browser` engine. The distribution is
`pyagentbrowser`, while Python imports use `agentbrowser`.

The project owns the typed Python API, agent-oriented evidence, safety policy,
resource lifecycle, native embedding, and binary distribution around a pinned
upstream engine.

## Development setup

Install [Pixi](https://pixi.sh/latest/installation/) 0.81.x, then run from the
repository root:

```bash
pixi install --locked
pixi run --locked install
pixi run --locked check
```

The committed `pixi.lock` supplies Python 3.14, Rust 1.98.1 (including Clippy and
rustfmt), C/C++ compilers and a Linux sysroot, Make, Git, uv, Node.js, pnpm,
FFmpeg, and Linux Chrome runtime libraries. Supported development platforms are
Linux x86-64/arm64 and macOS Intel/Apple Silicon. On Windows use WSL2 with a Linux
checkout; native Windows wheels remain covered by release CI. macOS also needs
Apple's SDK (`xcode-select --install`). Pixi cannot distribute that SDK.
The Linux Rust linker uses GCC's built-in specs to keep local Conda RPATHs out
of wheels while retaining the locked compiler and sysroot.

Use `pixi run --locked <task>` for the tasks below, or `pixi shell` and then
ordinary `make` / `uv run --no-sync` commands. Python dependencies and the
editable extension live in `.venv`; `.pixi` owns the system toolchain. For a
focused test use `pixi run --locked uv run --no-sync pytest -q path/to/test.py`.
Rebuild with `pixi run --locked install` after native changes. `pixi run python`
uses the toolchain interpreter; use `uv run --no-sync python` to import the SDK.

For browser work, run `pixi run --locked browser-install`, then
`pixi run --locked test-integration`. Browser downloads use the SDK's Chrome for
Testing cache and are separate from `pixi.lock`. Linux arm64 needs an installed
Chromium executable selected with `PYAGENTBROWSER_CHROME` because Chrome for
Testing has no Linux arm64 download. In containers with restricted user
namespaces, use `CI=1 pixi run --locked test-integration` to apply the upstream
engine's CI launch settings. Docs work starts with
`pixi run --locked docs-dev`; validate with `pixi run --locked docs-check`.

Keep dependency ownership separate: update `pixi.toml` and `pixi.lock` for
system tools, `pyproject.toml` and `uv.lock` for Python packages, and
`docs/package.json` and `docs/pnpm-lock.yaml` for docs packages. Refresh the
system lock with `pixi lock`, then verify `pixi install --locked`. Keep its Rust
pin aligned with `rust-toolchain.toml` and the Makefile. Existing Make commands
also support a manually provisioned toolchain through rustup.

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
  -> first-party Rust Engine interface
  -> generated modules from the agent-browser-build crate
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
