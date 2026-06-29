# pyagentbrowser

[![PyPI](https://img.shields.io/pypi/v/pyagentbrowser.svg?label=pip&logo=PyPI&logoColor=white)](https://pypi.org/project/pyagentbrowser/)
[![Release Check](https://github.com/peter-gy/pyagentbrowser/actions/workflows/check-release.yml/badge.svg)](https://github.com/peter-gy/pyagentbrowser/actions/workflows/check-release.yml)
[![License](https://img.shields.io/github/license/peter-gy/pyagentbrowser)](LICENSE)

Python SDK for the native Rust [`agent-browser`](https://github.com/vercel-labs/agent-browser) engine.

Use it to launch Chrome, inspect pages, act on snapshot refs, capture artifacts, and call Chrome DevTools Protocol from Python.

```bash
uv add pyagentbrowser
# or
python -m pip install pyagentbrowser
```

```python
import agentbrowser as ab

browser = ab.configure()
browser.page.open("https://github.com/peter-gy/pyagentbrowser")
browser.capture.screenshot(full_page=True)
```

Local Chrome launches use an installed Chrome or Chromium executable. When none is found, pyagentbrowser prepares Chrome for Testing through the bundled native installer.

## API

- `browser.page`: navigation, content, waits, and readable page extraction
- `browser.agent`: accessibility snapshots with action-ready refs
- `browser.find`: CSS, XPath, text, role, label, and test-id locators
- `browser.capture`: screenshots, PDFs, and action evidence
- `browser.tabs`: tab creation, listing, and switching
- `browser.network`: request logs, routing, HAR, and proxy credentials
- `browser.cdp`: frames, targets, execution contexts, and raw CDP calls

`AsyncBrowser` mirrors the same surface with awaitable methods.

## Extras

```bash
python -m pip install "pyagentbrowser[images]"
python -m pip install "pyagentbrowser[cdp]"
```

- `images` adds Pillow helpers for screenshot objects.
- `cdp` adds WebSocket-backed frame, target, and execution-context evaluation.

## Links

- [Install](docs/install.md)
- [Quickstart](docs/quickstart.md)
- [API reference](docs/api-reference.md)
- [Examples](examples/)
- [agent-browser docs](https://agent-browser.dev/)

## Development

```bash
make install
make check
```

Use `make package` for wheel and sdist smoke checks.

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
