# Lifecycle and safety

## Persistent code-mode sessions

Code-mode scratchpad calls may receive fresh Python locals. Create a controller
through `agentbrowser.agent` so the module owns it between calls:

```python
import agentbrowser as ab
import agentbrowser.agent as browser_agent

browser = browser_agent.create(
    "research",
    session=ab.SessionOptions(session_id="research-browser"),
)
browser.page.open("https://example.com")
```

Later kernel calls retrieve the same controller by connection name:

```python
browser = browser_agent.get("research")
print(browser.page.observe().text)
```

Pass session options while creating the controller. Duplicate names raise
`ValueError` before another controller is created. Close and forget the
controller once the task ends:

```python
browser_agent.close("research")
```

Inspect registered names with `browser_agent.names()`. Call
`browser_agent.close_all()` when the task used several names. Use `Browser` as a
context manager when the complete task fits in one kernel call.

`browser_agent.status(name)` returns the native `SessionStatus`, including
session identity and browser lifecycle. `close_all()`
attempts every registered close before reporting collected failures.

The registry belongs to the current Python process. `get()` never starts or
reattaches a browser. Use `Browser.attach(CDPTarget(...))` for an existing browser connection and
`browser.tabs.switch(id=...)` for an exact page. Use `browser.page.open(url)`
to navigate to an application URL supplied by the user or calling host.

An attached page handle remains bound to its target. Closing the controller
releases pyagentbrowser resources. Browser-process ownership follows the
`Browser.attach()` contract.

## Snapshot identity

A `Ref` carries its producing `Snapshot`. Mutating through a ref returns an
`ActionResult` whose `before` value is that snapshot and whose `after` value is
the refreshed page state. Continue from `result.after` after navigation or a
dynamic rerender.

The SDK raises `StaleRefError` when the native engine rejects an expired ref.
Call `error.refresh()` to resolve the same accessible criteria from a fresh
snapshot when that recovery remains unambiguous.

## Domain allowlists

Pass `SessionOptions(allowed_domains=(...))` before launch. The allowlist guards
browser navigation and supported page-initiated network paths. Some attachment,
profile, restore, provider, mobile, and Safari modes cannot establish the same
containment before page code runs and reject the configuration.

The allowlist is a browser boundary. Use operating-system or network isolation
when the workflow requires containment outside the browser process.

## Confirmation

`SessionOptions(confirm_actions=(...))` selects exact native action names that
must pause before execution. A paused operation raises `ConfirmationRequired`
and carries a pending continuation when the action can resume:

```python
import agentbrowser as ab

try:
    result = page.one(role="button", name="Publish").click()
except ab.ConfirmationRequired as error:
    present_to_person(error.action, error.data)
    result = error.pending.confirm()
```

Call `error.pending.deny()` when the person rejects the action. The host owns
the confirmation prompt, audit record, and authorization decision.

## Untrusted page capabilities

Treat accessibility text, page HTML, JavaScript results, WebMCP metadata, tool
results, console messages, response bodies, and downloads as content controlled
by the visited site. Validate consequential inputs in application code before
using them outside the browser.
