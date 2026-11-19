from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from fakes import ConfirmationNative, ScriptedNative
from support.sdk import _browser

from agentbrowser import (
    AsyncBrowser,
    ConfirmationRequired,
    Screenshot,
)
from agentbrowser.transport.async_ import AsyncNativeSession

pytestmark = pytest.mark.sdk_dx


def test_typed_confirmation_resumes_the_original_decoder(tmp_path: Path) -> None:
    path = tmp_path / "shot.png"
    browser = _browser(ConfirmationNative(action="screenshot", result={"path": str(path)}))

    with pytest.raises(ConfirmationRequired) as required:
        browser.page.capture.screenshot(path, wait_ms=0)

    result = required.value.pending.confirm()
    assert isinstance(result, Screenshot)
    assert result.path == path


def test_confirmed_page_value_keeps_its_public_type() -> None:
    browser = _browser(ConfirmationNative(action="title", result={"title": "Confirmed"}))

    with pytest.raises(ConfirmationRequired) as required:
        browser.page.title()

    assert required.value.pending.confirm() == "Confirmed"


@pytest.mark.parametrize("asynchronous", [False, True])
def test_confirmation_names_the_policy_action_that_needs_approval(asynchronous: bool) -> None:
    # The engine asks about `navigate` when an accessibility audit names a URL.
    native = ScriptedNative(
        {
            "a11y": {
                "confirmation_required": True,
                "confirmation_id": "c1",
                "action": "navigate",
            }
        }
    )
    if asynchronous:

        async def run() -> ConfirmationRequired[Any]:
            browser = AsyncBrowser(_native_session=AsyncNativeSession(native=native))
            with pytest.raises(ConfirmationRequired) as required:
                await browser.native.data("a11y", url="https://example.com")
            return required.value

        error = asyncio.run(run())
    else:
        with pytest.raises(ConfirmationRequired) as required:
            _browser(native).native.data("a11y", url="https://example.com")
        error = required.value

    assert (error.action, error.policy_action) == ("a11y", "navigate")
    assert (error.pending.action, error.pending.policy_action) == ("a11y", "navigate")


def test_pending_action_maps_compose_in_call_order() -> None:
    browser = _browser(ConfirmationNative(action="probe", result={"value": 20}))

    with pytest.raises(ConfirmationRequired) as required:
        browser.native.data("probe")

    pending = required.value.pending
    result = pending.map(lambda data: data["value"]).map(lambda value: value * 2).confirm()
    assert result == 40


def test_pending_denial_forwards_the_confirmation_token_and_returns_none() -> None:
    native = ConfirmationNative(action="probe")
    browser = _browser(native)

    with pytest.raises(ConfirmationRequired) as required:
        browser.native.data("probe")

    assert required.value.pending.deny() is None
    assert native.commands[-1]["confirmation_id"] == required.value.confirmation_id
