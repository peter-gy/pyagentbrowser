from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fakes import ScriptedNative
from support.sdk import _accessibility_audit_data, _browser, _command_without_id

from agentbrowser import (
    AccessibilityAudit,
    AsyncBrowser,
    NativeParseError,
)
from agentbrowser.transport.async_ import AsyncNativeSession

pytestmark = pytest.mark.sdk_dx


def test_console_messages_preserve_a_present_empty_collection() -> None:
    browser = _browser(ScriptedNative({"console": {"messages": []}}))

    assert browser.diagnostics.console() == ()


def test_accessibility_audit_returns_typed_results_and_serializes_scope() -> None:
    native = ScriptedNative({"a11y": _accessibility_audit_data()})
    browser = _browser(native)

    audit = browser.diagnostics.accessibility(
        "example.com",
        tags=("wcag2a", "wcag2aa"),
        selector="#main",
    )

    assert isinstance(audit, AccessibilityAudit)
    assert audit.axe_version == "4.12.1"
    assert audit.counts.violations == 1
    assert audit.violations[0].id == "image-alt"
    assert audit.violations[0].nodes[0].target == (
        "#logo",
        ("#shadow-root", "img"),
    )
    assert _command_without_id(native.commands[0]) == {
        "action": "a11y",
        "url": "https://example.com",
        "tags": "wcag2a,wcag2aa",
        "selector": "#main",
    }


@pytest.mark.parametrize("tags", ["wcag2a", ("",), ("wcag2a,wcag2aa",), (1,)])
def test_accessibility_audit_rejects_invalid_tags(tags: Any) -> None:
    native = ScriptedNative(default={})
    browser = _browser(native)

    with pytest.raises((TypeError, ValueError), match="tags"):
        browser.diagnostics.accessibility(tags=tags)

    assert native.commands == []


def test_accessibility_audit_rejects_invalid_native_targets() -> None:
    data = _accessibility_audit_data()
    data["violations"][0]["nodes"][0]["target"] = [42]
    browser = _browser(ScriptedNative({"a11y": data}))

    with pytest.raises(NativeParseError, match="target entries"):
        browser.diagnostics.accessibility()


def test_diff_namespace_returns_a_typed_snapshot_diff() -> None:
    browser = _browser(
        ScriptedNative(
            {
                "diff_snapshot": {
                    "diff": "+ ready",
                    "additions": 1,
                    "removals": 0,
                    "unchanged": 2,
                    "changed": True,
                }
            }
        )
    )

    diff = browser.diff.snapshot("baseline")

    assert diff.changed is True
    assert diff.additions == 1


def test_async_accessibility_audit_matches_the_sync_contract() -> None:
    async def run() -> None:
        native = ScriptedNative({"a11y": _accessibility_audit_data()})
        browser = AsyncBrowser(_native_session=AsyncNativeSession(native=native))

        audit = await browser.diagnostics.accessibility(tags=("wcag2aa",))

        assert audit.violations[0].nodes[0].failure_summary
        assert _command_without_id(native.commands[0]) == {
            "action": "a11y",
            "tags": "wcag2aa",
        }

    asyncio.run(run())
