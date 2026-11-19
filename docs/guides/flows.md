---
title: Record and run saved flows
description: Record a browser task once, save its first-party JSON requests as a named flow, and run it again with new parameters.
---

# Record and run saved flows

A saved flow is a browser task recorded once and stored as the first-party JSON requests the page sent. `browser.flows.run()` sends those requests again with new parameter values and returns the JSON answer, so a repeated lookup skips the page.

Saved flows are experimental in the embedded engine. A run can fail on a site that changed, and the engine then marks the flow unverified.

## Record, save, and run

Launch with `capture=["flow"]` to record the session's commands and the requests each one caused:

```python
from agentbrowser import Browser, LaunchOptions

with Browser.launch(LaunchOptions(capture=["flow"])) as browser:
    browser.page.open(f"{site}/?q=stove", wait_until="networkidle")
    for step in browser.flows.steps().steps:
        print(step.seq, step.command, step.requests)

    saved = browser.flows.save("catalog-search", params={"q": "stove"})
    print(saved.params, saved.output, [request.url for request in saved.requests])

with Browser() as browser:
    run = browser.flows.run("catalog-search", params={"q": "lamp"}, fields=["title"])
    print(run.steps[0].tier, run.data)
    print(browser.is_launched)
```

```text
1 navigate http://127.0.0.1:62661/?q=stove 3
('q',) s1r1 ['http://127.0.0.1:62661/api/search?q={{q}}']
http {'items': [{'title': 'lamp one'}, {'title': 'lamp two'}], 'list': 'items', 'matched': 2, 'total': 2}
False
```

This snippet is partial. `site` is a page that fetches `/api/search?q=...` from its own origin. [`examples/saved_flow.py`](https://github.com/peter-gy/pyagentbrowser/blob/main/examples/saved_flow.py) is the complete script with a local site.

- `flows.steps()` returns the `FlowRecording`: one `FlowStep` per recorded command with its request count.
- `flows.save(name, params={"q": "stove"})` keeps the first-party JSON requests and replaces every occurrence of the recorded value `stove` with the parameter `q`.
- `flows.run(name, params={"q": "lamp"})` sends the saved requests with the new value and returns a `FlowRun`. The second controller never launched a browser, because a direct HTTP request answered the run.

## Read the save report

`SavedFlow` describes what the flow will send:

| Field | Contract |
| --- | --- |
| `requests` | Saved requests with IDs such as `s1r1`, numbered by step and request. |
| `output` | ID of the request whose answer `run()` returns. Pass `output=` to `save()` to choose another one. |
| `params` | Parameter names a run accepts. |
| `writes` | Requests that change state on the site, each with an `id` and a `kind` of `explicit` or `suspected`. |
| `gaps` | Recorded commands that produced no saved request, each with a reason. |
| `dropped_headers` | Header names removed from the saved requests. |
| `path` | The flow file, under `AGENT_BROWSER_FLOWS_DIR` or `~/.agent-browser/flows/<host>/`. |

A flow file holds no cookies, `authorization` headers, or token headers. A run reads cookies from the live session when a browser is open. A value typed into a password or other secret field is stored as `<redacted>`, and its step is never replayed.

`save()` covers the steps from the last navigation after the previous save to the last recorded step. Pass `from_step` and `to_step` to save another range. Saving leaves capture running, so one session can save several flows.

## Shape the result

```python
run = browser.flows.run(
    "catalog-search",
    params={"q": "lamp"},
    where={"title": "two"},
    fields=["title"],
    limit=1,
)
print(run.data)
# {'list': 'items', 'total': 2, 'matched': 1, 'items': [{'title': 'lamp two'}]}
```

`where` keeps the list items whose named field contains the text, `fields` keeps the listed dotted paths of each item, and `limit` caps the item count. Without them, `run.data` is the JSON body of the output request.

## Follow the tier a run used

A run tries each request as a direct HTTP request, then as a `fetch()` from the active tab, then by replaying the recorded commands in a browser. `FlowRunStep.tier` reports `http`, `page`, or `replay`, and `FlowRunStep.fell_back` lists the earlier attempts. The replay tier launches a browser from the session's settings when none is open. Call `Browser.launch()` first when that browser needs specific `LaunchOptions`.

Every tier compares the answer with the recorded response shape. `FlowRun.verified` is `False` and `FlowRun.drift` names the tier and reason when one tier saw a changed shape and a later tier answered. Record the task again to restore a verified flow.

## Approve writes

A flow that submits a form or deletes a record lists those requests in `SavedFlow.writes`. A run sends a write only when `allow_writes` covers it:

```python
from agentbrowser import ConfirmationRequired

try:
    run = browser.flows.run("archive-invoice", params={"id": "42"})
except ConfirmationRequired as required:
    print(required.policy_action)  # flow_write:s2r1
    run = required.pending.confirm()

run = browser.flows.run("archive-invoice", params={"id": "43"}, allow_writes=["s2r1"])
```

Each confirmation approves one write, so `confirm()` raises `ConfirmationRequired` again for the next uncovered write. Pass `allow_writes="all"` to cover every write of the flow. `SessionOptions.confirm_actions` and an action policy match `flow_run` and each `flow_write:<id>` by exact name.

## Handle a stopped run

`flows.run()` raises `FlowRunError`, a `BrowserError` subclass, when the site stops the run. Branch on `status`:

| `status` | Meaning | Next step |
| --- | --- | --- |
| `auth_expired` | The site answered 401 or 403. | Sign in through the page, then run again. |
| `rate_limited` | The site answered 429. `retry_after` holds its hint. | Wait, then run again. |
| `blocked` | A bot challenge answered the request. | Use the page. |
| `drifted` | Every tier saw a changed response shape. | Use the page, then record and save the flow again. |
| `outcome_unknown` | A write got no usable answer. | Check the site before running again. The write is never resent. |
| `write_applied` | A write succeeded with a changed response shape. | Treat the write as done. Record the flow again. |
| `credential_not_sendable`, `request_signed` | The request needs a credential or signature that only the page produces. | Use the page. |
| `address_refused` | The host resolved to an address a run does not send to. | Run against the address class the flow was recorded on. |

`FlowRunError` also exposes `flow`, `step`, and `http_status`. A run that fails for another reason, such as a rejected parameter value, raises a plain `BrowserError`.

## Know where a run sends requests

A run sends requests only to hosts inside the registrable domain of the flow's start URL, and the session's `allowed_domains` applies on top. A direct request goes only to public addresses. A flow recorded against `localhost` or a private address runs only against that address class.

`flows.list(origin="example.com")` returns a `FlowSummary` for each flow saved for that registrable domain, with its parameters, recorded example values, and `verified_at` time. Pass `origin=` to `run()` when two sites have a flow with the same name.

## Capture owns network recording

A capturing session keeps the engine's HTTP Archive recorder running. `browser.network.har_start()` and `har_stop()` raise `BrowserError` on that session. `Browser.close()` reports commands recorded after the last save in `CloseResult.unsaved_flow_steps`.

See [`browser.flows`](/reference/namespaces#browser-flows) for signatures and [Flow models](/reference/models#flow-models) for fields.
