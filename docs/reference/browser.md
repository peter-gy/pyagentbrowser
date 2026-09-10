---
title: Browser controller reference
description: Exact construction, lifecycle, configuration, installation, and page-handle contracts for Browser and AsyncBrowser.
---

# Browser controller reference

Import the public controller and configuration objects from `agentbrowser`.

```python
from agentbrowser import Browser, LaunchOptions, SessionOptions
```

`AsyncBrowser` exposes the same operations with awaitable engine calls.

## Construction

| API | Contract |
| --- | --- |
| `Browser(*, session=None)` | Create a lazy controller. The first browser-dependent operation launches a local browser. |
| `Browser.launch(options=None, *, session=None)` | Launch a local browser and return an active controller. |
| `Browser.attach(target, *, launch=None, session=None)` | Connect to one browser debugging endpoint and select a responsive tab. |
| `AsyncBrowser(...)` | Create the asynchronous lazy controller. |
| `await AsyncBrowser.launch(...)` | Launch before returning the asynchronous controller. |
| `await AsyncBrowser.attach(...)` | Attach before returning the asynchronous controller. |

`Browser.launch()` raises `BrowserInstallError` when browser preparation fails and `BrowserError` when native launch fails.

`Browser.attach()` accepts `agentbrowser.CDPTarget` with exactly one port or WebSocket URL. If every available renderer is discarded, attachment attempts to reactivate the first tab before failing.

## Lifecycle

| Member | Contract |
| --- | --- |
| `closed` | Report terminal controller state. |
| `is_launched` | Report whether this controller has observed an active browser. |
| `close() -> CloseResult` | Release owned resources. Repeated calls return the cached terminal result or re-raise the cached close error. |
| `AsyncBrowser.close(*, timeout=5.0)` | Share one close operation across callers and wait up to `timeout` seconds. |
| `activate()` | Bring the local browser window forward and return the controller. |

Both controllers support context managers. Commands after close raise `RuntimeError`.

Closing releases controller-owned browser, dashboard stream, direct CDP, confirmation, and native helper-process resources. A persistence failure completes cleanup, then raises `RestoreSaveError` with the terminal `CloseResult` on `error.result`.

## `browser.page`

| Method | Returns | Behavior |
| --- | --- | --- |
| `open(url, *, wait_until="load")` | `None` | Normalize a host-like URL, launch when needed, and navigate. |
| `observe(spec=None)` | `Snapshot` | Capture an accessibility snapshot and bind its refs to this document. |
| `read(url=None, *, mode=None, filter=None, timeout_ms=None, headers=None, allowed_domains=None)` | `ReadResult` | Read an explicit URL or this page's rendered document. `filter` narrows headings or `llms.txt` sections. |
| `title()` | `str` | Return this document's title. |
| `url()` | `str` | Return this document's URL. |
| `content()` | `str` | Return this document's HTML. |
| `evaluate(script)` | JSON-compatible value | Evaluate JavaScript through the native engine. |
| `wait_for_text(text, *, timeout_ms=None)` | `None` | Wait for page text. |
| `wait_for_url(url, *, timeout_ms=None)` | `None` | Wait for a native URL pattern. |
| `wait_for_load(state="load")` | `None` | Wait for a load state. |

`browser.page` also provides document replacement, history, readiness, selector,
function, frame, capture, scrolling, and geometry operations.

`capabilities(host=None)` reports configured screenshot, image, direct CDP, and
host-delivery features. `healthcheck()` imports optional image and WebSocket
dependencies and reports their loaded module paths. Both methods avoid browser
startup.

`read()` requires a positive `timeout_ms` when supplied. `headers` adds HTTP request headers. A caller-supplied `Accept` header disables Markdown negotiation fallbacks. `allowed_domains` adds a read-specific allowlist, and every redirect or fallback URL must satisfy it plus the session allowlist.

## `LaunchOptions`

`LaunchOptions` is a frozen dataclass passed to `launch()` or as `Browser.attach(..., launch=...)`.

| Field | Default | Contract |
| --- | --- | --- |
| `headless` | `True` | Run a local browser without a visible window. |
| `executable_path` | `None` | Select a Chrome or Chromium executable. |
| `engine` | `None` | Select `chrome` or `lightpanda`. Chrome is the default. |
| `profile` | `None` | Use a browser profile directory. |
| `storage_state` | `None` | Load serialized browser storage state during launch. |
| `extensions` | `()` | Load extension paths. |
| `proxy` | `None` | Accept a URL, `ProxyConfig`, or proxy mapping. |
| `ca_cert` | `None` | Read a private proxy certificate authority from a filesystem path containing a Privacy-Enhanced Mail (PEM) bundle or Distinguished Encoding Rules (DER) certificate. |
| `provider` | `None` | Select a built-in or configured external browser provider. |
| `color_scheme` | `None` | Set `dark`, `light`, or `no-preference`. |
| `hide_scrollbars` | `None` | Control native scrollbar visibility. |
| `webgpu` | `None` | Inherit native behavior. `True` enables the local [WebGPU](https://www.w3.org/TR/webgpu/) graphics and compute preset. |
| `webmcp` | `None` | Inherit native behavior. `False` disables the local Chrome WebMCP integration. |
| `no_xvfb` | `None` | Inherit native behavior. `True` disables [Xvfb](https://www.x.org/releases/current/doc/man/man1/Xvfb.1.xhtml), the virtual X display used for headed Linux launches. |
| `args` | `()` | Add browser command-line arguments. |
| `allow_file_access` | `False` | Permit `file:` URL access. |
| `ignore_https_errors` | `False` | Continue through certificate validation errors. |
| `user_agent` | `None` | Set the launch user agent. |
| `download_path` | `None` | Set the default download directory. |

Pass sequences for `extensions` and `args`. Scalar strings raise `TypeError`.

`ca_cert` requires a local Chrome engine on Linux. It conflicts with browser profiles, `ignore_https_errors`, CDP attachment, and provider connections. The host needs `certutil` from `libnss3-tools` on Debian or Ubuntu, or `nss-tools` on RPM Linux.

WebGPU and `no_xvfb=True` apply to local launches. External endpoints and provider connections reject those settings.

Built-in providers are `browserbase`, `browserless`, `browser-use` or `browseruse`, `kernel`, `agentcore`, `ios`, and `safari`. A configured browser-provider plugin can supply another name. Provider sessions require their service credentials, network access, and platform setup. Use the [upstream provider configuration](https://agent-browser.dev/configuration) for the engine version reported by `agentbrowser.__agent_browser_version__`.

When attaching, `CDPTarget` supplies the endpoint and `launch` supplies remaining browser settings. Attachment rejects profiles, extensions, `ca_cert`, WebGPU, `no_xvfb=True`, and session domain containment. Local executable and browser-argument fields have no local process to configure.

[Lightpanda](https://lightpanda.io/) is a headless browser engine designed for machine workloads. Install its binary before selecting it. Profiles, storage-state launch, extensions, file access, headed mode, WebGPU, private CA import, and custom Chrome arguments are Chrome-specific. The [agent-browser Lightpanda guide](https://agent-browser.dev/engines/lightpanda) records its installation and current protocol coverage.

## `SessionOptions`

| Field | Default | Contract |
| --- | --- | --- |
| `session_id` | `None` | Name the native session and its optional pinned tab binding. |
| `restore` | `None` | Configure keyed restore persistence. |
| `namespace` | `None` | Separate native control and saved-state paths. |
| `timeout` | `15.0` | Set the default timeout in seconds. `None` disables it. |
| `allowed_domains` | `()` | Restrict exact hosts and wildcard suffixes. |
| `action_policy` | `None` | Load a JSON policy with exact native action names. |
| `confirm_actions` | `()` | Request confirmation for exact native action names. |
| `auto_dialogs` | `True` | Enable automatic JavaScript dialog handling. |
| `pin_tab` | `None` | Leave sticky session state unchanged. `True` enables and persists strict binding. `False` disables it. |
| `dashboard` | `None` | Configure dashboard observability before startup. |

The timeout must be non-negative. Domain and action entries must contain text. Sequence fields reject scalar strings.

`allowed_domains` requires a fresh browser context. It conflicts with keyed restore, storage-state replay, profiles, CDP attachment, auto-connect, iOS or Safari providers, and browser arguments that can open pages before containment.

See [Safety model](/concepts/safety#confirm-selected-actions) for the policy schema, evaluation order, exact-name rule, and confirmation replay behavior.

## `RestoreOptions`

```python
RestoreOptions(
    key,
    save=None,
    autosave_interval_ms=None,
    check_url=None,
    check_text=None,
    check_fn=None,
)
```

The key accepts letters, numbers, hyphens, and underscores. `save` accepts `auto`, `always`, or `never`. `autosave_interval_ms` accepts a non-boolean integer from 0 through 18446744073709551615.

The optional checks validate restored state through a URL pattern, page text, or JavaScript predicate.

## `CDPTarget`

`CDPTarget(url=None, port=None, auto_connect=True)` configures attachment to an existing browser. Pass exactly one URL or port. Ports range from 1 through 65535.

This top-level configuration type differs from `agentbrowser.cdp.CDPTarget`, which is a direct page-target handle returned by `browser.cdp.target()`.

## `ProxyConfig`

`ProxyConfig(server, bypass=None, username=None, password=None)` supplies a proxy server, optional bypass rules, and optional credentials.

## `DashboardOptions`

`DashboardOptions(port=None, cli_version=None)` configures the dashboard stream. Port 0 requests an ephemeral port. Explicit ports range from 1 through 65535. `cli_version` writes an expected dashboard CLI version into discovery metadata. Its default comes from `AGENT_BROWSER_DASHBOARD_CLI_VERSION`, then the embedded engine version.

## Browser installation

`ensure_installed(*, progress=True) -> InstallResult` selects a configured, cached, or system browser and prepares Chrome for Testing when discovery fails. `progress=True` allows native installer progress on the terminal.

`InstallResult` exposes `executable_path`, optional `version`, `source`, and `installed`. Source is `environment`, `cache`, `system`, or `download`.

## Derived session IDs

`session_id(*, scope="worktree", prefix=None, path=None) -> SessionId` derives a stable identifier from a worktree, current directory, or Git root. Converting `SessionId` to `str` returns the value accepted by `SessionOptions.session_id`.

See [Capability namespaces](/reference/namespaces) for the controller's focused APIs and [Models and errors](/reference/models) for return types.
