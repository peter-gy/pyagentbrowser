# 0002 Python SDK Tool Boundary

## Status

Accepted

## Context

The package is adjacent to established tools: `browser-use`, Playwright,
Selenium, and the upstream `agent-browser` CLI. Because all of them involve
browser automation, the SDK can easily grow APIs that other tools already own.

## Decision

Keep `pyagentbrowser` as a Python SDK for native `agent-browser` artifacts:
snapshots, element refs, action evidence, policy confirmations, launch/session
state, embedded upstream skills, and raw command escape hatches.

Recommend the package when Python code needs `agent-browser` primitives
in-process and typed as Python objects.

## Consequences

The public surface should grow around snapshots, refs, policy, evidence, skills,
CDP, and Python lifecycle ergonomics. New helpers should expose one of those
contracts above the raw `Browser.command(...)` surface.

The user-facing comparison table lives in
[docs/choosing-a-tool.md](../choosing-a-tool.md).
