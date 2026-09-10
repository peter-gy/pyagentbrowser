# Native crates

The native layer embeds a pinned engine behind the Python API.

## Ownership

- `pyagentbrowser/` owns the PyO3 module, native session construction, embedded
  skill data, dashboard sidecars, parent-process cleanup, and Python-facing
  native errors.
- `agent-browser-adapter/` owns the embedded `Engine` interface, configuration,
  confirmation, and document behavior. Keep upstream runtime types private to
  the adapter.
- `agent-browser-build/` owns module registration, feature rewrites, protocol
  generation, and source audit reports. The adapter's build script calls it to
  generate adapted modules in `OUT_DIR`.
- `third_party/agent-browser/` is the upstream source of truth and stays clean.

## Adapter rules

- Inspect the pinned upstream implementation before changing a rewrite.
- Match exact source anchors and require one match unless the upstream contract
  proves another count. Missing or duplicate matches must stop the build.
- Generate adapted source under `OUT_DIR`. Do not track generated Rust output.
- Declare dependencies when a patch consumes text introduced by another patch.
  Keep each feature's source transformations beside its own module registration.
- Keep adapter changes scoped to embedding constraints such as entrypoints,
  process ownership, control transport, or platform integration.
- Treat paths, text encoding, line endings, process identity, and cleanup as
  cross-platform contracts. Validate Windows and Unix behavior when they differ.
- Keep the adapter package version aligned with the embedded upstream version.
  Derive the PyO3 package version from the Python release through
  `scripts/release_version.py`.

## Validation

- `make test-native` covers the installed Python to PyO3 to adapter seam.
- `make rust-check` runs formatting and Clippy for the owned Rust packages.
- `make rust-test` runs PyO3 unit tests and adapter smoke tests.
- Add `make test-integration` for browser or process behavior.
- Add `make package` when build inputs or bundled payloads change.
