# Testing

Choose the lowest boundary that proves the supported contract, then add the next boundary when ownership crosses it.

## Test markers

| Marker         | Proves                                                                                                                                 |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `sdk_dx`       | Python API, models, refs, evidence, policy, lifecycle, embedded skills, and async behavior                                             |
| `native_smoke` | [PyO3](https://pyo3.rs/) Rust-to-Python bindings, generated adapter, native helper processes, embedded data, and native protocol seams |
| `integration`  | Real Chrome, page transitions, browser processes, direct CDP, and operating-system seams                                               |
| `packaging`    | Wheel, source distribution, version, provenance, and release contracts                                                                 |

## Boundary selection

Use fake-native SDK tests for Python input construction, strict decoding, continuation composition, error mapping, sync and async parity, and lifecycle state transitions.

Use compiled-native tests when the contract depends on PyO3, Rust resource ownership, generated adapter behavior, skill payloads, session discovery, or native helper-process cleanup.

Use real-browser integration tests for browser discovery, navigation, accessibility trees, screenshots, CDP targets and frames, WebMCP availability, renderer revival, and process teardown.

Use package tests for metadata, included and excluded files, license payload, native extension count, ABI tags, reproducibility, optional packages, clean wheel installs, and source builds.

## Downstream responsibility

Test the behavior this repository adds or changes:

- The official submodule URL, exact gitlink, provenance, and version relations.
- Every generated adaptation and its fail-closed upstream assumption.
- PyO3 construction, command, resource, and cleanup behavior.
- Python validation, decoding, composition, evidence, policy, and lifecycle.
- Artifact contents and clean installation on supported targets.

Generic engine actions remain upstream responsibility until this repository
adapts them, exposes a typed contract around them, or depends on them at an
integration boundary. An upstream update should exercise representative seams,
not duplicate the upstream suite.

## Test design

- Assert through the public API, protocol envelope, file artifact, process state, or browser state a consumer uses.
- Keep one contract per test.
- Test error timing when an action can complete before evidence fails.
- Cover both raw-envelope and checked-data behavior for native actions.
- Keep sync and async parameter surfaces aligned.
- Treat upstream engine behavior as pinned input unless Python, PyO3, or adapter ownership changes its contract.

## Commands

```bash
make test-sdk
make test-native
make test-integration
make test-package
make rust-check rust-test
make docs-check
make check
make check-release
```

`make check` is the normal Python and Rust handoff. Add `make docs-check` for
public documentation, contributor-page navigation, local links, and site
changes. Review changed Markdown against the repository documentation rules.
Add the boundary-specific command for the implementation surface changed.
