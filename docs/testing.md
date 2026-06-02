# Testing

The canonical command surface is the root `Makefile`. Run `make help` for the
current list.

## Local Loop

```bash
make check
```

`make check` runs the normal handoff gate: docs, examples, linting, type
checking, current-interpreter tests, and first-party Rust checks.

## Integration

```bash
make test-integration
```

This requires a real Chrome/Chromium binary and fails if integration coverage is
skipped.

## Python Matrix

```bash
make test-python-matrix
```

The default matrix is Python 3.10 through 3.14. Override with
`PYTHON_VERSIONS` when you need a narrower local run.

## Rust

```bash
make rust-check
make rust-test
make rust
```

`make rust-check` is the fast first-party Rust gate. `make rust` also runs Rust
tests and the adapter smoke test.

## Packaging

```bash
make package
```

This builds a wheel for each supported Python version plus one sdist, verifies
artifact boundaries, and installs the matching wheel and sdist into clean
environments. Narrow the local package matrix with `PYTHON_VERSIONS`:

```bash
PYTHON_VERSIONS=3.14 make package
```

## Release Gate

```bash
make check-release
```

This verifies prerelease metadata, then combines the normal handoff gate,
real-browser integration, Python matrix, Rust tests, and package smoke.

The GitHub check-release workflow runs the Python and packaging matrix on macOS
and Linux.
