# pyagentbrowser

[![PyPI](https://img.shields.io/pypi/v/pyagentbrowser.svg?label=pip&logo=PyPI&logoColor=white)](https://pypi.org/project/pyagentbrowser/)
[![Release Check](https://github.com/peter-gy/pyagentbrowser/actions/workflows/check-release.yml/badge.svg)](https://github.com/peter-gy/pyagentbrowser/actions/workflows/check-release.yml)
[![License](https://img.shields.io/github/license/peter-gy/pyagentbrowser)](LICENSE)

`pyagentbrowser` drives the native Rust `agent-browser` engine from Python. It
exposes page navigation, browser snapshots, element refs, action evidence,
screenshots, cookies, storage, frames, and CDP helpers through one Python
package.

```bash
python -m pip install pyagentbrowser
```

Requires Python 3.10 through 3.14 on macOS or Linux, with Chrome or Chromium
available on the host.

## Usage

```python
from pyagentbrowser import Browser

with Browser(headless=True) as browser:
    browser.page.open("https://example.com")

    page = browser.agent.observe()
    print(page.text)

    browser.find.text("More information").click()
```

Snapshot refs stay tied to the page state that created them. After navigation
or a large DOM update, call `browser.agent.observe()` again and continue from
the new snapshot.

For notebooks and REPL sessions, `pyagentbrowser` also exposes one process-local
default browser:

```python
import pyagentbrowser as pab

pab.configure(headless=True, allowed_domains="*.example.com")
pab.page.open("example.com")

page = pab.agent.observe()
pab.find.text("More information").click()

print(pab.page.title(), pab.page.url())
pab.close()
```

Use `pab.reset(force=True)` after an interrupted notebook run when the native
browser state should be discarded.

## Capabilities

- **Native browser control:** Launch Chrome, attach over CDP, navigate pages,
  switch tabs, wait for readiness, and close sessions.
- **Snapshot-driven actions:** Observe an accessibility snapshot, find refs by
  text, role, name, CSS, or XPath, then fill, click, press, or inspect the
  matching element.
- **Evidence after actions:** Use `click_and_observe()` to capture the next
  page snapshot and a text diff after a click.
- **Artifacts and state:** Capture screenshots, save and restore browser state,
  inspect cookies, storage, network entries, and frame content.
- **Typed escape hatches:** Call `Browser.command(action, **params)` for raw
  native commands, or use `browser.cdp` for frame and execution-context work.

## Optional Extras

```bash
python -m pip install "pyagentbrowser[images]"
python -m pip install "pyagentbrowser[cdp]"
```

`images` adds Pillow helpers for screenshots. `cdp` adds websocket-backed CDP
frame and context evaluation.

## Resources

- [Install](docs/install.md)
- [Quickstart](docs/quickstart.md)
- [Concepts](docs/concepts.md)
- [API reference](docs/api-reference.md)
- [Examples](examples/)
- [Choosing a tool](docs/choosing-a-tool.md)
- [Development](docs/development.md)
- [Security](SECURITY.md)
