from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fakes import ConfirmationNative, ScriptedNative

from agentbrowser import Browser, BrowserError, ConfirmationRequired
from agentbrowser.session import NativeSession

pytestmark = pytest.mark.sdk_dx


def _browser(native: Any, domains: str = "example.com") -> Browser:
    return Browser(
        _native_session=NativeSession(native=native, allowed_domains=domains),
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/path",
        "https://sub.example.com/path",
    ],
)
def test_allowlist_forwards_allowed_navigation(url: str) -> None:
    native = ScriptedNative({"navigate": {}})
    browser = _browser(native, "*.example.com,example.com")

    browser.native.data("navigate", url=url)

    assert native.commands[0]["url"] == url


@pytest.mark.parametrize(
    ("action", "field", "target"),
    [
        ("addscript", "url", "https://evil.example/script.js"),
        ("addstyle", "url", "https://evil.example/style.css"),
        ("auth_save", "url", "https://evil.example/login"),
        ("credentials_set", "url", "https://evil.example/login"),
        ("diff_url", "url1", "https://evil.example/first"),
        ("diff_url", "url2", "https://evil.example/second"),
        ("navigate", "url", "https://evil.example/path"),
        ("pushstate", "url", "https://evil.example/path"),
        ("read", "url", "https://evil.example/article"),
        ("recording_start", "url", "https://evil.example/path"),
        ("tab_new", "url", "https://evil.example/path"),
        ("vitals", "url", "https://evil.example/path"),
        ("frame", "url", "*://*.evil.example/*"),
        ("responsebody", "url", "*://*.evil.example/*"),
        ("route", "url", "*://*.evil.example/*"),
        ("unroute", "url", "*://*.evil.example/*"),
        ("wait", "url", "*://*.evil.example/*"),
        ("waitforurl", "url", "*://*.evil.example/*"),
    ],
)
def test_allowlist_rejects_every_mapped_url_target_before_native_dispatch(
    action: str,
    field: str,
    target: str,
) -> None:
    native = ScriptedNative(default={})
    browser = _browser(native)

    with pytest.raises(BrowserError) as denied:
        browser.native.data(action, **{field: target})

    assert denied.value.code == "allowed_domains"
    assert native.commands == []


def test_allowlist_rejects_cookie_query_urls_before_native_dispatch() -> None:
    native = ScriptedNative(default={})
    browser = _browser(native)

    with pytest.raises(BrowserError) as denied:
        browser.native.data("cookies_get", urls=["https://evil.example/path"])

    assert denied.value.code == "allowed_domains"
    assert native.commands == []


@pytest.mark.parametrize(
    ("action", "pattern", "domains"),
    [
        ("wait", "*://*.example.com/*", "*.example.com"),
        ("route", "**/localhost:3000/api/*", "localhost"),
        ("frame", "*://[::1]:9222/*", "::1"),
    ],
)
def test_allowlist_forwards_representative_host_qualified_patterns(
    action: str,
    pattern: str,
    domains: str,
) -> None:
    native = ScriptedNative({action: {}})
    browser = _browser(native, domains)

    browser.native.data(action, url=pattern)

    assert native.commands[0]["url"] == pattern


def test_exact_domain_does_not_authorize_a_wildcard_url_pattern() -> None:
    native = ScriptedNative({"wait": {}})
    browser = _browser(native)

    with pytest.raises(BrowserError) as denied:
        browser.native.data("wait", url="*://*.example.com/*")

    assert denied.value.code == "allowed_domains"
    assert native.commands == []


@pytest.mark.parametrize("allowed_domains", ["evil.example", ["evil.example"], [], None])
def test_raw_launch_cannot_weaken_the_session_allowlist(allowed_domains: object) -> None:
    native = ScriptedNative({"launch": {}})
    browser = _browser(native)

    with pytest.raises(BrowserError, match="allowed domains"):
        browser.native.data(
            "launch",
            allowedDomains=allowed_domains,
        )

    assert native.commands == []


def test_raw_launch_accepts_the_matching_array_allowlist() -> None:
    native = ScriptedNative({"launch": {}, "navigate": {}})
    browser = _browser(native)

    browser.native.data("launch", allowedDomains=["example.com"])

    with pytest.raises(BrowserError, match="not in the allowed domains"):
        browser.native.data("navigate", url="https://evil.example")
    assert [command["action"] for command in native.commands] == ["launch"]


def test_raw_launch_adopts_an_array_allowlist() -> None:
    native = ScriptedNative(
        {
            "launch": {},
            "cookies_get": {
                "cookies": [
                    {"name": "allowed", "value": "1", "domain": ".example.com"},
                    {"name": "blocked", "value": "2", "domain": ".evil.example"},
                ]
            },
        }
    )
    browser = _browser(native, domains="")

    browser.native.data("launch", allowedDomains=["example.com"])
    cookies = browser.native.data("cookies_get")["cookies"]

    assert cookies == [{"name": "allowed", "value": "1", "domain": ".example.com"}]


def test_denied_raw_launch_does_not_adopt_its_array_allowlist() -> None:
    native = ScriptedNative(
        {
            "launch": {
                "success": True,
                "data": {
                    "confirmation_required": True,
                    "confirmation_id": "launch-confirmation",
                    "action": "launch",
                },
            },
            "deny": {},
            "navigate": {},
        }
    )
    browser = _browser(native, domains="")

    with pytest.raises(ConfirmationRequired) as required:
        browser.native.data("launch", allowedDomains=["example.com"])

    required.value.pending.deny()
    browser.native.data("navigate", url="https://evil.example")
    assert [command["action"] for command in native.commands] == ["launch", "deny", "navigate"]


def test_confirmed_raw_launch_adopts_its_array_allowlist() -> None:
    native = ScriptedNative(
        {
            "launch": {
                "success": True,
                "data": {
                    "confirmation_required": True,
                    "confirmation_id": "launch-confirmation",
                    "action": "launch",
                },
            },
            "confirm": {
                "success": True,
                "data": {
                    "confirmed": True,
                    "action": "launch",
                    "result": {"id": "confirmed-launch", "success": True, "data": {}},
                },
            },
            "navigate": {},
        }
    )
    browser = _browser(native, domains="")

    with pytest.raises(ConfirmationRequired) as required:
        browser.native.data("launch", allowedDomains=["example.com"])

    required.value.pending.confirm()
    with pytest.raises(BrowserError, match="not in the allowed domains"):
        browser.native.data("navigate", url="https://evil.example")
    assert [command["action"] for command in native.commands] == ["launch", "confirm"]


def test_failed_confirm_can_retry_and_adopt_the_launch_allowlist() -> None:
    attempts = 0

    def confirm(_command: dict[str, Any]) -> dict[str, Any]:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return {"success": False, "error": "policy reload failed"}
        return {
            "success": True,
            "data": {
                "confirmed": True,
                "action": "launch",
                "result": {"id": "confirmed-launch", "success": True, "data": {}},
            },
        }

    native = ScriptedNative(
        {
            "launch": {
                "success": True,
                "data": {
                    "confirmation_required": True,
                    "confirmation_id": "launch-confirmation",
                    "action": "launch",
                },
            },
            "confirm": confirm,
            "navigate": {},
        }
    )
    browser = _browser(native, domains="")

    with pytest.raises(ConfirmationRequired) as required:
        browser.native.data("launch", allowedDomains=["example.com"])

    with pytest.raises(BrowserError, match="policy reload failed"):
        required.value.pending.confirm()
    required.value.pending.confirm()
    with pytest.raises(BrowserError, match="not in the allowed domains"):
        browser.native.data("navigate", url="https://evil.example")
    assert [command["action"] for command in native.commands] == [
        "launch",
        "confirm",
        "confirm",
    ]


def test_failed_confirmed_launch_does_not_adopt_its_array_allowlist() -> None:
    native = ScriptedNative(
        {
            "launch": {
                "success": True,
                "data": {
                    "confirmation_required": True,
                    "confirmation_id": "launch-confirmation",
                    "action": "launch",
                },
            },
            "confirm": {
                "success": True,
                "data": {
                    "confirmed": True,
                    "action": "launch",
                    "result": {
                        "id": "failed-launch",
                        "success": False,
                        "error": "launch failed",
                    },
                },
            },
            "navigate": {},
        }
    )
    browser = _browser(native, domains="")

    with pytest.raises(ConfirmationRequired) as required:
        browser.native.data("launch", allowedDomains=["example.com"])

    with pytest.raises(BrowserError, match="launch failed"):
        required.value.pending.confirm()
    browser.native.data("navigate", url="https://evil.example")
    assert [command["action"] for command in native.commands] == [
        "launch",
        "confirm",
        "navigate",
    ]


def test_chained_confirm_transfers_and_applies_the_launch_allowlist() -> None:
    attempts = 0

    def confirm(_command: dict[str, Any]) -> dict[str, Any]:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return {
                "success": True,
                "data": {
                    "confirmed": True,
                    "action": "launch",
                    "result": {
                        "id": "replayed-launch",
                        "success": True,
                        "data": {
                            "confirmation_required": True,
                            "confirmation_id": "launch-confirmation",
                            "action": "plugin:provider:launch.mutate",
                        },
                    },
                },
            }
        return {
            "success": True,
            "data": {
                "confirmed": True,
                "action": "plugin:provider:launch.mutate",
                "result": {"id": "confirmed-launch", "success": True, "data": {}},
            },
        }

    native = ScriptedNative(
        {
            "launch": {
                "success": True,
                "data": {
                    "confirmation_required": True,
                    "confirmation_id": "launch-confirmation",
                    "action": "launch",
                },
            },
            "confirm": confirm,
            "navigate": {},
        }
    )
    browser = _browser(native, domains="")

    with pytest.raises(ConfirmationRequired) as first:
        browser.native.data("launch", allowedDomains=["example.com"])
    with pytest.raises(ConfirmationRequired) as second:
        first.value.pending.confirm()

    second.value.pending.confirm()
    with pytest.raises(BrowserError, match="not in the allowed domains"):
        browser.native.data("navigate", url="https://evil.example")
    assert [command["action"] for command in native.commands] == [
        "launch",
        "confirm",
        "confirm",
    ]


def test_cookie_responses_are_filtered_at_the_python_boundary() -> None:
    native = ScriptedNative(
        {
            "cookies_get": {
                "cookies": [
                    {"name": "allowed", "value": "1", "domain": ".example.com"},
                    {"name": "blocked", "value": "2", "domain": ".evil.example"},
                ]
            }
        }
    )
    browser = _browser(native)

    data = browser.native.data("cookies_get")

    assert data["cookies"] == [{"name": "allowed", "value": "1", "domain": ".example.com"}]


def test_cookie_set_rejects_a_batch_that_crosses_the_allowlist() -> None:
    native = ScriptedNative({"cookies_set": {}})
    browser = _browser(native)

    with pytest.raises(BrowserError) as denied:
        browser.native.data(
            "cookies_set",
            cookies=[
                {"name": "allowed", "value": "1", "domain": ".example.com"},
                {"name": "blocked", "value": "2", "domain": ".evil.example"},
            ],
        )

    assert denied.value.code == "allowed_domains"
    assert native.commands == []


def test_cookie_clear_requires_an_explicit_unscoped_override() -> None:
    native = ScriptedNative({"cookies_clear": {}})
    browser = _browser(native)

    with pytest.raises(BrowserError) as denied:
        browser.native.data("cookies_clear")

    assert denied.value.code == "allowed_domains"
    browser.native.data("cookies_clear", unsafeClearAll=True)
    assert [command["action"] for command in native.commands] == ["cookies_clear"]


def test_permissions_origin_is_checked_before_native_dispatch() -> None:
    native = ScriptedNative({"permissions": {}})
    browser = _browser(native)

    with pytest.raises(BrowserError) as denied:
        browser.native.data(
            "permissions",
            permissions=["geolocation"],
            origin="https://evil.example",
        )

    assert denied.value.code == "allowed_domains"
    assert native.commands == []


def test_state_load_rejects_origin_replay_before_native_dispatch(tmp_path: Path) -> None:
    native = ScriptedNative({"state_load": {}})
    browser = _browser(native)

    with pytest.raises(BrowserError, match="saved origins") as denied:
        browser.state.load(tmp_path / "state.json")

    assert denied.value.code == "allowed_domains"
    assert native.commands == []


def test_launch_rejects_storage_state_before_native_dispatch(tmp_path: Path) -> None:
    native = ScriptedNative({"launch": {}})
    browser = _browser(native)

    with pytest.raises(BrowserError, match="storage_state") as denied:
        browser.native.data("launch", storageState=tmp_path / "state.json")

    assert denied.value.code == "allowed_domains"
    assert native.commands == []


@pytest.mark.parametrize(
    ("unsafe_export_all", "expected_origins"),
    [
        (False, ["https://example.com"]),
        (True, ["https://example.com", "https://evil.example"]),
    ],
)
def test_state_save_applies_the_requested_export_scope(
    tmp_path: Path,
    unsafe_export_all: bool,
    expected_origins: list[str],
) -> None:
    target = tmp_path / "saved-state.json"
    target.write_text(
        json.dumps(
            {
                "cookies": [],
                "origins": [
                    {"origin": "https://example.com", "localStorage": []},
                    {"origin": "https://evil.example", "localStorage": []},
                ],
            }
        )
    )
    browser = _browser(ScriptedNative({"state_save": {"path": str(target)}}))

    browser.native.data("state_save", unsafeExportAll=unsafe_export_all)

    saved = json.loads(target.read_text())
    assert [origin["origin"] for origin in saved["origins"]] == expected_origins


def test_confirmed_cookie_response_keeps_the_original_allowlist() -> None:
    native = ConfirmationNative(
        action="cookies_get",
        result={
            "cookies": [
                {"name": "allowed", "value": "1", "domain": ".example.com"},
                {"name": "blocked", "value": "2", "domain": ".evil.example"},
            ]
        },
    )
    browser = _browser(native)

    with pytest.raises(ConfirmationRequired) as required:
        browser.native.data("cookies_get")

    data = required.value.pending.confirm()
    assert data["cookies"] == [{"name": "allowed", "value": "1", "domain": ".example.com"}]


def test_confirmed_state_save_filters_the_deferred_response(tmp_path: Path) -> None:
    target = tmp_path / "confirmed-state.json"
    target.write_text(
        json.dumps(
            {
                "cookies": [],
                "origins": [
                    {"origin": "https://example.com", "localStorage": []},
                    {"origin": "https://evil.example", "localStorage": []},
                ],
            }
        )
    )
    browser = _browser(ConfirmationNative(action="state_save", result={"path": str(target)}))

    with pytest.raises(ConfirmationRequired) as required:
        browser.native.data("state_save")

    required.value.pending.confirm()
    saved = json.loads(target.read_text())
    assert [origin["origin"] for origin in saved["origins"]] == ["https://example.com"]
