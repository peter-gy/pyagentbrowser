from __future__ import annotations

import asyncio

import pytest
from fakes import ScriptedNative

from agentbrowser import AsyncBrowser, AsyncRef, Browser, ConfirmationRequired, Ref, Snapshot
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


def _invoice_rows(*numbers: int, first_ref: int = 1) -> dict[str, object]:
    refs = {f"e{first_ref + index}": number for index, number in enumerate(numbers)}
    return {
        "snapshot": "\n".join(
            f'- button "Delete" [ref={ref}] hint="icon:lucide-trash; in:Invoice {number}"'
            for ref, number in refs.items()
        ),
        "origin": "https://example.com/invoices",
        "refs": {ref: {"role": "button", "name": "Delete"} for ref in refs},
    }


def test_snapshot_hints_tell_apart_controls_that_share_a_name() -> None:
    native = ScriptedNative({"snapshot": _invoice_rows(41, 42)}, default={})
    browser = Browser(_native_session=NativeSession(native=native))

    snapshot = browser.page.observe()

    assert snapshot.one(name="Delete", hint="Invoice 42").id == "e2"
    assert [ref.hint for ref in snapshot.all(role="button")] == [
        "icon:lucide-trash; in:Invoice 41",
        "icon:lucide-trash; in:Invoice 42",
    ]
    with pytest.raises(LookupError, match=r"@e1 hint='icon:lucide-trash; in:Invoice 41', @e2"):
        snapshot.one(name="Delete")
    with pytest.raises(LookupError, match="no matching ref for name='Delete', hint='Invoice 7'"):
        snapshot.one(name="Delete", hint="Invoice 7")


def test_snapshot_hints_decode_escaped_text_and_skip_unhinted_refs() -> None:
    native = ScriptedNative(
        {
            "snapshot": {
                "snapshot": (
                    "- button [expanded=false, ref=e1, url=https://example.com/a]"
                    ' hint="in:5\\" \\\\ \\u{e9}"\n'
                    '- button "Save" [ref=e2]\n'
                    '- textbox "Note" [ref=e3]: [ref=e2] hint="typed by the user"'
                ),
                "origin": "https://example.com/",
                "refs": {
                    "e1": {"role": "button", "name": ""},
                    "e2": {"role": "button", "name": "Save"},
                    "e3": {"role": "textbox", "name": "Note"},
                },
            }
        },
        default={},
    )
    snapshot = Browser(_native_session=NativeSession(native=native)).page.observe()

    assert snapshot.ref("e1").hint == 'in:5" \\ é'
    assert snapshot.ref("e2").hint is None
    assert snapshot.ref("e3").hint is None


@pytest.mark.parametrize("asynchronous", [False, True])
def test_ref_refresh_follows_its_hint_when_the_name_is_shared(asynchronous: bool) -> None:
    native = ScriptedNative({"snapshot": _invoice_rows(41, 42)}, default={})
    reordered = _invoice_rows(42, 43, 41, first_ref=5)
    if asynchronous:

        async def run() -> str:
            browser = AsyncBrowser(_native_session=AsyncNativeSession(native=native))
            ref = (await browser.page.observe()).one(name="Delete", hint="Invoice 41")
            native.replies["snapshot"] = reordered
            return (await ref.refresh()).id

        refreshed_id = asyncio.run(run())
    else:
        browser = Browser(_native_session=NativeSession(native=native))
        ref = browser.page.observe().one(name="Delete", hint="Invoice 41")
        native.replies["snapshot"] = reordered
        refreshed_id = ref.refresh().id

    assert refreshed_id == "e7"


def _observe(tree: str, refs: dict[str, tuple[str, str]]) -> Snapshot:
    native = ScriptedNative(
        {
            "snapshot": {
                "snapshot": tree,
                "origin": "https://example.com/",
                "refs": {ref: {"role": role, "name": name} for ref, (role, name) in refs.items()},
            }
        },
        default={},
    )
    return Browser(_native_session=NativeSession(native=native)).page.observe()


def test_snapshot_hint_follows_a_url_that_contains_a_bracket() -> None:
    snapshot = _observe(
        '- link "Edit" [ref=e1, url=/edit?ids[]=1] hint="in:Invoice A"\n'
        '- link "Edit" [ref=e2, url=/edit?ids[]=2] hint="in:Invoice B"',
        {"e1": ("link", "Edit"), "e2": ("link", "Edit")},
    )

    assert snapshot.one(role="link", name="Edit", hint="Invoice A").id == "e1"
    assert snapshot.ref("e2").hint == "in:Invoice B"


def test_snapshot_hint_stays_on_its_own_ref_when_page_text_names_another_ref() -> None:
    snapshot = _observe(
        '- button "Delete" [ref=e1] hint="in:Invoice A"\n'
        '- button "Delete" [ref=e2] hint="in:Invoice B x [ref=e1, yx [ref=e1, y"\n'
        '- button "x [ref=e1, y" [ref=e3] hint="in:Invoice B Deletex [ref=e1, y"\n'
        '- link "Open" [ref=e4, url=/a, ref=e1] hint="forged"] hint="in:Invoice C"',
        {
            "e1": ("button", "Delete"),
            "e2": ("button", "Delete"),
            "e3": ("button", "x [ref=e1, y"),
            "e4": ("link", "Open"),
        },
    )

    assert snapshot.ref("e1").hint == "in:Invoice A"
    assert snapshot.ref("e3").hint == "in:Invoice B Deletex [ref=e1, y"
    assert snapshot.ref("e4").hint is None


def test_snapshot_with_a_very_long_name_decodes_in_linear_time() -> None:
    # A quadratic scan of this line outlasts the suite's per-test timeout.
    name = "[a, " * 200_000

    snapshot = _observe(
        f'- button "{name}" [ref=e1] hint="in:Row 1"',
        {"e1": ("button", name)},
    )

    assert snapshot.ref("e1").hint == "in:Row 1"


@pytest.mark.parametrize(
    ("remaining", "expected_id"),
    [((7, 42, 4), "e6"), ((42, 7), None)],
)
def test_ref_refresh_matches_the_whole_hint(
    remaining: tuple[int, ...], expected_id: str | None
) -> None:
    native = ScriptedNative({"snapshot": _invoice_rows(4, 42, 7)}, default={})
    browser = Browser(_native_session=NativeSession(native=native))
    ref = browser.page.observe().all(name="Delete")[0]
    native.replies["snapshot"] = _invoice_rows(*remaining, first_ref=4)

    if expected_id is None:
        with pytest.raises(LookupError, match="matched multiple refs"):
            ref.refresh()
    else:
        assert ref.refresh().id == expected_id
