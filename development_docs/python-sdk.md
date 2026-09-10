# Python SDK design

The Python layer promotes native actions into stable workflows when it can own validation, a typed result, lifecycle behavior, agent evidence, or a durable composition pattern.

## Public surface rule

Add a high-level method or namespace member when at least one of these contracts belongs to Python:

- The input has a stable Python shape that should be validated before dispatch.
- The result has fields callers should consume through a typed model.
- The operation composes several native actions.
- The operation updates controller lifecycle or direct CDP state.
- A ref action needs waits, a resulting snapshot, and a diff.
- A page or frame operation must preserve document scope across dispatch,
  waiting, and evidence capture.
- A code-mode host supplies an application target, image delivery, or execution
  limit through the host contract.
- Confirmation must resume higher-level work after the native action.

Keep `browser.native.execute(action, **params)` and `browser.native.data(action, **params)` complete for the pinned engine. A typed API should reduce repeated caller work. It should not hide the raw extension path.

## Sync and async parity

Every stable browser, snapshot, ref, query, and namespace operation has a synchronous and asynchronous form with the same names, parameters, validation, and result shape.

Intentional differences are narrow:

- Engine calls become awaitable.
- Handle factories and immutable snapshot lookup stay synchronous.
- `AsyncBrowser.close()` adds a shutdown timeout in seconds.
- Async native work is serialized through one owner thread.

`tests/test_browser_api.py` introspects public methods and parameters across the two surfaces. Update both implementations before changing that parity witness.

## Result decoding

Typed methods decode required fields strictly. Missing or malformed fields raise `NativeParseError`. Preserve the native mapping on the returned model when callers may need additional engine fields.

The raw and checked paths have different contracts:

```text
NativeSession.execute()
  -> native.execute(): preserve BrowserResponse
  -> native.data(): check success and return data
  -> typed method: check success and decode a Python result
```

`native.execute()` preserves unsuccessful and confirmation-required envelopes. `native.data()` and typed methods raise `BrowserError` or `ConfirmationRequired`.

## Public exports

Export new public models from `agentbrowser.__init__` when users need them to construct configuration, catch an error, annotate a supported value, or consume a result. Types that appear in public signatures should have one deliberate import path.

Update the closest public guide, exact reference page, runnable example, and SDK contract test with every public change.

[Evidence and refs](evidence-and-refs.md) owns the composed action pipeline.
[Direct CDP](direct-cdp.md) owns the optional persistent protocol connection and
generation-bound handles.
