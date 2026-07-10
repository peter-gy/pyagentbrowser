# pyagentbrowser

[![PyPI](https://img.shields.io/pypi/v/pyagentbrowser.svg?label=pip&logo=PyPI&logoColor=white)](https://pypi.org/project/pyagentbrowser/)
[![Release Check](https://github.com/peter-gy/pyagentbrowser/actions/workflows/check-release.yml/badge.svg)](https://github.com/peter-gy/pyagentbrowser/actions/workflows/check-release.yml)
[![License](https://img.shields.io/github/license/peter-gy/pyagentbrowser)](LICENSE)

pyagentbrowser embeds the native Rust [`agent-browser`](https://github.com/vercel-labs/agent-browser) engine in Python. It gives agents accessibility snapshots, stable element refs, and before-and-after evidence for browser actions.

```bash
uv add pyagentbrowser
```

```python
from agentbrowser import Browser, Wait

with Browser.launch() as browser:
    browser.open("https://example.com")
    page = browser.observe()
    result = page.one(role="link", name="Learn more").click(
        wait=Wait.url("*://www.iana.org/*")
    )

    print(result.after.text)
```

`Browser` owns the native session. `Snapshot` binds accessibility refs to the page state that produced them. Ref actions return an `ActionResult` containing the original snapshot, the resulting snapshot, and their diff.

Use `browser.find` for live CSS, XPath, and semantic queries. Namespaces such as `browser.capture`, `browser.tabs`, `browser.network`, and `browser.cdp` expose focused browser capabilities. Every action in the pinned native engine remains available through `browser.native`.

## Documentation

- [Get started](docs/getting-started.md)
- [Guides](docs/guides.md)
- [API reference](docs/api.md)
- [Runnable examples](examples/)

## Installation options

The distribution is named `pyagentbrowser`. Python imports it as `agentbrowser`. Wheels support Python 3.11 through 3.14 on macOS and Linux.

```bash
uv add "pyagentbrowser[images]"  # Pillow-backed screenshot helpers
uv add "pyagentbrowser[cdp]"     # CDP frames, targets, and evaluation
```

Local launches find an installed Chromium browser or prepare Chrome for Testing through the native installer.

## Development

```bash
make install
make check
```

`make test-integration` exercises the Python, PyO3, adapter, and CDP seams against a real browser. `make check-release` builds and installs both distribution artifacts.

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
