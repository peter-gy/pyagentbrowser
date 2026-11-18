---
title: Environment and platform reference
description: Supported Python and operating-system targets, optional packages, environment variables, timeout units, and embedded-engine provenance.
---

# Environment and platform reference

pyagentbrowser publishes one Python distribution with an ABI3 native extension. [Python's stable application binary interface](https://docs.python.org/3/c-api/stable.html) lets one wheel serve several supported Python versions on the same platform.

## Supported wheels

| Operating system | Architecture | Wheel contract |
| --- | --- | --- |
| macOS | arm64 | Python 3.11 through 3.14 |
| macOS | x86-64 | Python 3.11 through 3.14 |
| Linux | arm64 | manylinux 2.28, Python 3.11 through 3.14 |
| Linux | x86-64 | manylinux 2.28, Python 3.11 through 3.14 |
| Windows | x86-64 | Python 3.11 through 3.14 |

Source installations require the Rust toolchain and build dependencies used by [Maturin](https://www.maturin.rs/), the Python-to-Rust packaging backend.

[manylinux](https://peps.python.org/pep-0600/) is the Python wheel compatibility standard for broadly deployable Linux binaries. The 2.28 tag requires a Linux runtime with glibc 2.28 or newer.

## Optional packages

| Install | Adds |
| --- | --- |
| `pyagentbrowser` | Browser controllers, native engine, snapshots, refs, queries, capabilities, and file capture |
| `pyagentbrowser[images]` | [Pillow](https://pillow.readthedocs.io/) screenshot loading and conversion |
| `pyagentbrowser[cdp]` | WebSocket transport for direct Chrome DevTools Protocol APIs |

`Screenshot.content()` returns a dependency-free `ImageContent` value for an
agent host. Notebook display protocols read the same screenshot bytes.

## Browser selection

Local launch checks the explicit executable environment, the native cache and discovery path, system Chrome or Chromium installations, and browser caches managed by Puppeteer or Playwright. It prepares Chrome for Testing when discovery fails.

| Variable | Contract |
| --- | --- |
| `AGENT_BROWSER_EXECUTABLE_PATH` | Select the local Chrome or Chromium executable. |
| `AGENT_BROWSER_ENGINE` | Select `chrome` or `lightpanda` when `LaunchOptions.engine` is unset. |
| `AGENT_BROWSER_PROVIDER` | Select `browserbase`, `browserless`, `browser-use` or `browseruse`, `kernel`, `agentcore`, `ios`, `safari`, or a configured provider plugin when `LaunchOptions.provider` is unset. |
| `AGENT_BROWSER_CDP` | Attach to an existing browser's Chrome DevTools Protocol port or WebSocket URL when the controller names no `CDPTarget`. |
| `AGENT_BROWSER_CDP_HEADERS` | Send a JSON object of WebSocket headers with the `AGENT_BROWSER_CDP` connection. |
| `AGENT_BROWSER_AUTO_CONNECT` | Discover and attach to a running Chrome instance. `0`, `false`, and `no` leave it off. |
| `AGENT_BROWSER_WEBGPU` | Enable the native local WebGPU preset unless `LaunchOptions.webgpu` overrides it. |
| `AGENT_BROWSER_AUTOSAVE_INTERVAL_MS` | Set keyed restore autosave cadence unless `RestoreOptions.autosave_interval_ms` overrides it. |
| `AGENT_BROWSER_DASHBOARD_CLI_VERSION` | Set the external dashboard version written to session discovery metadata. |
| `AGENT_BROWSER_SOCKET_DIR` | Select the native socket and control-file base directory. Saved browser state uses its separate state directory. |
| `AGENT_BROWSER_ENABLE` | Enable built-in launch features such as `react-devtools` before page scripts run. |
| `AGENT_BROWSER_NO_VERSION_CHECK` | Set to `1` or `true` to skip the Chrome release-feed request behind the outdated-browser `EngineWarning`. |
| `AGENT_BROWSER_FLOWS_DIR` | Select the directory for saved flows. The default is `~/.agent-browser/flows`. |

The engine reads these variables when a controller creates its native session. Explicit Python options take precedence where the same behavior is configurable in `LaunchOptions`, `SessionOptions`, or `RestoreOptions`.

A connection variable selects the browser for every launch of that controller, including `Browser.launch()`. `Browser.attach(CDPTarget(...))` and `LaunchOptions.provider` replace it.

External providers require provider-specific credentials and can create billable remote browser sessions. Follow the [upstream configuration reference](https://agent-browser.dev/configuration) for the embedded engine version.

## Time units

| Surface | Unit |
| --- | --- |
| `SessionOptions.timeout` | Seconds |
| `AsyncBrowser.close(timeout=...)` | Seconds |
| Direct CDP client timeout | Seconds |
| Browser operation `timeout_ms` | Milliseconds |
| `RestoreOptions.autosave_interval_ms` | Milliseconds |
| Screenshot `wait_ms` | Milliseconds |

## Accepted literal values

| Contract | Values |
| --- | --- |
| Load state | `load`, `domcontentloaded`, `networkidle`, `none` |
| Selector wait state | `attached`, `detached`, `hidden`, `visible` |
| Storage area | `local`, `session` |
| Color scheme | `dark`, `light`, `no-preference` |
| Cookie same-site | `Strict`, `Lax`, `None` |
| HAR content | `all`, `text`, `none` |
| Restore save policy | `auto`, `always`, `never` |

## Version and provenance

```python
import agentbrowser

print(agentbrowser.__version__)
print(agentbrowser.__agent_browser_version__)
print(agentbrowser.__agent_browser_commit__)
```

The Python package version and embedded `agent-browser` engine version are separate identities. A package version such as `0.36.0.2` embeds upstream tag `v0.36.0` and identifies the second downstream update on that tag. Each release records the exact upstream commit in the installed package.

The current package is classified as Alpha. Pin the package version for production workflows and review changes before upgrading.
