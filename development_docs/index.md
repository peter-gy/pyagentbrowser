# Contributor documentation

pyagentbrowser is a downstream wrapper around a pinned `agent-browser` engine.
It ships the engine inside a Python distribution, adapts it for in-process use,
and owns the typed Python API, safety policy, evidence model, lifecycle, and
release artifacts around that engine.

Start with [the downstream wrapper model](repository-model.md). It defines what
this repository owns, what remains upstream, and how a change crosses the pin,
generated adapter, native extension, and Python layers.

## Understand the system

| Question                                                            | Page                                                |
| ------------------------------------------------------------------- | --------------------------------------------------- |
| What kind of repository is this, and which source is authoritative? | [Downstream wrapper model](repository-model.md)     |
| How does one operation cross Python, Rust, and the embedded engine? | [Architecture](architecture.md)                     |
| When should a native action become a typed Python API?              | [Python SDK design](python-sdk.md)                  |
| How do snapshots and refs become action-scoped evidence?            | [Evidence and refs](evidence-and-refs.md)           |
| Where is domain containment or confirmation enforced?               | [Safety architecture](safety.md)                    |
| Who owns sessions, async work, sidecars, and teardown?              | [Sessions and lifecycle](sessions-and-lifecycle.md) |
| What does the PyO3 extension own at runtime?                        | [Native extension](native-extension.md)             |
| How does the optional direct CDP path coexist with native actions?  | [Direct CDP](direct-cdp.md)                         |

## Maintain the system

| Task                                                           | Page                                        |
| -------------------------------------------------------------- | ------------------------------------------- |
| Adapt pinned upstream source for in-process embedding          | [Generated adapter](generated-adapter.md)   |
| Update the upstream pin or publish a release                   | [Maintenance](maintenance.md)               |
| Change bundled skills, protocol inputs, provenance, or notices | [Embedded resources](embedded-resources.md) |
| Choose the boundary that proves a change                       | [Testing](testing.md)                       |
| Author or validate public documentation                        | [Documentation](documentation.md)           |
| Change wheel or source-distribution contents                   | [Packaging](packaging.md)                   |

## Source of truth

When summaries disagree with implementation, inspect the nearest owned
contract in this order:

1. Public Python signatures, models, and exports in `src/agentbrowser/`.
2. Python-to-native command construction in `session.py`, `session_async.py`,
   and `command_params.py`.
3. PyO3 resource ownership in `crates/pyagentbrowser/`.
4. Generated adaptation rules in `crates/agent-browser-adapter/build.rs`.
5. The exact pinned source in `third_party/agent-browser/`.
6. Artifact and automation contracts in `pyproject.toml`, the Makefile,
   package scripts, and GitHub workflows.

Tests prove these contracts at their consumer boundaries. They do not replace
the owning source.

## Canonical vocabulary

| Term                      | Meaning                                                                                         |
| ------------------------- | ----------------------------------------------------------------------------------------------- |
| Downstream wrapper        | This repository, which packages and extends a pinned upstream engine for Python                 |
| Upstream engine           | The `agent-browser` source tracked as an exact Git submodule commit                             |
| Upstream pin              | The gitlink commit stored by this repository for `third_party/agent-browser`                    |
| Generated adaptation      | A checked source transformation written to Cargo `OUT_DIR` during the build                     |
| Native extension          | The PyO3 module imported as `agentbrowser._native`                                              |
| High-level operation      | One public Python method call, which can contain several native actions                         |
| Native action             | One engine behavior such as `launch`, `navigate`, or `click`                                    |
| JSON command              | One serialized invocation of a native action                                                    |
| `Browser` controller      | The public synchronous or asynchronous Python object                                            |
| Native session            | The ordered command, policy, identity, and persistence boundary owned by a controller           |
| Browser process           | A locally launched Chrome, Chromium, or Lightpanda engine process                               |
| Attached browser endpoint | An externally owned Chrome DevTools Protocol connection target                                  |
| Tab                       | A browser page target selected by native ID, label, index, or CDP target ID                     |
| Page handle               | Operations bound to one browser page target                                                     |
| Frame handle              | Operations bound to one child browsing context                                                  |
| Direct CDP handle         | A page-target selector or generation-bound execution context from `agentbrowser.cdp`             |
| Explicit saved state      | A file managed through `browser.state`                                                          |
| Keyed restore             | Automatic persistence configured through `RestoreOptions`                                       |
| Dashboard                 | The external observability UI                                                                   |
| Stream                    | The data feed exposed for dashboard observation                                                 |
| Sidecar                   | A native helper process for discovery or control metadata                                       |

Use `pyagentbrowser` for the Python distribution, `agentbrowser` for the import
package, and `agent-browser` for the embedded upstream engine.
