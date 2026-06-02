# Choosing A Tool

Use the tool that owns the workflow. `pyagentbrowser` is the right fit only
when Python code needs native `agent-browser` artifacts in-process.

| Tool | Use It For | Do Not Use It For |
| --- | --- | --- |
| `pyagentbrowser` | Python-native access to `agent-browser` snapshots, refs, action evidence, policy confirmations, browser state, CDP-backed frame evaluation, and embedded skills | Autonomous agent orchestration, Playwright parity, WebDriver compatibility, or shell workflows |
| `browser-use` | LLM task loops, model integrations, tool registries, hosted/cloud browsers, MCP, and autonomous browser agents | A small in-process SDK over native `agent-browser` state |
| `agent-browser` CLI | Shell commands, agent tool calls, daemon workflows, dashboard startup, and manual CLI debugging | Python object APIs, typed exceptions, or async Python lifecycle management |
| Playwright Python | Deterministic browser testing, fixtures, tracing, browser matrix coverage, and stable locator semantics | Native `agent-browser` snapshots, `@eN` refs, policy exceptions, or action evidence |
| Selenium | W3C WebDriver, Selenium Grid, remote browser vendors, and enterprise browser infrastructure | In-process `agent-browser` refs, evidence, skills, or policy confirmation handling |

## Decision Rule

Choose `pyagentbrowser` if one of these is central:

- The caller is Python code and should not orchestrate a subprocess daemon.
- The workflow uses `observe()`, `AgentSnapshot`, `AgentRef`, or
  `ActionEvidence`.
- Native policy confirmations should become Python exceptions.
- The code needs browser state, downloads, frames, or CDP evaluation through the
  same native session.
- An agent needs installed access to upstream `agent-browser` skill guidance.

Choose something else when those are not central.

The durable rationale lives in
[ADR 0002](adr/0002-python-sdk-tool-boundary.md).
