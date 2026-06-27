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
- Chrome or Chromium available to the native `agent-browser` engine.
- Rust stable only when building from source.

If Chrome is not on the default path, pass an executable path:

```python
from agentbrowser import Browser, LaunchOptions

with Browser.launch(
    LaunchOptions(executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
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
