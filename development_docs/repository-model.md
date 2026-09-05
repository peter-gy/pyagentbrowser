# Downstream wrapper model

pyagentbrowser is an independently versioned Python product built around an
exact revision of the upstream
[`agent-browser`](https://github.com/vercel-labs/agent-browser) engine. Git calls
the repository that records a submodule pin the _superproject_. This guide uses
_downstream wrapper_ because it also describes the product boundary.

The upstream engine supplies browser automation behavior. This repository owns
how that behavior is embedded, constrained, typed, composed, tested, packaged,
and released for Python users.

## Repository contract

```text
official agent-browser repository
  -> exact commit recorded by this repository
  -> immutable source under third_party/agent-browser
  -> generated adaptation under Cargo OUT_DIR
  -> PyO3 native extension
  -> typed Python SDK
  -> wheel and source distribution
```

The submodule is source input, not a downstream editing surface. A checkout
records its exact commit as a Git _gitlink_. A clean clone initializes that
commit before Rust compilation or package verification.

The generated adapter registers required upstream modules, writes adapted
modules and wrapper trees to Cargo `OUT_DIR`, and compiles them as a downstream
library. The PyO3 crate links that library into `agentbrowser._native`. The
Python package then owns the public contract above the JSON command protocol.

The root Cargo workspace contains the adapter and PyO3 crates. It explicitly
excludes the upstream Cargo workspace, so Cargo resolves one downstream lock
and never treats the submodule as another workspace member.

## Ownership boundaries

| Concern                                              | Owner                           | Primary source                                         |
| ---------------------------------------------------- | ------------------------------- | ------------------------------------------------------ |
| Generic engine actions and browser behavior          | Upstream `agent-browser`        | `third_party/agent-browser/`                           |
| Upstream revision selection and intake               | pyagentbrowser                  | `scripts/update_upstream.py` and the submodule gitlink |
| In-process compatibility transformations             | pyagentbrowser adapter          | `crates/agent-browser-adapter/build.rs`                |
| Rust runtime and Python binding                      | pyagentbrowser native extension | `crates/pyagentbrowser/`                               |
| Typed workflows, evidence, safety, and lifecycle     | pyagentbrowser SDK              | `src/agentbrowser/`                                    |
| Wheels, source distribution, provenance, and release | pyagentbrowser                  | `pyproject.toml`, `scripts/`, and `.github/workflows/` |

An engine defect or generally applicable capability belongs upstream. An
embedding constraint, Python contract, or distribution concern belongs here.
When a downstream requirement changes upstream source, encode it as a
fail-closed generated adaptation and keep the pinned checkout clean.

## Three independent identities

The repository tracks three related identities with different meanings:

| Identity               | Meaning                                         | Recorded in                                                 |
| ---------------------- | ----------------------------------------------- | ----------------------------------------------------------- |
| pyagentbrowser version | Python product and PyO3 extension release       | `pyproject.toml`, `_version.py`, PyO3 Cargo manifest, locks |
| Upstream version       | Version declared by the pinned engine           | upstream Cargo manifest and adapter Cargo manifest          |
| Upstream commit        | Exact source revision embedded by this checkout | submodule gitlink and `_upstream.json`                      |

The Python release version can advance while the upstream version stays fixed.
The adapter crate follows the upstream version because it describes
compatibility with that source. `src/agentbrowser/_upstream.json` records the
version and commit exposed to installed Python callers.

## Classify a change

Before editing, identify the lowest owner that can hold the contract.

| Change                                                | Correct owner                             |
| ----------------------------------------------------- | ----------------------------------------- |
| New reusable engine action                            | Upstream engine, followed by a pin update |
| Python validation, result model, or composed workflow | Python SDK                                |
| JSON payload or confirmation bookkeeping              | Python native session                     |
| Rust runtime, process, watchdog, or control transport | PyO3 crate                                |
| Upstream source incompatibility during embedding      | Generated adapter                         |
| Included source, license, ABI, or wheel content       | Packaging and release tooling             |

A typed Python wrapper is warranted when Python owns stable validation, result
decoding, lifecycle behavior, evidence capture, or a composition that callers
would otherwise repeat. The raw native API preserves immediate access to every
action in the pinned engine.

## Intake an upstream revision

An upstream update is a source review, not a dependency-number edit.

1. Resolve the candidate ref from the official remote.
2. Compare it with the current gitlink and classify engine, protocol, build,
   skill-data, license, and dependency changes.
3. Update the pin and synchronized provenance with `make update-upstream`.
4. Let adapter anchor failures identify assumptions that require re-audit.
5. Update typed Python surfaces when the new capability belongs in the stable
   SDK.
6. Run the affected boundary tests, then the full release gate.

[Maintenance](maintenance.md) defines the commands and release sequence.
[Generated adapter](generated-adapter.md) defines the transformation contract.
[Embedded resources](embedded-resources.md) covers upstream data bundled into
an installed artifact.

## Review invariants

- The submodule worktree remains clean.
- Every adaptation is generated and fails when its inspected anchor drifts.
- Installed provenance matches both the gitlink and upstream manifest.
- Python and upstream versions remain independently meaningful.
- Source distributions contain every upstream input required to build without
  a Git submodule checkout.
- Tests assert downstream ownership. Generic upstream behavior remains an
  upstream responsibility.
