# 0001 Native Safety Patches

## Status

Accepted

## Context

`pyagentbrowser` exposes native `agent-browser` behavior directly to Python.
Most upstream bugs should stay upstream-owned and, when needed, documented with
strict upstream-boundary tests. Security-sensitive behavior is different. If Python
turns a native response into a trusted exception or action replay API, the SDK
must not expose known unsafe native semantics.

The repository still must not edit `third_party/agent-browser`.

## Decision

Allow generated Native Safety Patches only when all constraints hold:

- the issue is security-sensitive native behavior exposed through the Python
  SDK
- the patch is generated into `OUT_DIR` during adapter build
- the patch never edits `third_party/agent-browser`
- the patch is named, documented, and covered by tests
- the patch is removed when upstream owns the behavior

## Accepted Patches

| Patch ID | Type | Purpose | Generated output | Coverage | Owner |
| --- | --- | --- | --- | --- | --- |
| `confirmation-replay` | Native Safety Patch | Bind confirmation replay to the requested confirmation ID and re-check policy and allowlist constraints before replay. | OUT_DIR | crates/agent-browser-adapter/tests/smoke.rs, tests/test_native.py | Python SDK until upstream owns confirmation replay safety |
| `dashboard-stream-result-success` | Native Safety Patch | Emit dashboard stream result success from native boolean response data. | OUT_DIR | crates/agent-browser-adapter/tests/smoke.rs, tests/test_native.py | Python SDK until upstream owns stream result correctness |
| `dashboard-stream-hooks` | Build-surface drift assertion | Assert that upstream still exposes the dashboard stream hooks used by SDK session observability. | OUT_DIR | crates/agent-browser-adapter/build.rs, crates/agent-browser-adapter/tests/smoke.rs, tests/test_native.py | Adapter, not a behavior patch |

`dashboard-stream-hooks` is a build-surface drift assertion. It verifies SDK
dashboard hooks during generated-source builds and does not change native safety
behavior.

`native-safety-patches.json` ships with the ADR files as the structured patch
inventory. Each entry names the behavior, generated output boundary, and
coverage paths for release review.

## Consequences

The upstream submodule remains clean. The cost is that generated rewrites must
be audited whenever upstream source changes. `make package` and
`make check-release` are the release gates for that boundary.
