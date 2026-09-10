# Python SDK design

Each capability owns its public operations, payload validation, result models,
and decoding under `src/agentbrowser/features/<capability>/`. It executes
`Command[T]` through an `Executor` or `AsyncExecutor` supplied by a browser or
document handle.

```python
from agentbrowser import Command, Executor

class HeadingCount:
    def __init__(self, executor: Executor) -> None:
        self.executor = executor

    def read(self) -> int:
        return self.executor.execute(Command(
            "evaluate",
            {"script": "document.querySelectorAll('h1').length"},
            decode=lambda data: int(data["result"]),
        ))
```

The complete [extension example](../docs/guides/extensions.md) includes strict
decoding, sync and async use, and resource cleanup.

## Add a vertical capability

1. Define the smallest public call and its result. Decide whether it targets a
   browser session, page, or frame.
2. Place the API, local models, parameter builders, and decoders in the feature
   package. Add separate files when each owns a distinct responsibility.
3. Share command construction and decoding between sync and async APIs. Keep
   the execution and continuation code explicit at each async boundary.
4. Execute through the supplied executor. Add multi-stage confirmation
   continuations when work must continue after an approved action.
5. Export caller-facing types from `agentbrowser`. Compose a built-in feature
   from its owning browser or document when it belongs in the stable SDK.
6. Verify the public contract and update its guide and reference entry.

Use `contracts/` for values shared across features. Use `execution/` for
session-wide policy, lifecycle, confirmation, and command effects. Use
`transport/` for wire serialization and ordered native work. Host execution and
tool content belong in `integrations/`.

An extension factory receives the same executor used by built-in capabilities.
It can be an ordinary class or function. Keep application-specific workflows
in the consuming application until the package owns a stable reusable contract.

## Checked commands and result decoding

`Command[T]` contains an action, parameters, and a decoder from the native data
mapping to `T`. The executor checks the response before invoking the decoder.
If confirmation pauses execution, the pending operation retains that decoder.

Required fields decode strictly. Raise `NativeParseError` for malformed native
data and retain the mapping on models when additional engine fields matter to
callers. Command parameters remain native protocol names at this boundary.

`browser.native.execute()` preserves the complete `BrowserResponse`, including
unsuccessful and confirmation-required envelopes. `browser.native.data()` and
typed methods check success. The raw methods cover the pinned engine's complete
action set.

## Sync and async parity

Stable operations have the same names, parameters, validation, and result
shapes across synchronous and asynchronous APIs. Engine calls become awaitable.
Handle factories and immutable snapshot lookup stay synchronous.
`AsyncBrowser.close()` additionally accepts a shutdown timeout in seconds.

`tests/test_api_parity.py` checks public signatures. Capability tests establish
returned values, error behavior, confirmation, and lifecycle. Use
`tests/test_extensions.py` for the consumer extension boundary and
`make test-integration` when the contract requires real document state.

## Public imports

Import public configuration, errors, protocols, and result types from
`agentbrowser`. Internal module paths follow ownership and can change as a
feature grows. Code-mode controller registration and packaged guidance use
`agentbrowser.agent`.

Run `make test-sdk`, then `make check`. Add native or browser tests when a
capability introduces a contract at those boundaries.
