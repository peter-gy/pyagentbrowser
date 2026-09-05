---
title: Observe a session dashboard
description: Stream a Python-owned browser session to the external agent-browser observability dashboard.
---

# Observe a session dashboard

The dashboard is a separate local web interface for live viewport frames and command activity. pyagentbrowser publishes an observation stream while its `Browser` controller retains session creation and browser control.

## Match the dashboard version

Install the upstream [`agent-browser` CLI](https://agent-browser.dev/installation). Match its release to the version embedded in pyagentbrowser:

```bash
required=$(python -c 'import agentbrowser; print(agentbrowser.__agent_browser_version__)')
npm install --global "agent-browser@$required"
agent-browser --version
```

The reported CLI version must match `required`. Start the dashboard after verification:

```bash
agent-browser dashboard start
```

The default local URL is `http://127.0.0.1:4848`.

## Publish a Python session

Configure the stream before the native session starts:

```python
from agentbrowser import Browser, DashboardOptions, SessionOptions

session = SessionOptions(
    session_id="research-agent",
    dashboard=DashboardOptions(port=0),
)

with Browser.launch(session=session) as browser:
    browser.open("https://example.com")
    print(browser.dashboard.status()["port"])
```

Open the dashboard URL and select `research-agent`. The live viewport and activity feed update as Python sends actions.

`DashboardOptions.port=None` lets the engine choose an operating-system-assigned stream port. Port 0 requests the same ephemeral behavior explicitly. Explicit ports range from 1 through 65535. `cli_version` overrides the compatibility version written to discovery metadata. Its default is `AGENT_BROWSER_DASHBOARD_CLI_VERSION`, followed by the embedded engine version.

Dashboard sessions require a `session_id` from 1 through 64 characters with no path separators or null character.

Closing the controller releases the stream and discovery helpers. `browser.dashboard.stop()` stops the stream earlier.

Stop the external dashboard when observation is finished:

```bash
agent-browser dashboard stop
```

Loopback access requires no token. Read the [dashboard security and reverse-proxy guide](https://agent-browser.dev/dashboard) before exposing it beyond the local machine.
