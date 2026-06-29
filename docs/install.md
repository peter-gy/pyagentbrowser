# Install

## Package

```bash
uv add pyagentbrowser
# or
python -m pip install pyagentbrowser
```

The distribution package is `pyagentbrowser`. Import it as `agentbrowser`.

```python
from agentbrowser import Browser
```

## Requirements

- Python 3.11, 3.12, 3.13, or 3.14.
- macOS or Linux.
- Rust stable only when building from source.

For local Chrome launches, pyagentbrowser searches the native `agent-browser`
browser cache, system Chrome and Chromium locations, and browser caches from
Puppeteer or Playwright. When the search misses, the Python package runs the
bundled native Chrome for Testing installer before launch.

Prepare Chrome before the first browser command:

```python
import agentbrowser

result = agentbrowser.ensure_installed()
print(result.executable_path)
```

Pass an executable path when a program should use a specific Chromium-based
browser:

```python
from agentbrowser import Browser

with Browser.launch(
    {"executable_path": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"}
) as browser:
    browser.page.open("https://example.com")
```

## Optional Extras

```bash
uv add "pyagentbrowser[images]"
uv add "pyagentbrowser[cdp]"
```

- `images` installs Pillow support for `Screenshot.image` and `Screenshot.pil()`.
- `cdp` installs WebSocket support for frame, target, and execution-context
  evaluation.

## Source Builds

Clone the repository and run:

```bash
make install
```

Source distributions include the selected upstream Rust source slice needed to
build the native extension. Runtime wheels do not require an `agent-browser` CLI
installation.
