<p align="center">
  <a href="https://peter-gy.github.io/pyagentbrowser/">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://peter-gy.github.io/pyagentbrowser/brand/pyagentbrowser-lockup-horizontal-dark.svg">
      <img alt="pyagentbrowser" src="https://peter-gy.github.io/pyagentbrowser/brand/pyagentbrowser-lockup-horizontal-light.svg" width="420">
    </picture>
  </a>
</p>

<p align="center">
  Native browser automation with typed Python APIs and before-and-after evidence.
</p>

<p align="center">
  <a href="https://peter-gy.github.io/pyagentbrowser/">Documentation</a> ·
  <a href="https://peter-gy.github.io/pyagentbrowser/getting-started.html">Get started</a> ·
  <a href="examples/">Examples</a> ·
  <a href="https://pypi.org/project/pyagentbrowser/">PyPI</a> ·
  <a href="https://github.com/peter-gy/pyagentbrowser/issues">Issues</a>
</p>

<p align="center">
  <a href="https://pypi.org/project/pyagentbrowser/"><img alt="PyPI version" src="https://img.shields.io/pypi/v/pyagentbrowser.svg?logo=PyPI&logoColor=white"></a>
  <a href="https://pypi.org/project/pyagentbrowser/"><img alt="Python 3.11 through 3.14" src="https://img.shields.io/badge/python-3.11%E2%80%933.14-3776AB.svg"></a>
  <a href="https://github.com/peter-gy/pyagentbrowser/actions/workflows/check-release.yml"><img alt="Release Check" src="https://github.com/peter-gy/pyagentbrowser/actions/workflows/check-release.yml/badge.svg"></a>
  <a href="LICENSE"><img alt="Apache-2.0 license" src="https://img.shields.io/github/license/peter-gy/pyagentbrowser"></a>
</p>

pyagentbrowser embeds the native Rust
[`agent-browser`](https://github.com/vercel-labs/agent-browser) engine in a
Python process. A `Browser` controller owns startup, ordered native work,
snapshot-scoped element refs, safety policy, direct browser capabilities, and
terminal cleanup.

> **Alpha:** The public API and native integration can change between minor
> releases. Pin a version for production automation.

## Quickstart

Install pyagentbrowser from the Python Package Index:

```bash
python -m pip install pyagentbrowser
```

The first local launch selects a configured, cached, or installed Chrome or
[Chromium](https://www.chromium.org/chromium-projects/) executable. When
discovery finds none, pyagentbrowser downloads
[Chrome for Testing](https://developer.chrome.com/blog/chrome-for-testing/).
Local browsers run headlessly by default.

```python
from agentbrowser import Browser

with Browser.launch() as browser:
    browser.page.set_content(
        "<button onclick=\"this.textContent='Done'\">Run</button>"
    )
    snapshot = browser.observe()
    result = snapshot.one(role="button", name="Run").click()

    print(result.after.one(role="button").name)
    print(result.diff.changed)
```

```text
Done
True
```

## The evidence model

`Browser.observe()` returns an accessibility `Snapshot`. Each `Ref` identifies
one element inside that snapshot. A ref mutation returns an `ActionResult` with
the source snapshot, resulting snapshot, and their `SnapshotDiff`.

```text
Snapshot A -> Ref -> action and wait -> Snapshot B -> SnapshotDiff
```

Use `browser.find` for live CSS, XPath, role, text, label, placeholder,
alternative text, title, and test ID queries. Live queries resolve when each
operation runs. Snapshot-scoped refs preserve the inspected page state and add
transition evidence.

## What you can automate

- [Navigate, inspect, and act on pages](https://peter-gy.github.io/pyagentbrowser/guides/interact.html)
- [Read documents and capture screenshots, PDFs, diffs, and downloads](https://peter-gy.github.io/pyagentbrowser/guides/read-and-capture.html)
- [Manage tabs, named sessions, cookies, Web Storage, and restored state](https://peter-gy.github.io/pyagentbrowser/guides/tabs-and-state.html)
- [Route requests, record HTTP Archive files, and inspect diagnostics](https://peter-gy.github.io/pyagentbrowser/guides/network-and-diagnostics.html)
- [Evaluate targets, frames, and contexts through the Chrome DevTools Protocol](https://peter-gy.github.io/pyagentbrowser/guides/cdp.html)
- [Invoke page-provided WebMCP tools](https://peter-gy.github.io/pyagentbrowser/guides/webmcp.html)
- [Observe a Python-owned browser session in the dashboard](https://peter-gy.github.io/pyagentbrowser/guides/dashboard.html)
- [Use agent skills and marimo code mode](https://peter-gy.github.io/pyagentbrowser/guides/agent-skills.html)
- [Call the raw native protocol](https://peter-gy.github.io/pyagentbrowser/guides/native-protocol.html)

## Choose a runtime

`Browser` is synchronous. `AsyncBrowser` mirrors its browser, snapshot, ref,
query, policy, and capability APIs with awaitable native operations.

`Browser.launch()` starts a local browser before returning. `Browser()` starts
lazily. `Browser.attach(CDPTarget(...))` connects to an existing Chrome DevTools
Protocol endpoint. All three paths share the same typed result and lifecycle
model.

## Installation options

Wheels support Python 3.11 through 3.14 on macOS arm64 and x86-64,
[manylinux 2.28](https://peps.python.org/pep-0600/)-compatible Linux arm64 and
x86-64, and Windows x86-64.

```bash
uv add pyagentbrowser
uv add "pyagentbrowser[images]"  # Pillow image loading for Screenshot
uv add "pyagentbrowser[cdp]"     # Direct Chrome DevTools Protocol clients
```

## Learn and contribute

- [What is pyagentbrowser?](https://peter-gy.github.io/pyagentbrowser/introduction.html)
- [Runtime model](https://peter-gy.github.io/pyagentbrowser/concepts/runtime-model.html)
- [Safety model](https://peter-gy.github.io/pyagentbrowser/concepts/safety.html)
- [API reference](https://peter-gy.github.io/pyagentbrowser/reference/browser.html)
- [Troubleshooting](https://peter-gy.github.io/pyagentbrowser/troubleshooting.html)
- [Contributing](CONTRIBUTING.md)

Serve the documentation through [Portless](https://portless.sh/) with
`make docs-dev`. The main checkout uses
`https://docs.pyagentbrowser.localhost/`, while linked worktrees receive a
branch-prefixed subdomain.

## License

pyagentbrowser is licensed under the [Apache License 2.0](LICENSE). See
[NOTICE](NOTICE) for bundled software attribution.
