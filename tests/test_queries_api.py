from __future__ import annotations

import pytest
from fakes import ConfirmationNative, ScriptedNative
from support.sdk import _browser, _command_without_id

from agentbrowser import (
    ConfirmationRequired,
    Query,
)

pytestmark = pytest.mark.sdk_dx


def test_live_queries_share_one_type_and_capability_set() -> None:
    native = ScriptedNative(
        {
            "click": {},
            "getbyrole": {"text": "Save"},
        }
    )
    browser = _browser(native)

    css = browser.page.find.css("#save")
    role = browser.page.find.role("button", name="Save", exact=True)

    assert isinstance(css, Query)
    assert isinstance(role, Query)
    assert css.click() is css
    assert role.text() == "Save"
    assert native.commands[0]["selector"] == "#save"
    assert _command_without_id(native.commands[1]) == {
        "action": "getbyrole",
        "role": "button",
        "name": "Save",
        "exact": True,
        "subaction": "text",
    }


def test_query_factories_validate_empty_and_negative_inputs() -> None:
    browser = _browser(ScriptedNative(default={}))

    with pytest.raises(ValueError, match="selector"):
        browser.page.find.css("")
    with pytest.raises(ValueError, match="expression"):
        browser.page.find.xpath("xpath=")
    with pytest.raises(ValueError, match="exactly one"):
        Query(browser.extension(lambda executor: executor))
    with pytest.raises(ValueError, match="exactly one"):
        Query(browser.extension(lambda executor: executor), selector="#save", action="click")


def test_confirmed_query_action_returns_the_same_query() -> None:
    browser = _browser(ConfirmationNative(action="click", result={}))
    query = browser.page.find.css("#save")

    with pytest.raises(ConfirmationRequired) as required:
        query.click()

    assert required.value.pending.confirm() is query
