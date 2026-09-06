# Maintenance

The Makefile is the executable command index. This guide records the ordering
and evidence behind upstream updates, package releases, and CI.

Read [the generated adapter contract](generated-adapter.md) before changing a
rewrite. Read [the packaging contract](packaging.md) before changing artifact
contents or build inputs.

The [downstream wrapper model](repository-model.md) defines why an upstream
update changes a source pin, generated compatibility assumptions, provenance,
and distribution inputs as one reviewed unit.

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

Before applying the update, classify the candidate diff:

| Upstream area                     | Downstream consequence                                                           |
| --------------------------------- | -------------------------------------------------------------------------------- |
| Registered Rust module            | Re-audit adapter module registry and rewrite anchors                             |
| Command or response contract      | Check raw compatibility, typed decoding, safety, and lifecycle                   |
| Browser process or state behavior | Check PyO3 ownership and integration seams                                       |
| Protocol schema                   | Regenerate and compile adapter protocol types                                    |
| `skill-data`                      | Verify embedded resource parsing and package payload                             |
| Cargo dependencies or features    | Reconcile adapter dependencies, refresh the root lock, and re-audit build inputs |
| License or third-party notice     | Update packaged license material                                                 |

Then:

1. Run `git diff --submodule=log -- third_party/agent-browser` to confirm the
   superproject pin, then inspect the exact source range with
   `git -C third_party/agent-browser diff "$(git rev-parse HEAD:third_party/agent-browser)..HEAD"`.
2. Run `make test-native`. A failed adapter rewrite identifies an upstream
   anchor that moved or changed cardinality.
3. Repair the narrow rewrite in `crates/agent-browser-adapter/build.rs`. Keep the
   upstream submodule clean.
4. Reconcile upstream dependencies and features with
   `crates/agent-browser-adapter/Cargo.toml`. The updater aligns its version and
   refreshes the root lock, but dependency declarations remain a reviewed
   downstream contract.
5. Add or update Python APIs when the upstream capability belongs in a stable
   typed workflow. The raw native path already exposes the complete command set.
6. Run `make check-release`.

An upstream update normally changes the submodule pointer, provenance, adapter
version, and lockfiles. Adapter and Python changes depend on the upstream diff.

The submodule pointer is the source identity. `_upstream.json` is installed
provenance. The adapter manifest describes compatibility. All three must agree
before release.

## Generated adapter source

The [generated adapter contract](generated-adapter.md) owns the module registry,
rewrite-anchor, confirmation, namespace, tab-binding, protocol-generation,
stream, and dashboard rules. Follow its audit and validation sequence after an
upstream pin changes.

## Package versions

The Python release uses `X.Y.Z[.N][rcN]`. `X.Y.Z` matches the embedded
`agent-browser` tag. The baseline pyagentbrowser release uses `X.Y.Z`. Another
release on the same upstream tag appends a downstream revision beginning with
`.1`. Moving to a new upstream tag resets the downstream revision.

For example:

```text
pyagentbrowser 0.36.0      -> agent-browser v0.36.0, baseline release
pyagentbrowser 0.36.0.1    -> agent-browser v0.36.0, downstream revision 1
pyagentbrowser 0.36.0.2rc4 -> release candidate 4 for downstream revision 2
pyagentbrowser 0.37.0      -> agent-browser v0.37.0, baseline release
```

Python package metadata uses the public version. Cargo requires three numeric
release components, so the unpublished PyO3 crate carries the downstream
revision as build metadata. The PyO3 crate is a path dependency, so the Cargo
version records build identity while Python package metadata owns release
ordering.

| Source                             | Example                |
| ---------------------------------- | ---------------------- |
| `pyproject.toml`                   | `0.36.0.2rc4`          |
| `src/agentbrowser/_version.py`     | `0.36.0.2rc4`          |
| `uv.lock`                          | `0.36.0.2rc4`          |
| `crates/pyagentbrowser/Cargo.toml` | `0.36.0-rc.4+py.2`     |
| `Cargo.lock`                       | `0.36.0-rc.4+py.2`     |
| `src/agentbrowser/_upstream.json`  | `0.36.0` plus exact SHA |

`scripts/release_version.py` owns the public grammar and Cargo mapping. The
adapter crate follows the embedded upstream version because it compiles that
source.

Set `RELEASE_TAG` to the planned pyagentbrowser tag, then verify the package,
Cargo, and upstream identities with:

```bash
make release-version-check
python -m scripts.check_release --tag "$RELEASE_TAG"
```

The release tag must include `v`. The checker verifies that the package version
matches the tag and that the encoded upstream tag resolves to the pinned
upstream commit. Fetch upstream tags when a shallow clone lacks the encoded
tag. The checker also requires a clean upstream worktree because its files enter
the source distribution.

## Release state machine

1. Set the Python package version and derived Cargo version, then refresh both
   lockfiles.
2. Run `make check-release`.
3. Commit and push the version change to `main`.
4. Wait for a successful push-event `Release Check` on the exact commit SHA.
5. Create and push an annotated version tag for that commit.
6. Follow the tag-triggered `Publish` workflow through public verification.

The publish workflow requires successful exact-SHA release evidence before it
accepts a tag. It builds five wheels against Python's stable application binary interface and one sdist, validates every payload,
publishes through PyPI trusted publishing, installs the public wheel on Linux
and Windows, and verifies the public artifact set plus GitHub prerelease state.
Release candidate notes compare with the nearest ancestor release tag. Final
release notes compare with the nearest final tag, preserving the complete
change set across a release candidate series.

Published artifacts are immutable. If publication starts and a later gate
fails, fix forward with a new version and tag.

## Validation ladder

| Evidence               | Command                     | Use when                                                                 |
| ---------------------- | --------------------------- | ------------------------------------------------------------------------ |
| Python public contract | `make test-sdk`             | API, models, policy, lifecycle, refs, async behavior                     |
| Native embedding       | `make test-native`          | PyO3, generated adapter, sidecars, provenance                            |
| Rust ownership         | `make rust-check rust-test` | Rust source or generator logic                                           |
| Real browser           | `make test-integration`     | Chrome, CDP, process, or page-transition behavior                        |
| Documentation site     | `make docs-check`           | TypeScript config, build, links, navigation, metadata, and public assets |
| Distribution           | `make test-package`         | Metadata, payload, version, provenance rules                             |
| Installed artifacts    | `make package`              | Build inputs, extras, ABI, wheel, or sdist changes                       |
| Release                | `make check-release`        | Upstream pins, versions, CI, publishing, release work                    |

CI uses the same ownership boundaries. `Release Check` separates quality, SDK
versions, platform builds, and real-browser seams. `Publish` reuses the wheel
builder, then verifies the public index from clean environments. `Required
gate` reports one aggregate result after every `Release Check` job group
finishes.

[Testing](testing.md) defines which marker and runtime boundary should carry a
new contract. [Documentation](documentation.md) defines the public-site build
and browser checks.

## Cross-platform source

Repository text is checked out with LF line endings through `.gitattributes`.
Generated and embedded text still normalizes newlines because source archives
and external inputs can bypass checkout attributes. Treat paths, executable
discovery, process identity, socket or TCP control transport, and extension
suffixes as platform-specific boundaries.
