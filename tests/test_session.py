from __future__ import annotations

import asyncio
import gc
import json
import weakref
from pathlib import Path
from typing import Any, cast

import pytest
from fakes import (
    BlockingNative,
    ConfirmationNative,
    EchoNative,
    ErrorNative,
    RawResponseNative,
    WarningNative,
)

import agentbrowser.session as session_module
from agentbrowser import BrowserError, ConfirmationRequired, RestoreOptions
from agentbrowser.models import OMIT, DashboardOptions
from agentbrowser.session import NativeSession
from agentbrowser.session_async import AsyncNativeSession

pytestmark = pytest.mark.sdk_dx


def test_command_builder_owns_ids_paths_nulls_and_omission(tmp_path: Path) -> None:
    native = EchoNative()
    session = NativeSession(native=native)

    first = session.command(
        "probe",
        path=tmp_path / "value.json",
        explicit=None,
        omitted=OMIT,
        nested={"keep": 1, "drop": OMIT},
    )
    second = session.command("probe")

    command = cast(dict[str, Any], first)["echo"]
    first_id = command["id"]
    second_id = cast(dict[str, Any], second)["echo"]["id"]
    assert isinstance(first_id, str) and first_id
    assert isinstance(second_id, str) and second_id
    assert second_id != first_id
    assert command["path"] == str(tmp_path / "value.json")
    assert command["explicit"] is None
    assert "omitted" not in command
    assert command["nested"] == {"keep": 1}


def test_native_constructor_receives_session_options_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict[str, Any]] = []

    class NativeConstructor:
        def __init__(self, options_json: str) -> None:
            captured.append(json.loads(options_json))

        def execute_json(self, command_json: str) -> str:
            command = json.loads(command_json)
            return json.dumps({"id": command["id"], "success": True, "data": {}})

    monkeypatch.setattr(session_module, "NativeBrowser", NativeConstructor)
    session = NativeSession(
        session="research",
        namespace="worker-a",
        restore=RestoreOptions(
            "research",
            save="always",
            autosave_interval_ms=250,
        ),
        default_timeout_ms=2500,
        dashboard=DashboardOptions(port=0, cli_version="0.31.1"),
    )

    session.command("probe")
    session.command("probe")

    assert captured == [
        {
            "session": "research",
            "restore_key": "research",
            "restore_save": "always",
            "autosave_interval_ms": 250,
            "namespace": "worker-a",
            "default_timeout_ms": 2500,
            "no_auto_dialog": False,
            "dashboard": {
                "enabled": True,
                "port": 0,
                "cli_version": "0.31.1",
            },
        }
    ]


@pytest.mark.parametrize(
    "factory,match",
    [
        (lambda: RestoreOptions("state", autosave_interval_ms=-1), "non-negative"),
        (lambda: DashboardOptions(port=65536), "between"),
        (lambda: DashboardOptions(cli_version=" "), "empty"),
    ],
)
def test_option_models_reject_invalid_values(factory: Any, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        factory()


def test_execute_preserves_failed_and_warning_envelopes() -> None:
    failed = NativeSession(native=ErrorNative()).execute("probe")
    warning = NativeSession(native=WarningNative()).execute("probe")

    assert failed.success is False
    assert failed.raw["error"] == "native rejected this command"
    assert warning.warning == "dialog is blocking the page"
    assert warning.data == {"ok": True}


def test_command_turns_failed_envelopes_into_browser_errors() -> None:
    with pytest.raises(BrowserError, match="native rejected") as failed:
        NativeSession(native=ErrorNative()).command("probe")

    assert failed.value.action == "probe"


@pytest.mark.parametrize(
    "response,match",
    [
        ("not json", "valid JSON"),
        ("[]", "not an object"),
        (json.dumps({"data": {}}), "success.*boolean"),
    ],
)
def test_native_envelope_validation_is_strict(response: str, match: str) -> None:
    with pytest.raises(BrowserError, match=match):
        NativeSession(native=RawResponseNative(response)).execute("probe")


def test_array_data_remains_available_at_the_raw_boundary() -> None:
    response = json.dumps({"id": "native", "success": True, "data": [1, 2]})
    assert NativeSession(native=RawResponseNative(response)).command("probe") == [1, 2]


def test_confirmation_uses_native_tokens_and_forwards_them() -> None:
    native = ConfirmationNative(action="probe", result={"ok": True})
    session = NativeSession(native=native)

    with pytest.raises(ConfirmationRequired) as required:
        session.command("probe")

    token = required.value.confirmation_id
    assert token == "confirmation-1"
    confirmed = session.execute("confirm", confirmation_id=token)
    assert confirmed.success is True
    assert native.commands[-1]["confirmation_id"] == token


def test_async_session_skips_cancelled_queued_work() -> None:
    async def run() -> None:
        native = BlockingNative()
        session = AsyncNativeSession(native=native)

        active = asyncio.create_task(session.command("block"))
        assert await asyncio.to_thread(native.started.wait, 1.0)
        queued = asyncio.create_task(session.command("queued"))
        await asyncio.sleep(0)
        queued.cancel()
        with pytest.raises(asyncio.CancelledError):
            await queued

        native.release.set()
        assert await active == {"ok": True}
        await session.aclose(timeout=1.0)
        assert not any(command["action"] == "queued" for command in native.commands)

    asyncio.run(run())


def test_async_session_close_dispatches_shutdown_and_rejects_reuse() -> None:
    async def run() -> None:
        native = EchoNative()
        session = AsyncNativeSession(native=native)
        await session.command("probe")
        await session.aclose(timeout=1.0)

        assert any(
            command["action"] == "__agent_browser_internal_shutdown" for command in native.commands
        )
        with pytest.raises(RuntimeError, match="closed"):
            await session.command("probe")

    asyncio.run(run())


def test_async_session_finalizer_dispatches_shutdown() -> None:
    async def run() -> None:
        native = EchoNative()
        session = AsyncNativeSession(native=native)
        await session.command("probe")
        session_ref = weakref.ref(session)
        del session

        for _ in range(20):
            gc.collect()
            if any(
                command["action"] == "__agent_browser_internal_shutdown"
                for command in native.commands
            ):
                break
            await asyncio.sleep(0.05)

        assert session_ref() is None
        assert any(
            command["action"] == "__agent_browser_internal_shutdown" for command in native.commands
        )

    asyncio.run(run())
