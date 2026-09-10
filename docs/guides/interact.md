---
title: Interact with pages
description: Choose snapshot-scoped refs or live queries, wait for page state, and use input, scripts, frames, and emulation.
---

# Interact with pages

pyagentbrowser exposes two element models. Snapshot-scoped refs produce transition evidence. Live queries resolve against the current document for direct control.

Focused snippets that start from `browser` are partial. Place them inside an active `Browser` context such as the complete examples in the first two sections.

## Act through an observed ref

```python
from agentbrowser import Browser, Wait

with Browser.launch() as browser:
    browser.page.set_content("""
        <label>Email <input id="email"></label>
        <button onclick="document.body.dataset.saved = 'yes'">Save</button>
    """)

    snapshot = browser.observe()
    snapshot.one(role="textbox", name="Email").fill("ada@example.com")
    result = snapshot.refresh().one(role="button", name="Save").click(
        wait=Wait.all(
            Wait.loaded("none"),
            Wait.text("Save"),
        )
    )

    print(result.diff.changed)
```

Ref mutations include `click`, `fill`, `type`, `select`, `check`, `uncheck`, `hover`, `tap`, `focus`, `clear`, and `scroll_into_view`. Ref reads include text, inner text, input value, attributes, and visible, enabled, or checked state.

Use `Wait.text`, `Wait.url`, or `Wait.loaded` for one condition. `Wait.all` applies several conditions in order after the mutation.

::: tip Snapshot lifetime
Refresh the snapshot before selecting a second ref when the first action can replace the document or its accessibility nodes.
:::

## Act through a live query

```python
with Browser.launch() as browser:
    browser.page.set_content("""
        <label>Email <input id="email"></label>
        <button type="button">Continue</button>
    """)

    browser.find.label("Email").fill("ada@example.com")
    browser.find.role("button", name="Continue").hover().click()
    print(browser.find.role("button", name="Continue").text())
```

Query factories cover CSS selectors, XPath expressions, accessible roles, visible text, labels, placeholders, alternative text, title attributes, and test IDs. Query mutations return the query for chaining.

## Wait on observable state

The `browser.page` namespace waits for text, a URL pattern, selector state, a JavaScript predicate, a load state, or a minimum amount of body text.

```python
browser.page.set_content('<div data-ready="true">Ready</div>')
browser.page.wait_for_selector("[data-ready]", state="visible")
browser.page.wait_for_function("document.querySelector('[data-ready]') !== null")
browser.page.wait_for_load_state("domcontentloaded")
```

Selector states are `attached`, `detached`, `hidden`, and `visible`. Load states are `load`, `domcontentloaded`, `networkidle`, and `none`. Operation timeouts use milliseconds.

## Use keyboard, mouse, and clipboard input

```python
browser.keyboard.press("Control+A")
browser.keyboard.type("replacement text")
browser.mouse.move(200, 160)
browser.mouse.wheel(600)
browser.clipboard.write("copied by pyagentbrowser")
browser.clipboard.paste()
```

The keyboard and mouse namespaces also expose low-level down, up, and dispatch operations.

## Inject scripts and styles

`scripts.add_init()` registers JavaScript before scripts on future documents run. It returns an identifier accepted by `remove_init()`.

```python
identifier = browser.scripts.add_init("window.__agentReady = true")
browser.open("https://example.com")
print(browser.evaluate("window.__agentReady"))
browser.scripts.remove_init(identifier)
```

`scripts.add()` injects JavaScript into the current document. `scripts.add_style()` injects CSS. Each accepts inline content or a URL according to its signature.

## Work in a child frame

```python
browser.page.set_content("""
    <iframe name="checkout" srcdoc="<button>Pay</button>"></iframe>
""")
checkout = browser.page.frames.get(selector="iframe[name='checkout']")
checkout.find.role("button", name="Pay").click()
print(checkout.evaluate("document.title"))
```

The `Frame` carries its browser frame identity through queries, evaluation,
waits, snapshots, and ref actions. `frame.frames` resolves nested child frames.

## Emulate the browser environment

```python
browser.emulation.viewport(390, 844, device_scale_factor=3, mobile=True)
browser.emulation.media(color_scheme="dark", reduced_motion="reduce")
browser.emulation.timezone("Europe/Zurich")
browser.emulation.locale("de-CH")
```

The emulation namespace also controls named devices, HTTP headers, offline mode, user agent, geolocation, and permissions. Dialogs are available through `browser.dialogs.status()`, `accept()`, and `dismiss()`.

Read [Snapshots and action evidence](/concepts/evidence) for transition semantics, [Models and errors](/reference/models#snapshot) for exact ref and wait signatures, and [Capability namespaces](/reference/namespaces) for browser namespace methods.
