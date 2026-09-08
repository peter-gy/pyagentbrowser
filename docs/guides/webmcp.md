---
title: Invoke page-provided WebMCP tools
description: Discover, invoke, wait for, and cancel browser tools registered by the active page.
---

# Invoke page-provided WebMCP tools

[WebMCP](https://webmachinelearning.github.io/webmcp/) is a browser API draft that lets a page register structured tools for browser agents. Local Chrome launches enable the engine integration by default. Set `LaunchOptions(webmcp=False)` to disable it.

## Trust the page as the tool provider

Tool descriptions, input schemas, annotations, and results are claims from page content. Treat them as untrusted input. The page's tool executor owns application authorization. The agent host should confirm actions with external or consequential effects before invoking them.

## Register, discover, and invoke a tool

```python
from agentbrowser import Browser

with Browser.launch() as browser:
    browser.page.set_content('<output id="result">idle</output>')
    browser.evaluate("""
      (() => {
        if (typeof document.modelContext?.registerTool !== "function") {
          document.body.dataset.webmcpReady = "unavailable";
        } else {
          document.modelContext.registerTool({
            name: "set_message",
            description: "Sets the visible message",
            inputSchema: {
              type: "object",
              properties: {message: {type: "string"}},
              required: ["message"],
              additionalProperties: false
            },
            annotations: {readOnlyHint: false},
            execute: async ({message}) => {
              document.getElementById("result").textContent = message;
              return {message};
            }
          }).then(() => {
            document.body.dataset.webmcpReady = "true";
          });
        }
      })()
    """)
    browser.page.wait_for_function(
        "document.body.dataset.webmcpReady !== undefined"
    )
    if browser.evaluate("document.body.dataset.webmcpReady") != "true":
        print("WebMCP is unavailable in this Chrome build")
    else:
        tools = browser.webmcp.list()
        set_message = next(tool for tool in tools if tool.name == "set_message")
        invocation = browser.webmcp.invoke(
            set_message.name,
            {"message": "Ready"},
            frame_id=set_message.frame_id,
        )
        print(invocation.status, browser.find.css("#result").text())
```

Tool names can repeat across frames. Pass the selected tool's `frame_id` to bind the call to its page context.

## Inspect availability after navigation

Raw navigation data includes `webmcp` when the enabled Chrome integration finds
allowed page tools within its bounded discovery window:

```python
from agentbrowser import Browser

with Browser.launch() as browser:
    navigation = browser.native.data("navigate", url="https://example.com")
    print(navigation.get("webmcp"))
```

The field reports `experimental`, `available`, and `toolCount`. An absent field
can mean the page registers its tools later. Call `browser.webmcp.list()` after
the page is ready to discover those tools.

## Detach from long-running work

The focused snippet assumes `browser`, `tool`, and `params` belong to an active controller and a tool selected from `webmcp.list()`.

```python
invocation = browser.webmcp.invoke(
    tool.name,
    params,
    frame_id=tool.frame_id,
    detach=True,
)

result = browser.webmcp.result(invocation.invocation_id)
```

Call `cancel(invocation_id)` to request cancellation. `WebMCPInvocation` reports pending, completed, canceled, failed, or timed-out state, plus duration, output, truncation, and error details.

WebMCP availability depends on the selected browser engine and build. Unsupported browsers raise `BrowserError`.

See [Capability namespaces](/reference/namespaces#browserwebmcp) and [Models and errors](/reference/models#webmcp-models) for exact contracts.
