---
title: Inspect network and page diagnostics
description: Route requests, record HTTP Archive files, inspect browser diagnostics, and run typed accessibility audits.
---

# Inspect network and page diagnostics

The network namespace controls request routing and capture. Diagnostics report console output, page errors, web vitals, accessibility results, and React tree data.

Focused snippets that start from `browser` are partial. Place them inside an active `Browser` context such as the request-routing example.

## Route a request

```python
from agentbrowser import Browser, RouteResponse

with Browser.launch() as browser:
    browser.network.route(
        "**/api/profile",
        RouteResponse(
            status=200,
            body='{"name":"Ada"}',
            content_type="application/json",
        ),
    )
    browser.page.open("https://example.com")
    body = browser.page.evaluate("fetch('/api/profile').then(response => response.text())")
    print(body)
    browser.network.unroute("**/api/profile")
```

`RouteResponse` describes the status, body, content type, and headers sent for every matching request. A JSON body without a content type is sent as `application/json`.

Set `abort=True` without a response to stop matching requests. `resource_types=["fetch", "xhr"]` narrows the route to those request kinds.

### Answer cross-origin requests

A page on one origin that fetches a mocked API on another origin needs CORS headers. Set `allow_origin` to the page origin:

```python
browser.network.route(
    "https://api.example.com/**",
    RouteResponse(body='{"ok":true}', allow_origin="https://app.example.com"),
)
```

The route answers the browser's CORS preflight for that origin and adds `Access-Control-Allow-Origin` to the mocked response.

## Inspect requests

```python
browser.network.requests()  # start capture
browser.page.open("https://example.com")

for request in browser.network.requests(method="GET", status=200):
    detail = browser.network.request(request.id)
    print(request.url, request.status, len(detail.response_body or ""))

browser.network.clear_requests()
```

Capture starts with the first `requests()` call. Filters include URL substring, resource type, method, and status. Each `NetworkRequest` carries request headers, response status and headers, and MIME type. `request(id)` adds the response body. `clear_requests()` empties the capture buffer. `network.credentials()` sets HTTP authentication credentials.

## Record an HTTP Archive

An [HTTP Archive](https://w3c.github.io/web-performance/specs/HAR/Overview.html) file records network request and response metadata.

```python
with Browser.launch() as browser:
    browser.network.har_start(content="text")
    browser.page.open("https://example.com")
    har_path = browser.network.har_stop("trace.har")

print(har_path)
```

`content="text"` embeds text-like bodies up to 2 MiB each. `"all"` also embeds binary bodies as base64. `"none"` records metadata. One recording can embed up to 64 MiB.

HAR files can contain cookies, authorization headers, request data, and response bodies.

## Read browser diagnostics

```python
for message in browser.diagnostics.console():
    print(message.type, message.text)
for error in browser.diagnostics.errors():
    print(error.text, error.url, error.line)

browser.diagnostics.clear_console()
browser.diagnostics.clear_errors()
vitals = browser.diagnostics.vitals()
```

`console()` returns `ConsoleMessage` records and `errors()` returns `PageError` records for uncaught exceptions. The clear methods empty each buffer, so a later read reports only new output.

`diagnostics.vitals()` reloads the active page, waits three seconds for layout shifts and React effects, and returns a raw mapping. Time to First Byte (TTFB), First Contentful Paint (FCP), Interaction to Next Paint (INP), hydration, phase, and component timing values use milliseconds. Largest Contentful Paint (LCP) contains start time, rendered size, element name, and URL. Cumulative Layout Shift (CLS) contains a unitless score and layout-shift entries. The [web.dev metric guides](https://web.dev/explore/learn-core-web-vitals) explain how to interpret these metrics.

React inspection requires the embedded React DevTools hook before application code runs. Set the engine feature before constructing the controller:

```python
import os

from agentbrowser import Browser

os.environ["AGENT_BROWSER_ENABLE"] = "react-devtools"

with Browser.launch() as browser:
    browser.page.open("https://react.dev/")
    tree = browser.diagnostics.react_tree()
    print(tree)
```

`diagnostics.react_tree(*, selector=None)` returns [React](https://react.dev/) component data exposed through that hook. Calling it in a session launched without the feature raises `BrowserError` with the required setup.

## Audit accessibility

Accessibility snapshots support agent interaction. An accessibility audit is a separate workflow that runs the embedded [axe-core](https://github.com/dequelabs/axe-core) rules.

```python
with Browser.launch() as browser:
    audit = browser.diagnostics.accessibility(
        "https://example.com",
        tags=("wcag2a", "wcag2aa"),
    )

for issue in audit.violations:
    print(issue.id, issue.impact, issue.node_count)
```

The tags select [Web Content Accessibility Guidelines](https://www.w3.org/WAI/standards-guidelines/wcag/) rule groups. Pass a URL to navigate before the audit or omit it for the active page. The selector must be valid CSS and match an element. Selector paths remain nested across frames and shadow roots. Audits require a CDP-capable browser.

Use [Models and errors](/reference/models) for the typed audit, network, and console results.
