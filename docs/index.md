# Documentation

The `pyagentbrowser` distribution runs the native Rust `agent-browser` engine
in-process from Python. Import it as `pyagentbrowser`. It exposes `Browser`,
`AgentSnapshot`, element refs, action evidence, screenshots, browser state, CDP
handles, and embedded upstream skills.

```python
from pyagentbrowser import Browser, LaunchOptions

with Browser.launch(LaunchOptions(headless=True)) as browser:
    browser.page.open("https://example.com")
    page = browser.agent.observe()
    print(page.text)
```

## Start

- [Install](install.md): package install, Chrome requirements, optional extras,
  and source builds.
- [Quickstart](quickstart.md): browser sessions, selectors, snapshot refs,
  screenshots, async usage, and default sessions.

## Reference

- [API reference](api-reference.md): constructor signatures, namespace methods,
  exported models, errors, and version surfaces.
- [Concepts](concepts.md): native sessions, namespaces, refs, confirmations,
  skills, and default-browser lifecycle.
- [Choosing a tool](choosing-a-tool.md): where this SDK fits relative to
  browser-use, Playwright, Selenium, and the upstream CLI.

Reference pages document SDK contracts. Workflow examples stay in the quickstart
and examples directory.

## Maintainers

- [Testing](testing.md): local verification commands and release gates.
- [Development](development.md): maintainer workflow and repo layout.
- [Internals](internals/upstream.md): upstream submodule tracking, adapter
  generation, native safety patches, and package boundaries.

Public examples live in the [examples directory](../examples).
