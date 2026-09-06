# Packaging

pyagentbrowser ships one Python distribution, one import package, one pinned native engine, and one extension built against [Python's stable application binary interface](https://docs.python.org/3/c-api/stable.html) per platform target.

The artifact is the final output of the [downstream wrapper model](repository-model.md).
It binds one Python SDK release to one exact upstream commit while preserving
their independent version identities.

## Artifact set

| Artifact            | Target                                        |
| ------------------- | --------------------------------------------- |
| Wheel               | manylinux 2.28 x86-64                         |
| Wheel               | manylinux 2.28 arm64                          |
| Wheel               | macOS x86-64                                  |
| Wheel               | macOS arm64                                   |
| Wheel               | Windows x86-64                                |
| Source distribution | Portable source inputs for a local Rust build |

The stable-ABI baseline is Python 3.11. Release verification exercises Python 3.11 and 3.14 endpoints and the SDK matrix covers every supported Python version.

## Wheel contract

A wheel contains the `agentbrowser` package, one nonempty native extension, `py.typed`, embedded engine provenance, embedded skill data, the pyagentbrowser Agent Plugin, project licensing, and required upstream notices. Its `marimo.agent.capability` entry point resolves to `agentbrowser.agent`.

Package smoke tests reject source trees, development instructions, caches, duplicate native extensions, and local build-path leaks.

## Source distribution contract

The source distribution contains the Python source, root Cargo lock, Rust toolchain file, PyO3 crate, adapter crate, pinned upstream engine source required by the build, the Agent Plugin build backend and staged resources, user-facing Markdown docs, examples, and license material.

The manifest excludes repository automation, local artifacts, and upstream
project tooling outside the source set selected for downstream builds. Package
smoke tests define the exact excluded paths.

When a registered upstream module becomes a new adapter dependency, update the
source-distribution inclusion and package smoke allowlists in the same change.

## Reproducibility

Package builds set `SOURCE_DATE_EPOCH` from the repository commit, clamp source-distribution member timestamps to that value, and remap the workspace and Cargo home paths in Rust debug metadata. CI repeats the same timestamp and path normalization inside native and manylinux builders.

Inspect built binaries and archive members for checkout paths before accepting the artifact.

## Installed behavior

`scripts/verify-install-artifacts.py` creates clean environments and checks:

- Base package import and version metadata.
- Native extension and embedded engine provenance.
- Missing-extra diagnostics.
- The `images` and `cdp` optional packages.
- Embedded skill reads.
- Marimo capability metadata, dynamic help, and Agent Plugin resource lookup.
- Wheel installation across supported Python endpoints.
- Source-distribution build and install.
- `pip check` dependency consistency.

Run `make package` after changing build inputs, bundled files, extras, ABI settings, license content, or source-distribution boundaries.

Publication sequencing and exact-SHA release evidence belong to [Maintenance](maintenance.md).
Build-time skill data, protocol schemas, provenance, and notices belong to
[Embedded resources](embedded-resources.md).
