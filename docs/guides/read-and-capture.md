---
title: Read and capture browser content
description: Read rendered or remote documents and write screenshots, PDFs, downloads, and snapshot diffs.
---

# Read and capture browser content

`browser.read()` returns agent-readable content from an explicit URL or from the rendered active tab. `browser.capture` writes page artifacts. `browser.downloads` waits for files produced by the page.

Focused snippets that start from `browser` are partial. Place them inside an active `Browser` context such as the screenshot example.

## Read a document

```python
from agentbrowser import Browser, ReadMode

with Browser() as browser:
    document = browser.read(
        "https://example.com",
        mode=ReadMode.markdown(),
    )

    print(document.final_url)
    print(document.content)
```

An explicit URL can use the engine's HTTP reader before a lazy browser starts. Omit the URL to read the rendered active tab.

`ReadMode` selects the response contract:

| Mode | Result |
| --- | --- |
| `markdown(*, require=False)` | Prefer Markdown. Fall back through a `.md` path, plain text, a matching `llms.txt` link, HTML-to-text conversion, or the raw response body. |
| `html()` | Unprocessed response body, regardless of its media type |
| `outline_only()` | Compact heading outline |
| `llms_index(*, require_markdown=False)` | First `llms.txt` found from the target directory toward the site root |
| `llms_full(*, require_markdown=False)` | First `llms-full.txt` found from the target directory toward the site root |

`ReadResult` records the requested URL, final URL, status, content type, source, truncation state, content, and raw native data.

`llms.txt` is a site-provided Markdown index for language models. The [llms.txt proposal](https://llmstxt.org/) defines its intended shape. `require=True` accepts an exact `text/markdown` response and raises `BrowserError` for another content type. A caller-supplied `Accept` header disables Markdown negotiation fallbacks.

## Capture a screenshot

```python
from agentbrowser import Browser

with Browser.launch() as browser:
    browser.open("https://example.com")
    screenshot = browser.capture.screenshot(
        "example.png",
        full_page=True,
        annotate=True,
    )

print(screenshot.path)
print(screenshot.annotations)
```

Screenshots can target the page or one selector. Set `format` to `png` or `jpeg`. JPEG quality ranges from 0 through 100. `wait_ms` adds a bounded delay before capture and defaults to 100 milliseconds.

Install `pyagentbrowser[images]` for `Screenshot.pil()` and `Screenshot.image`. Notebook frontends can display PNG and JPEG screenshot bytes directly. `Screenshot.marimo()` returns an image for a [marimo](https://marimo.io/) reactive Python notebook when marimo is installed.

## Write a PDF

```python
path = browser.capture.pdf(
    "report.pdf",
    print_background=True,
    prefer_css_page_size=True,
)
```

PDF capture uses the active tab and returns the written `Path`.

## Compare the current page with a baseline

```python
baseline = browser.observe()
# Perform work that can change the page.
diff = baseline.diff()
print(diff.changed, diff.additions, diff.removals)
```

`Snapshot.diff()` captures the current page with the baseline's `SnapshotSpec` and compares origin plus accessibility text. Use `browser.diff.snapshot(baseline_text_or_path, selector=..., compact=..., max_depth=...)` when the baseline is text or a file and the new capture needs explicit options.

## Wait for a download

```python
browser.page.set_content(
    '<a download="report.csv" href="data:text/csv,name%0AAda">Download</a>'
)
path = browser.downloads.download("a[download]", "report.csv")
print(path)
```

Use `downloads.wait(path=None, *, timeout_ms=None)` when another action starts the download. `LaunchOptions.download_path` sets the browser's default download directory.

Screenshots, PDFs, downloads, and read results can contain account data. Store them according to the origin, account, and retention rules described in the [safety model](/concepts/safety#treat-captured-artifacts-as-sensitive).
