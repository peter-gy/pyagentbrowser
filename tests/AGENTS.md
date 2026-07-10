# Test contracts

Tests protect behavior this repository owns through the nearest public or
artifact boundary.

## Marker ownership

| Marker | Contract |
| --- | --- |
| `sdk_dx` | Python API, safety, typing, lifecycle, refs, and async behavior |
| `native_smoke` | PyO3, generated adapter, dashboard, and native provenance |
| `integration` | Curated real-Chrome seams across Python, Rust, adapter, and CDP |
| `packaging` | Wheel, sdist, version, provenance, and release artifacts |

## Test design

- Prefer `ScriptedNative` and the other fakes in `tests/fakes.py` for Python
  contracts. Assert the public result and the native command when serialization
  is part of that contract.
- Use native smoke tests for behavior that requires the compiled extension or
  generated adapter. Use integration tests when Chrome or process behavior is
  the boundary under test.
- Keep each test focused on one supported behavior, lifecycle guarantee, data
  shape, or failure mode.
- Test sync and async behavior together when parity is the contract.
- Keep packaging tests in `tests/packaging/` so the focused local and CI gates
  discover them together. Verify built and installed artifacts through
  `scripts/package_smoke.py` and `scripts/verify-install-artifacts.py`.
- Assert required artifact members when import, runtime, build, license, or type
  support depends on them. Do not add source-tree tests for docs, repository file
  presence, deleted names, comments, formatting trivia, or private helper details
  that consumers cannot observe.
- Use comments for artificial setup, external runtime quirks, or ordering
  constraints. Let names and assertions explain ordinary behavior.

## Running tests

- One test: `uv run --no-sync pytest -q path/to/test.py::test_name`
- Python contracts: `make test-sdk`
- Native boundary: `make test-native`
- Packaging contracts: `make test-package`
- Real browser: `make test-integration`
