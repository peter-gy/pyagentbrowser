# pyagentbrowser

[![PyPI](https://img.shields.io/pypi/v/pyagentbrowser.svg?label=pip&logo=PyPI&logoColor=white)](https://pypi.org/project/pyagentbrowser/)
[![Release Check](https://github.com/peter-gy/pyagentbrowser/actions/workflows/check-release.yml/badge.svg)](https://github.com/peter-gy/pyagentbrowser/actions/workflows/check-release.yml)
[![License](https://img.shields.io/github/license/peter-gy/pyagentbrowser)](LICENSE)

`pyagentbrowser` gives Python a native browser controller for Chrome. Import it
as `agentbrowser` and drive pages through `page`, `find`, `agent`, `capture`,
`tabs`, `network`, and `cdp`.

```bash
python -m pip install pyagentbrowser
```

Requires Python 3.11 through 3.14 on macOS or Linux, with Chrome or Chromium
available on the host.

## Use

The package root owns one process-local browser for REPLs, notebooks, and short
scripts.

```python
import agentbrowser as ab

ab.configure(launch={"headless": True})
try:
    ab.page.open("https://example.com")
    page = ab.agent.observe()
    print(page.text)

    ab.find.text("Learn more").click()
    ab.page.wait_for_url("*://www.iana.org/*")
    print(ab.page.url())
finally:
    ab.close()
```

`ab.reset(force=True)` discards the default browser after an interrupted run.

Use `Browser` when a browser needs an explicit lifetime or when a program owns
more than one session.

```python
from agentbrowser import Browser

with Browser.launch({"headless": True}) as browser:
    browser.page.open("https://example.com")
    print(browser.page.title())
```

## Workflows

- Navigate pages, wait for load states, switch tabs, and attach to running
  Chrome through CDP.
- Observe accessibility snapshots, resolve refs by text, role, name, CSS, or
  XPath, then click, fill, press, or inspect matching elements.
- Capture action evidence with `click_and_observe()` and
  `fill_and_observe()`.
- Save screenshots, PDFs, cookies, storage state, network logs, console output,
  and session restore data.
- Drop to `browser.native.execute(...)` for raw native commands or `browser.cdp`
  for frame and execution-context work.

## Extras

```bash
python -m pip install "pyagentbrowser[images]"
python -m pip install "pyagentbrowser[cdp]"
```

`images` adds Pillow helpers for screenshots. `cdp` adds WebSocket-backed frame,
target, and execution-context evaluation.

## Docs

- [Install](docs/install.md)
- [Quickstart](docs/quickstart.md)
- [API reference](docs/api-reference.md)
- [Examples](examples/)

## Acknowledgements

Built with Apache-2.0 source from Vercel Labs'
[`agent-browser`](https://github.com/vercel-labs/agent-browser). This project
is independent and not affiliated with Vercel.
