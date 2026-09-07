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

Control browsers from Python with the native
[`agent-browser`](https://github.com/vercel-labs/agent-browser) engine.
Inspect a page, act on an element, and get the before-and-after snapshots
with a diff of what changed.

> **Alpha:** The public API and native integration can change between minor
> releases. Pin a version for production automation.

## Get started

```bash
python -m pip install pyagentbrowser
```

Requires Python 3.11 through 3.14. Local browsers run headlessly by default.
The first launch finds Chrome or Chromium, or downloads
[Chrome for Testing](https://developer.chrome.com/blog/chrome-for-testing/)
when needed.

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

`observe()` captures a `Snapshot` of the page's accessible elements. Selecting
a button returns a `Ref`. Clicking it returns an `ActionResult` with `before`,
`after`, and `diff`.
Use [`browser.find`](docs/guides/interact.md) for live element queries.

## Browser workflows

- **Inspect and act.** Navigate pages, fill forms, read documents, and capture
  screenshots and PDFs through typed namespaces.
- **Manage sessions.** Launch a browser or attach to an existing one. Work with
  tabs, cookies, saved state, and explicit cleanup.
- **Control actions.** Configure domain restrictions and confirmation policy
  for operations through the native engine.
- **Compose in Python.** Use synchronous or asynchronous controllers, agent
  skills, and the complete engine protocol through `browser.native`.

## Documentation

[Get started](docs/getting-started.md) ·
[Concepts](docs/concepts/runtime-model.md) ·
[Action evidence](docs/concepts/evidence.md) ·
[Safety](docs/concepts/safety.md) ·
[API reference](docs/reference/browser.md) ·
[Troubleshooting](docs/troubleshooting.md)

The [documentation site](https://peter-gy.github.io/pyagentbrowser/) covers
browser workflows, optional packages, supported platforms, and integrations.
See [examples](examples/) for Python scripts and
[Contributing](CONTRIBUTING.md) for development setup and checks.

## License

pyagentbrowser is licensed under the [Apache License 2.0](LICENSE). See
[NOTICE](NOTICE) for bundled software attribution.
