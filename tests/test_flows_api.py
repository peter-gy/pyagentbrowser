from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest
from fakes import CLOSE_DATA, ScriptedNative
from support.sdk import _command_without_id

from agentbrowser import (
    AsyncBrowser,
    Browser,
    BrowserError,
    ConfirmationRequired,
    FlowDrift,
    FlowFallback,
    FlowGap,
    FlowRecording,
    FlowRequest,
    FlowRun,
    FlowRunError,
    FlowRunStep,
    FlowStep,
    FlowSummary,
    FlowWrite,
    LaunchOptions,
    NativeParseError,
    SavedFlow,
    SessionOptions,
)
from agentbrowser.transport.async_ import AsyncNativeSession
from agentbrowser.transport.sync import NativeSession

pytestmark = pytest.mark.sdk_dx


def _flow_replies() -> dict[str, dict[str, Any]]:
    return {
        "flow_steps": {
            "steps": [
                {
                    "seq": 1,
                    "command": "navigate https://shop.example/search?q=stove",
                    "url": "https://shop.example/search?q=stove",
                    "requests": 3,
                    "ok": True,
                    "saved": True,
                },
                {
                    "seq": 2,
                    "command": "click @e3",
                    "url": None,
                    "requests": 0,
                    "ok": False,
                    "saved": False,
                },
            ],
            "lastSave": 1,
            "unsaved": 1,
        },
        "flow_save": {
            "name": "order",
            "origin": "shop.example",
            "steps": 2,
            "requests": [
                {
                    "id": "s1r1",
                    "method": "GET",
                    "url": "https://shop.example/api/search?q={{q}}",
                    "bytes": 1234,
                },
            ],
            "output": "s1r1",
            "params": ["q"],
            "detectedParams": [
                {
                    "name": "id",
                    "example": "42",
                    "source": "response",
                    "from": {"request": "s1r1", "list": "items"},
                }
            ],
            "references": [{"request": "s2r1", "from": "s1r1", "path": "session.key"}],
            "writes": [
                {
                    "id": "s2r1",
                    "method": "POST",
                    "url": "https://shop.example/api/order",
                    "kind": "explicit",
                    "step": 2,
                }
            ],
            "gaps": [
                {
                    "step": 2,
                    "command": "click @e3",
                    "reason": "no network traffic while this command ran",
                }
            ],
            "droppedHeaders": ["authorization", "cookie"],
            "verified": False,
            "path": "/flows/shop.example/order.json",
            "from": 1,
            "to": 2,
            "reachNote": "shop.example could not be confirmed as a local host",
        },
        "flow_run": {
            "name": "order",
            "origin": "shop.example",
            "ok": True,
            "verified": False,
            "ms": 412,
            "steps": [
                {
                    "id": "s1r1",
                    "step": 1,
                    "tier": "page",
                    "status": 200,
                    "ms": 180,
                    "error": None,
                    "fellBack": [{"tier": "http", "error": "HTTP 403"}],
                }
            ],
            "data": {"list": "items", "total": 40, "matched": 1, "items": [{"title": "Lamp"}]},
            "empty": True,
            "drift": {"tier": "http", "step": 1, "reason": "the response lost its items list"},
            "saveError": "permission denied",
        },
        "flow_list": {
            "flows": [
                {
                    "name": "order",
                    "origin": "shop.example",
                    "valid": True,
                    "params": ["q"],
                    "examples": {"q": "stove"},
                    "description": "Order the first search result",
                    "inputSchema": {"type": "object", "properties": {"q": {"type": "string"}}},
                    "paramSources": {"id": "s1r1 items"},
                    "itemFields": ["id", "title"],
                    "recordedOn": "https://shop.example/search?q=stove",
                    "provenance": "observed",
                    "verifiedAt": None,
                }
            ]
        },
    }


_RATE_LIMITED = {
    "success": False,
    "error": (
        "rate_limited: flow 'order' step 2 (http): HTTP 429; retry after 30. Wait before rerunning"
    ),
    "code": "rate_limited",
    "data": {
        "status": "rate_limited",
        "flow": "order",
        "step": 2,
        "httpStatus": 429,
        "retryAfter": "30",
        "saveError": "flow file is read-only",
    },
}


def _run_everything(browser: Browser) -> tuple[Any, ...]:
    return (
        browser.flows.steps(),
        browser.flows.save(
            "order",
            params={"q": "stove"},
            description="Order the first search result",
            output="s1r1",
            from_step=1,
            to_step=2,
            timeout_ms=5000,
        ),
        browser.flows.run(
            "order",
            params={"q": "lamp"},
            origin="shop.example",
            allow_writes=["s2r1"],
            where={"title": "lamp"},
            fields=["title", "price.amount"],
            limit=1,
            timeout_ms=9000,
        ),
        browser.flows.run("order", allow_writes="all"),
        browser.flows.run("order"),
        browser.flows.list(origin="shop.example"),
        browser.flows.list(),
    )


async def _run_everything_async(browser: AsyncBrowser) -> tuple[Any, ...]:
    return (
        await browser.flows.steps(),
        await browser.flows.save(
            "order",
            params={"q": "stove"},
            description="Order the first search result",
            output="s1r1",
            from_step=1,
            to_step=2,
            timeout_ms=5000,
        ),
        await browser.flows.run(
            "order",
            params={"q": "lamp"},
            origin="shop.example",
            allow_writes=["s2r1"],
            where={"title": "lamp"},
            fields=["title", "price.amount"],
            limit=1,
            timeout_ms=9000,
        ),
        await browser.flows.run("order", allow_writes="all"),
        await browser.flows.run("order"),
        await browser.flows.list(origin="shop.example"),
        await browser.flows.list(),
    )


def test_flows_typed_namespace_preserves_sync_async_command_parity() -> None:
    sync_native = ScriptedNative(_flow_replies(), default={})
    browser = Browser(_native_session=NativeSession(native=sync_native))

    results = _run_everything(browser)
    recording, saved, run, _run_all, _run_plain, summaries, _all_summaries = results

    assert recording == FlowRecording(
        steps=(
            FlowStep(
                seq=1,
                command="navigate https://shop.example/search?q=stove",
                url="https://shop.example/search?q=stove",
                requests=3,
                ok=True,
                saved=True,
            ),
            FlowStep(seq=2, command="click @e3", url=None, requests=0, ok=False, saved=False),
        ),
        last_save=1,
        unsaved=1,
    )
    assert saved == SavedFlow(
        name="order",
        origin="shop.example",
        step_count=2,
        requests=(
            FlowRequest(
                id="s1r1",
                method="GET",
                url="https://shop.example/api/search?q={{q}}",
                bytes=1234,
            ),
        ),
        output="s1r1",
        params=("q",),
        detected_params=(
            {
                "name": "id",
                "example": "42",
                "source": "response",
                "from": {"request": "s1r1", "list": "items"},
            },
        ),
        references=({"request": "s2r1", "from": "s1r1", "path": "session.key"},),
        writes=(
            FlowWrite(
                id="s2r1",
                method="POST",
                url="https://shop.example/api/order",
                kind="explicit",
                step=2,
            ),
        ),
        gaps=(
            FlowGap(
                step=2,
                command="click @e3",
                reason="no network traffic while this command ran",
            ),
        ),
        dropped_headers=("authorization", "cookie"),
        verified=False,
        path=Path("/flows/shop.example/order.json"),
        from_step=1,
        to_step=2,
        reach_note="shop.example could not be confirmed as a local host",
    )
    assert run == FlowRun(
        name="order",
        origin="shop.example",
        verified=False,
        duration_ms=412,
        steps=(
            FlowRunStep(
                id="s1r1",
                step=1,
                tier="page",
                status=200,
                duration_ms=180,
                fell_back=(FlowFallback(tier="http", error="HTTP 403"),),
            ),
        ),
        data={"list": "items", "total": 40, "matched": 1, "items": [{"title": "Lamp"}]},
        empty=True,
        drift=FlowDrift(tier="http", step=1, reason="the response lost its items list"),
        save_error="permission denied",
    )
    assert summaries == (
        FlowSummary(
            name="order",
            origin="shop.example",
            valid=True,
            params=("q",),
            examples={"q": "stove"},
            description="Order the first search result",
            input_schema={"type": "object", "properties": {"q": {"type": "string"}}},
            param_sources={"id": "s1r1 items"},
            item_fields=("id", "title"),
            recorded_on="https://shop.example/search?q=stove",
            provenance="observed",
            verified_at=None,
        ),
    )
    sync_commands = [_command_without_id(command) for command in sync_native.commands]
    assert sync_commands == [
        {"action": "flow_steps"},
        {
            "action": "flow_save",
            "name": "order",
            "params": {"q": "stove"},
            "description": "Order the first search result",
            "output": "s1r1",
            "from": 1,
            "to": 2,
            "timeout": 5000,
        },
        {
            "action": "flow_run",
            "name": "order",
            "params": {"q": "lamp"},
            "origin": "shop.example",
            "allowWrite": ["s2r1"],
            "where": {"title": "lamp"},
            "fields": "title,price.amount",
            "limit": 1,
            "timeout": 9000,
        },
        {"action": "flow_run", "name": "order", "allowWrite": "all"},
        {"action": "flow_run", "name": "order"},
        {"action": "flow_list", "origin": "shop.example"},
        {"action": "flow_list"},
    ]

    async def run_async() -> list[dict[str, Any]]:
        async_native = ScriptedNative(_flow_replies(), default={})
        async_browser = AsyncBrowser(_native_session=AsyncNativeSession(native=async_native))
        assert await _run_everything_async(async_browser) == results
        await async_browser.close()
        return [
            _command_without_id(command)
            for command in async_native.commands
            if command["action"] != "__agent_browser_internal_shutdown"
        ]

    assert asyncio.run(run_async()) == sync_commands
    browser.close()


def test_flow_run_defaults_optional_result_fields() -> None:
    reply = _flow_replies()["flow_run"]
    for key in ("empty", "drift", "saveError"):
        del reply[key]
    del reply["steps"][0]["fellBack"]
    reply["data"] = None
    browser = Browser(_native_session=NativeSession(native=ScriptedNative({"flow_run": reply})))

    run = browser.flows.run("order")

    assert run.data is None
    assert run.empty is False
    assert run.drift is None
    assert run.save_error is None
    assert run.steps[0].fell_back == ()


@pytest.mark.parametrize(
    ("call", "error", "match"),
    [
        (lambda flows: flows.save("checkout flow"), ValueError, "invalid flow name"),
        (lambda flows: flows.run(""), ValueError, "invalid flow name"),
        (lambda flows: flows.run(cast(Any, 7)), TypeError, "name must be a string"),
        (lambda flows: flows.run("order", allow_writes="s1r1"), TypeError, "allow_writes"),
        (lambda flows: flows.run("order", allow_writes=[" "]), ValueError, "allow_writes"),
        (lambda flows: flows.run("order", fields="title"), TypeError, "fields must be a sequence"),
        (lambda flows: flows.run("order", fields=["id,title"]), ValueError, "comma"),
        (lambda flows: flows.run("order", params={"q": 1}), TypeError, "params entry 'q'"),
        (lambda flows: flows.run("order", where={"title": None}), TypeError, "where entry"),
        (lambda flows: flows.run("order", limit=-1), ValueError, "limit must be non-negative"),
        (lambda flows: flows.run("order", limit=True), TypeError, "limit must be an integer"),
        (lambda flows: flows.run("order", origin=" "), ValueError, "origin must not be empty"),
        (lambda flows: flows.save("order", params=["q"]), TypeError, "params must be a mapping"),
        (lambda flows: flows.save("order", from_step=True), TypeError, "from_step"),
        (lambda flows: flows.save("order", to_step=-2), ValueError, "to_step"),
        (lambda flows: flows.save("order", timeout_ms=-1), ValueError, "timeout_ms"),
        (lambda flows: flows.list(origin=""), ValueError, "origin must not be empty"),
    ],
)
def test_flows_reject_invalid_arguments_before_reaching_the_engine(
    call: Callable[[Any], object],
    error: type[Exception],
    match: str,
) -> None:
    native = ScriptedNative()
    browser = Browser(_native_session=NativeSession(native=native))

    with pytest.raises(error, match=match):
        call(browser.flows)

    assert native.commands == []


def _without(reply: dict[str, Any], *path: str | int) -> dict[str, Any]:
    target: Any = reply
    for key in path[:-1]:
        target = target[key]
    del target[path[-1]]
    return reply


def _with(reply: dict[str, Any], value: object, *path: str | int) -> dict[str, Any]:
    target: Any = reply
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return reply


@pytest.mark.parametrize(
    ("action", "mutate", "match"),
    [
        ("flow_steps", lambda r: _without(r, "lastSave"), "flow_steps field 'lastSave'"),
        ("flow_steps", lambda r: _without(r, "steps", 0, "url"), "flow_steps field 'url'"),
        ("flow_save", lambda r: _without(r, "path"), "flow_save field 'path'"),
        ("flow_save", lambda r: _with(r, None, "output"), "flow_save field 'output'"),
        (
            "flow_save",
            lambda r: _with(r, "maybe", "writes", 0, "kind"),
            "flow_save field 'kind' has unknown value 'maybe'",
        ),
        ("flow_run", lambda r: _without(r, "data"), "flow_run field 'data' is required"),
        ("flow_run", lambda r: _without(r, "steps", 0, "status"), "flow_run field 'status'"),
        (
            "flow_run",
            lambda r: _with(r, "socket", "steps", 0, "tier"),
            "flow_run field 'tier' has unknown value 'socket'",
        ),
        (
            "flow_run",
            lambda r: _with(r, "socket", "drift", "tier"),
            "flow_run field 'tier' has unknown value 'socket'",
        ),
        ("flow_list", lambda r: _with(r, {}, "flows"), "flow_list field 'flows'"),
        (
            "flow_list",
            lambda r: _without(r, "flows", 0, "recordedOn"),
            "flow_list field 'recordedOn'",
        ),
    ],
)
def test_flows_decode_native_results_strictly(
    action: str,
    mutate: Callable[[dict[str, Any]], dict[str, Any]],
    match: str,
) -> None:
    reply = mutate(deepcopy(_flow_replies()[action]))
    browser = Browser(_native_session=NativeSession(native=ScriptedNative({action: reply})))
    calls: dict[str, Callable[[], object]] = {
        "flow_steps": browser.flows.steps,
        "flow_save": lambda: browser.flows.save("order"),
        "flow_run": lambda: browser.flows.run("order"),
        "flow_list": browser.flows.list,
    }

    with pytest.raises(NativeParseError, match=match):
        calls[action]()


def _assert_rate_limited(error: FlowRunError) -> None:
    assert error.status == "rate_limited"
    assert error.code == "rate_limited"
    assert error.flow == "order"
    assert error.step == 2
    assert error.http_status == 429
    assert error.retry_after == "30"
    assert error.save_error == "flow file is read-only"
    assert error.action == "flow_run"
    assert error.response["data"]["status"] == "rate_limited"
    assert "retry after 30" in str(error)


def test_stopped_flow_run_raises_flow_run_error_with_the_engine_stop_data() -> None:
    browser = Browser(
        _native_session=NativeSession(
            native=ScriptedNative({"flow_run": _RATE_LIMITED}, default={})
        )
    )

    with pytest.raises(FlowRunError) as stopped:
        browser.flows.run("order", allow_writes="all")

    _assert_rate_limited(stopped.value)
    assert isinstance(stopped.value, BrowserError)

    async def run_async() -> None:
        async_browser = AsyncBrowser(
            _native_session=AsyncNativeSession(
                native=ScriptedNative({"flow_run": _RATE_LIMITED}, default={})
            )
        )
        with pytest.raises(FlowRunError) as async_stopped:
            await async_browser.flows.run("order", allow_writes="all")
        _assert_rate_limited(async_stopped.value)
        await async_browser.close()

    asyncio.run(run_async())
    browser.close()


def test_drifted_flow_run_reports_a_status_without_an_http_response() -> None:
    reply = {
        "success": False,
        "error": "drifted: flow 'order' step 1 (http: the response lost its items list)",
        "code": "drifted",
        "data": {"status": "drifted", "flow": "order", "step": 1},
    }
    browser = Browser(_native_session=NativeSession(native=ScriptedNative({"flow_run": reply})))

    with pytest.raises(FlowRunError) as drifted:
        browser.flows.run("order")

    assert drifted.value.status == "drifted"
    assert drifted.value.step == 1
    assert drifted.value.http_status is None
    assert drifted.value.retry_after is None


@pytest.mark.parametrize(
    "reply",
    [
        {"success": False, "error": "no saved flow named 'order'"},
        {
            "success": False,
            "error": "flow 'order' failed at step 1: HTTP 500 (the flow file was not updated)",
            "code": None,
            "data": {"saveError": "permission denied"},
        },
    ],
)
def test_failed_flow_run_without_stop_data_stays_a_browser_error(reply: dict[str, Any]) -> None:
    browser = Browser(_native_session=NativeSession(native=ScriptedNative({"flow_run": reply})))

    with pytest.raises(BrowserError) as failed:
        browser.flows.run("order")

    assert type(failed.value) is BrowserError
    assert failed.value.action == "flow_run"


@pytest.mark.parametrize(
    ("stop", "match"),
    [
        ({"status": "paused", "flow": "order", "step": 1}, "field 'status' has unknown value"),
        ({"status": "blocked", "step": 1}, "flow_run stop field 'flow'"),
    ],
)
def test_flow_run_stop_data_decodes_strictly(stop: dict[str, Any], match: str) -> None:
    reply = {"success": False, "error": "stopped", "data": stop}
    browser = Browser(_native_session=NativeSession(native=ScriptedNative({"flow_run": reply})))

    with pytest.raises(NativeParseError, match=match):
        browser.flows.run("order")


def _write_confirmation_native(result: Mapping[str, Any]) -> ScriptedNative:
    """Park `flow_run` on one uncovered write, then answer `confirm` with `result`."""
    return ScriptedNative(
        {
            "flow_run": {
                "confirmation_required": True,
                "confirmation_id": "confirmation-1",
                "action": "flow_write:s2r1",
            },
            "confirm": {
                "confirmed": True,
                "action": "flow_write:s2r1",
                "result": {"id": "confirmed-result", **result},
            },
        },
        default={},
    )


def test_confirmed_flow_write_returns_the_decoded_run() -> None:
    result = {"success": True, "data": _flow_replies()["flow_run"]}
    native = _write_confirmation_native(result)
    browser = Browser(_native_session=NativeSession(native=native))

    with pytest.raises(ConfirmationRequired) as required:
        browser.flows.run("order")

    assert required.value.data["action"] == "flow_write:s2r1"
    run = cast(Any, required.value.pending).confirm()
    assert isinstance(run, FlowRun)
    assert run.steps[0].tier == "page"
    assert [_command_without_id(command) for command in native.commands] == [
        {"action": "flow_run", "name": "order"},
        {"action": "confirm", "confirmation_id": "confirmation-1"},
    ]

    async def run_async() -> None:
        async_browser = AsyncBrowser(
            _native_session=AsyncNativeSession(native=_write_confirmation_native(result))
        )
        with pytest.raises(ConfirmationRequired) as async_required:
            await async_browser.flows.run("order")
        assert await cast(Any, async_required.value.pending).confirm() == run
        await async_browser.close()

    asyncio.run(run_async())
    browser.close()


def test_confirmed_flow_write_that_the_site_stops_raises_flow_run_error() -> None:
    browser = Browser(
        _native_session=NativeSession(native=_write_confirmation_native(_RATE_LIMITED))
    )

    with pytest.raises(ConfirmationRequired) as required:
        browser.flows.run("order")
    with pytest.raises(FlowRunError) as stopped:
        cast(Any, required.value.pending).confirm()

    _assert_rate_limited(stopped.value)

    async def run_async() -> None:
        async_browser = AsyncBrowser(
            _native_session=AsyncNativeSession(native=_write_confirmation_native(_RATE_LIMITED))
        )
        with pytest.raises(ConfirmationRequired) as async_required:
            await async_browser.flows.run("order")
        with pytest.raises(FlowRunError) as async_stopped:
            await cast(Any, async_required.value.pending).confirm()
        _assert_rate_limited(async_stopped.value)
        await async_browser.close()

    asyncio.run(run_async())
    browser.close()


def test_flow_run_with_two_uncovered_writes_confirms_each_before_decoding() -> None:
    results: list[Mapping[str, Any]] = [
        {
            "success": True,
            "data": {
                "confirmation_required": True,
                "confirmation_id": "confirmation-2",
                "action": "flow_write:s3r1",
            },
        },
        _RATE_LIMITED,
    ]
    native = _write_confirmation_native({})
    native.replies["confirm"] = lambda command: {
        "confirmed": True,
        "action": "flow_write:s2r1",
        "result": {"id": command["id"], **results.pop(0)},
    }
    browser = Browser(_native_session=NativeSession(native=native))

    with pytest.raises(ConfirmationRequired) as first:
        browser.flows.run("order")
    with pytest.raises(ConfirmationRequired) as second:
        cast(Any, first.value.pending).confirm()
    assert second.value.data["action"] == "flow_write:s3r1"
    with pytest.raises(FlowRunError) as stopped:
        cast(Any, second.value.pending).confirm()

    _assert_rate_limited(stopped.value)
    browser.close()


def test_close_reports_unsaved_flow_steps() -> None:
    def close_with(data: dict[str, Any]) -> Browser:
        return Browser(
            _native_session=NativeSession(
                native=ScriptedNative({"__agent_browser_internal_shutdown": data})
            )
        )

    assert close_with({**CLOSE_DATA, "unsaved": {"steps": 3}}).close().unsaved_flow_steps == 3
    assert close_with(dict(CLOSE_DATA)).close().unsaved_flow_steps == 0
    with pytest.raises(NativeParseError, match="close unsaved field 'steps'"):
        close_with({**CLOSE_DATA, "unsaved": {"steps": "3"}}).close()

    async def run_async() -> int:
        async_browser = AsyncBrowser(
            _native_session=AsyncNativeSession(
                native=ScriptedNative(
                    {
                        **_flow_replies(),
                        "__agent_browser_internal_shutdown": {
                            **CLOSE_DATA,
                            "unsaved": {"steps": 3},
                        },
                    }
                )
            )
        )
        # The async session answers close itself until a command has reached the engine.
        await async_browser.flows.steps()
        return (await async_browser.close()).unsaved_flow_steps

    assert asyncio.run(run_async()) == 3


def test_launch_capture_option_reaches_the_launch_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sync_native = ScriptedNative(default={})
    sync_from_configuration = Browser._from_configuration

    def sync_browser(
        cls: type[Browser],
        configuration: Any,
        *,
        session: SessionOptions | None = None,
        native_session: NativeSession | None = None,
    ) -> Browser:
        del cls, native_session
        return sync_from_configuration(
            configuration, session=session, native_session=NativeSession(native=sync_native)
        )

    monkeypatch.setattr(Browser, "_from_configuration", classmethod(sync_browser))

    with Browser.launch(LaunchOptions(capture=["flow"])):
        pass
    with Browser.launch():
        pass

    launches = [command for command in sync_native.commands if command["action"] == "launch"]
    assert launches[0]["capture"] == ["flow"]
    assert "capture" not in launches[1]

    async def run_async() -> dict[str, Any]:
        async_native = ScriptedNative(default={})
        async_from_configuration = AsyncBrowser._from_configuration

        def async_browser(
            cls: type[AsyncBrowser],
            configuration: Any,
            *,
            session: SessionOptions | None = None,
            native_session: AsyncNativeSession | None = None,
        ) -> AsyncBrowser:
            del cls, native_session
            return async_from_configuration(
                configuration,
                session=session,
                native_session=AsyncNativeSession(native=async_native),
            )

        monkeypatch.setattr(AsyncBrowser, "_from_configuration", classmethod(async_browser))
        async with await AsyncBrowser.launch(LaunchOptions(capture=["flow"])):
            pass
        return async_native.commands[0]

    async_launch = asyncio.run(run_async())
    assert async_launch["action"] == "launch"
    assert async_launch["capture"] == ["flow"]
