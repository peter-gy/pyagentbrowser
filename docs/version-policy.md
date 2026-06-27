# Version Policy

`pyagentbrowser` publishes pre-1.0 releases. Public APIs may change when the
change simplifies the launch surface or corrects an unsafe API shape. Each
published version uses the pinned upstream `agent-browser` manifest version as
its version base and records the exact upstream commit.

## Python Support

The package targets Python 3.10, 3.11, 3.12, 3.13, and 3.14. Keep classifiers, tests, and
release notes aligned with that range.

## Public API

Public API is the importable surface from:

- `agentbrowser`
- `agentbrowser.Browser`
- `agentbrowser.AsyncBrowser`
- `agentbrowser.skills`
- documented models such as `AgentSnapshot`, `AgentRef`, `ActionEvidence`,
  `Screenshot`, and `BrowserError`

Internal adapter files, generated Rust source, and `third_party/agent-browser`
are not Python API.

## Breaking Changes

Before a stable `1.0`, breaking changes are allowed when they simplify the
launch surface or correct an unsafe API shape. They still require:

- README and docs updates.
- Example updates.
- Tests that assert the new public shape.
- A changelog or release note once releases are published.

After `1.0`, remove or rename public API only with a deprecation path unless the
old behavior is security-sensitive.

## Upstream Versioning

The Python version uses `third_party/agent-browser/cli/Cargo.toml` as its base
and publishes only pre-release identifiers while the SDK is pre-stable:

```text
<upstream-version>rc<N>
```

For example, a package based on upstream `0.27.2` publishes as `0.27.2rc0`.
The package records the nearest upstream release tag for provenance and exposes
the exact pinned upstream commit through
`agentbrowser.__agent_browser_commit__`, `agentbrowser.__upstream_commit__`,
and the `Upstream agent-browser commit` project URL.

Public PyPI releases cannot use local version labels such as `+gabcdef0`. The
git commit is recorded as package metadata.

Before publishing:

- The `third_party/agent-browser` submodule must be checked out at the upstream
  commit whose `cli/Cargo.toml` version is used by the package version.
- `src/agentbrowser/_version.py` must match the upstream tag, upstream version,
  and short commit.
- `pyproject.toml` must contain a pre-release version and the upstream commit
  Project-URL.
- Upstream behavior changes must be documented in
  [docs/internals/upstream.md](internals/upstream.md).
