# Upstream Tracking

`pyagentbrowser` builds on upstream `agent-browser` without maintaining a
fork. The upstream project lives in `third_party/agent-browser` as a clean git
submodule. Local integration code lives outside that submodule.

## Layout

- `third_party/agent-browser`: upstream source.
- `crates/pyagentbrowser`: PyO3 native extension crate.
- `crates/agent-browser-adapter`: Rust adapter crate named `agent-browser`.
- `src/pyagentbrowser`: Python SDK.
- `crates/pyagentbrowser/build.rs`: embeds upstream `skill-data` into the
  native extension.

The PyO3 crate depends on:

```toml
agent-browser = { path = "../agent-browser-adapter" }
```

## Categories

### Source Shims

The adapter generates module shims into `OUT_DIR` so the Python extension can
use selected upstream Rust modules as a library. These shims are source-path
wiring, not behavior changes.

When upstream moves a file, update `crates/agent-browser-adapter/build.rs`.
Missing moved files should fail loudly during adapter generation.

### Native Safety Patches

A Native Safety Patch is a generated rewrite for security-sensitive native
behavior that the Python SDK cannot safely expose as-is. It must:

- write generated files in `OUT_DIR`
- never edit `third_party/agent-browser`
- be named in `crates/agent-browser-adapter/build.rs`
- be documented in [ADR 0001](../adr/0001-native-safety-patches.md)
- be covered by tests
- be removed when upstream owns the behavior

### Build-Surface Drift Assertions

Some generated rewrites assert that upstream still exposes the hooks the SDK
needs, such as dashboard stream types and command/result broadcast points. These
are not Native Safety Patches unless they change security-sensitive behavior.
The current build-surface assertion is `dashboard-stream-hooks`.

### SDK Dashboard Pruning

Python-owned dashboard sessions are observable-only. The SDK may include the
upstream stream source needed for session visibility, but it must not bundle the
dashboard web UI or shell out to the CLI daemon. Dashboard control accepts only
detach commands (`close`, `quit`, and `exit`). Other commands, including
`navigate` and `kill`, must be rejected while the host Python browser remains
alive.

## Packaging Rules

- Wheels must contain the Python package, `py.typed`, and the native extension.
- Wheels must not contain `third_party`, `crates`, Rust build inputs, docs
  figures, or a Python CLI entry point.
- Source distributions include only the selected upstream source slice needed to
  build the native extension.
- Runtime skill data comes from the embedded native extension, not repository
  paths.

`make package` enforces these artifact boundaries.

## Updating Upstream

```bash
scripts/update-upstream.sh <commit-or-tag>
make check-release
```

The update script checks out the requested upstream ref, syncs prerelease
metadata from the upstream base tag and exact pinned commit, then runs the
upstream contract, skills, native, Rust, and package checks.

If upstream fixes behavior covered by a Native Safety Patch, remove the rewrite.
Parallel implementations make upstream drift harder to catch.

Expected-fail tests are acceptable only for upstream-owned behavior that the
Python SDK does not expose as a safety boundary. Mark them `xfail(strict=True)`
so a future upstream fix becomes visible.
