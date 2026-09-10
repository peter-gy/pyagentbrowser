from __future__ import annotations

import asyncio

import pytest
from fakes import ScriptedNative

from agentbrowser import AsyncBrowser, AsyncRef, Browser, ConfirmationRequired, Ref
from agentbrowser.transport.async_ import AsyncNativeSession
from agentbrowser.transport.sync import NativeSession

pytestmark = pytest.mark.sdk_dx


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize(("contains", "expected_id"), [(None, "e3"), ("Send", "e4")])
def test_ref_refresh_resumes_selection_after_snapshot_confirmation(
    asynchronous: bool, contains: str | None, expected_id: str
) -> None:
    native = ScriptedNative(
        {
            "snapshot": {
                "snapshot": "button Submit [ref=e1]",
                "origin": "https://example.com/form",
                "refs": {"e1": {"role": "button", "name": "Submit"}},
            },
            "confirm": {
                "confirmed": True,
                "action": "snapshot",
                "result": {
                    "success": True,
                    "data": {
                        "snapshot": "button Submit [ref=e3]\nbutton Send report [ref=e4]",
                        "origin": "https://example.com/form",
                        "refs": {
                            "e3": {"role": "button", "name": "Submit"},
                            "e4": {"role": "button", "name": "Send report"},
                        },
                    },
                },
            },
        },
        default={},
    )
    confirmation = {"confirmation_required": True, "confirmation_id": "refresh"}
    if asynchronous:

        async def run() -> None:
            async with AsyncBrowser(_native_session=AsyncNativeSession(native=native)) as browser:
                snapshot = await browser.page.observe()
                ref = snapshot.one(role="button", name="Submit")
                native.replies["snapshot"] = confirmation
                with pytest.raises(ConfirmationRequired) as raised:
                    await ref.refresh(contains=contains, exact=contains is None)
                refreshed = await raised.value.pending.confirm()
                assert isinstance(refreshed, AsyncRef)
                assert refreshed.id == expected_id

        asyncio.run(run())
    else:
        with Browser(_native_session=NativeSession(native=native)) as browser:
            ref = browser.page.observe().one(role="button", name="Submit")
            native.replies["snapshot"] = confirmation
            with pytest.raises(ConfirmationRequired) as raised:
                ref.refresh(contains=contains, exact=contains is None)
            refreshed = raised.value.pending.confirm()
            assert isinstance(refreshed, Ref)
            assert refreshed.id == expected_id
