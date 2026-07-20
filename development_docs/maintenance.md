# Maintenance

The Makefile is the executable command index. This guide records the ordering
and evidence behind upstream updates, package releases, and CI.

## Update the embedded engine

Pin the latest commit from the official upstream branch with:

```bash
make update-upstream
```

Set `UPSTREAM_REF` to pin a release tag, branch, or commit:

```bash
make update-upstream UPSTREAM_REF=v1.2.3
```

`make update-upstream` tracks `origin/main`. For a release-aligned update,
verify the latest official release and compare its tag with the current pin
before setting `UPSTREAM_REF`. The updater accepts fast-forward changes and
requires an explicit override for older or divergent refs:

```bash
make update-upstream UPSTREAM_REF=v1.2.3 ALLOW_NON_FAST_FORWARD=1
```

The script initializes the submodule when needed, refuses a dirty upstream
checkout, checks out the resolved commit, synchronizes the adapter package
version, updates `src/agentbrowser/_upstream.json`, synchronizes the adapter
entry in `Cargo.lock`, and prints the inspected `old..new` range. Supporting
Python dependency changes refresh `uv.lock` through the normal project workflow.

Then:

1. Run `git diff --submodule=log -- third_party/agent-browser` to confirm the
   superproject pin, then inspect the exact source range with
   `git -C third_party/agent-browser diff "$(git rev-parse HEAD:third_party/agent-browser)..HEAD"`.
2. Run `make test-native`. A failed adapter rewrite identifies an upstream
   anchor that moved or changed cardinality.
3. Repair the narrow rewrite in `crates/agent-browser-adapter/build.rs`. Keep the
   upstream submodule clean.
4. Add or update Python APIs when the upstream capability belongs in a stable
   typed workflow. The raw native path already exposes the complete command set.
5. Run `make check-release`.

An upstream update normally changes the submodule pointer, provenance, adapter
version, and lockfiles. Adapter and Python changes depend on the upstream diff.

## Generated adapter source

The adapter build script copies selected upstream modules into Cargo `OUT_DIR`,
normalizes source text, applies explicit rewrites, and compiles the generated
module tree. Rewrites are build contracts:

- Each anchor names an upstream construct that was inspected at the pinned
  commit.
- The expected match count is checked.
- Generated output remains outside the tracked source tree.
- Adapter smoke tests and native smoke tests exercise the resulting boundary.

When an anchor fails, inspect the pinned upstream source before changing the
match. Broadening a pattern until the build passes can silently adapt the wrong
code.

## Package versions

The Python distribution and PyO3 crate share one release version. Cargo uses its
native prerelease spelling.

| Source | Example |
| --- | --- |
| `pyproject.toml` | `1.2.3rc4` |
| `src/agentbrowser/_version.py` | `1.2.3rc4` |
| `uv.lock` | `1.2.3rc4` |
| `crates/pyagentbrowser/Cargo.toml` | `1.2.3-rc.4` |
| `Cargo.lock` | `1.2.3-rc.4` |

The adapter crate follows the embedded upstream version. Set `RELEASE_TAG` to
the planned tag, then verify all version and provenance sources with:

```bash
make prerelease-version-check
./scripts/release.sh check-version "$RELEASE_TAG"
```

## Release state machine

1. Update the five SDK version sources and refresh both locks.
2. Run `make check-release`.
3. Commit and push the version change to `main`.
4. Wait for a successful push-event `Release Check` on the exact commit SHA.
5. Create and push an annotated version tag for that commit.
6. Follow the tag-triggered `Publish` workflow through public verification.

The publish workflow requires successful exact-SHA release evidence before it
accepts a tag. It builds five ABI3 wheels and one sdist, validates every payload,
publishes through PyPI trusted publishing, installs the public wheel on Linux
and Windows, and verifies the public artifact set plus GitHub prerelease state.

Published artifacts are immutable. If publication starts and a later gate
fails, fix forward with a new version and tag.

## Validation ladder

| Evidence | Command | Use when |
| --- | --- | --- |
| Python public contract | `make test-sdk` | API, models, policy, lifecycle, refs, async behavior |
| Native embedding | `make test-native` | PyO3, generated adapter, sidecars, provenance |
| Rust ownership | `make rust-check rust-test` | Rust source or generator logic |
| Real browser | `make test-integration` | Chrome, CDP, process, or page-transition behavior |
| Distribution | `make test-package` | Metadata, payload, version, provenance rules |
| Installed artifacts | `make package` | Build inputs, extras, ABI, wheel, or sdist changes |
| Release | `make check-release` | Upstream pins, versions, CI, publishing, release work |

CI uses the same ownership boundaries. `Release Check` separates quality, SDK
versions, platform builds, and real-browser seams. `Publish` reuses the wheel
builder, then verifies the public index from clean environments. `Required
gate` reports one aggregate result after every `Release Check` job group
finishes.

## Cross-platform source

Repository text is checked out with LF line endings through `.gitattributes`.
Generated and embedded text still normalizes newlines because source archives
and external inputs can bypass checkout attributes. Treat paths, executable
discovery, process identity, socket or TCP control transport, and extension
suffixes as platform-specific boundaries.
