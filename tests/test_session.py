from __future__ import annotations

import asyncio
import gc
import json
import weakref
from pathlib import Path
from typing import cast

import pytest
from fakes import (
    BlockingNative,
    ConfirmationNative,
    EchoNative,
    ErrorNative,
    FailingConfirmationNative,
    RawResponseNative,
    WarningNative,
)

import pyagentbrowser.session as session_module
from pyagentbrowser import BrowserError, DashboardOptions
from pyagentbrowser._browser_common import INTERNAL_SHUTDOWN_ACTION
from pyagentbrowser.models import OMIT, ActionConfirmationRequired
from pyagentbrowser.session import NativeSession
from pyagentbrowser.session_async import AsyncNativeSession

pytestmark = pytest.mark.sdk_dx


class DistinctConfirmationNative:
    def __init__(self) -> None:
        self.commands: list[dict[str, object]] = []

    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        self.commands.append(command)
        if command["action"] == "click":
            return json.dumps(
                {
                    "id": command["id"],
                    "success": True,
                    "data": {
                        "confirmation_required": True,
                        "confirmation_id": "confirmation-token",
                        "action": "click",
                    },
                }
            )
        if command["action"] == "confirm":
            if command.get("confirmation_id") != "confirmation-token":
                return json.dumps(
                    {
                        "id": command["id"],
                        "success": False,
                        "error": "confirmation-token was not forwarded",
                    }
                )
            return json.dumps(
                {
                    "id": command["id"],
                    "success": True,
                    "data": {
                        "confirmed": True,
                        "action": "click",
                        "result": {
                            "id": "confirmed-native",
                            "success": True,
                            "data": {"clicked": "#danger"},
                        },
                    },
                }
            )
        raise AssertionError(f"unexpected action: {command['action']}")


class NestedConfirmationNative:
    def execute_json(self, command_json: str) -> str:
        command = json.loads(command_json)
        if command["action"] == "click":
            return json.dumps(
                {
                    "id": command["id"],
                    "success": True,
                    "data": {
                        "confirmation_required": True,
                        "confirmation_id": "confirmation-token",
                        "action": "click",
                    },
                }
            )
        if command["action"] == "confirm":
            return json.dumps(
                {
                    "id": command["id"],
                    "success": True,
                    "data": {
                        "confirmed": True,
                        "action": "click",
                        "result": {
                            "id": "confirmed-native",
                            "success": True,
                            "data": {"clicked": "#danger"},
                        },
                    },
                }
            )
        raise AssertionError(f"unexpected action: {command['action']}")


def _echoed_command(result: object) -> dict[str, object]:
    result_data = cast(dict[str, object], result)
    raw_command = result_data["echo"]
    assert isinstance(raw_command, dict)
    return cast(dict[str, object], raw_command)


def test_native_session_uses_unique_opaque_command_ids() -> None:
    native = EchoNative()
    session = NativeSession(native=native)

    first = _echoed_command(session.command("route"))
    second = _echoed_command(session.command("status"))

    assert isinstance(first["id"], str)
    assert isinstance(second["id"], str)
    assert first["id"]
    assert second["id"]
    assert second["id"] != first["id"]


def test_native_session_serializes_path_parameters(tmp_path: Path) -> None:
    session = NativeSession(native=EchoNative())

    result = session.command(
        "route",
        path=tmp_path / "out.har",
        nested={"keep": tmp_path / "file.txt"},
    )

    command = _echoed_command(result)
    assert command["action"] == "route"
    assert command["path"] == str(tmp_path / "out.har")
    assert command["nested"] == {"keep": str(tmp_path / "file.txt")}


def test_native_session_preserves_null_parameters() -> None:
    session = NativeSession(native=EchoNative())

    result = session.command(
        "route",
        raw_null=None,
        nested={"drop": None},
    )

    command = _echoed_command(result)
    assert command["raw_null"] is None
    assert command["nested"] == {"drop": None}


def test_native_session_omits_explicit_omit_parameters() -> None:
    session = NativeSession(native=EchoNative())

    result = session.command(
        "route",
        omitted=OMIT,
        nested_omitted={"drop": OMIT, "keep": None},
    )

    command = _echoed_command(result)
    assert command["nested_omitted"] == {"keep": None}
    assert "omitted" not in command


def _capture_native_options(monkeypatch: pytest.MonkeyPatch) -> list[str | None]:
    captured: list[str | None] = []

    class CaptureNative:
        def __init__(self, options_json: str | None = None) -> None:
            captured.append(options_json)

        def execute_json(self, command_json: str) -> str:
            command = json.loads(command_json)
            return json.dumps({"id": command["id"], "success": True, "data": {}})

    monkeypatch.setattr(session_module, "NativeBrowser", CaptureNative)
    return captured


def test_native_session_serializes_dashboard_options(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _capture_native_options(monkeypatch)
    NativeSession(
        session="dash",
        dashboard=DashboardOptions(port=0, cli_version="1.2.3"),
    ).command("device_list")

    options = json.loads(str(captured[0]))
    assert options["session"] == "dash"
    assert options["dashboard"] == {"enabled": True, "port": 0, "cli_version": "1.2.3"}


def test_native_session_omits_dashboard_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _capture_native_options(monkeypatch)

    NativeSession(dashboard=False).command("device_list")

    assert "dashboard" not in json.loads(str(captured[0]))


def _captured_native_options(monkeypatch: pytest.MonkeyPatch) -> list[str | None]:
    captured: list[str | None] = []

    class CaptureNative:
        def __init__(self, options_json: str | None = None) -> None:
            captured.append(options_json)

        def execute_json(self, command_json: str) -> str:
            command = json.loads(command_json)
            return json.dumps({"id": command["id"], "success": True, "data": {}})

    monkeypatch.setattr(session_module, "NativeBrowser", CaptureNative)
    return captured


def test_native_session_defaults_to_15_second_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _captured_native_options(monkeypatch)
    NativeSession().command("device_list")

    default_options = json.loads(str(captured[0]))
    assert default_options["default_timeout_ms"] == 15_000


def test_native_session_serializes_explicit_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _captured_native_options(monkeypatch)
    NativeSession(default_timeout_ms=5_000).command("device_list")

    explicit_options = json.loads(str(captured[0]))
    assert explicit_options["default_timeout_ms"] == 5_000


def test_native_session_omits_timeout_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _captured_native_options(monkeypatch)
    NativeSession(default_timeout_ms=None).command("device_list")

    disabled_options = json.loads(str(captured[0]))
    assert "default_timeout_ms" not in disabled_options


def test_dashboard_options_validate_port() -> None:
    with pytest.raises(ValueError, match="dashboard port"):
        DashboardOptions(port=70000)


def test_dashboard_options_validate_cli_version() -> None:
    with pytest.raises(ValueError, match="dashboard cli_version"):
        DashboardOptions(cli_version=" ")


def test_native_session_execute_returns_failed_response() -> None:
    failure = NativeSession(native=ErrorNative()).execute("explode")

    assert failure.success is False
    assert failure.action == "explode"
    assert failure.raw["error"] == "native rejected this command"


def test_native_session_command_raises_browser_error() -> None:
    with pytest.raises(BrowserError) as exc_info:
        NativeSession(native=ErrorNative()).command("explode")

    assert exc_info.value.action == "explode"


def test_native_session_execute_preserves_warning_data() -> None:
    warning = NativeSession(native=WarningNative()).execute("status")

    assert warning.warning == "dialog is blocking the page"
    assert warning.data == {"ok": True}


def test_native_session_rejects_invalid_json_envelope() -> None:
    with pytest.raises(BrowserError, match="not valid JSON"):
        NativeSession(native=RawResponseNative("{not-json")).execute("status")


def test_native_session_rejects_non_object_envelope() -> None:
    with pytest.raises(BrowserError, match="not an object"):
        NativeSession(native=RawResponseNative("[]")).execute("status")


def test_native_session_rejects_envelope_without_success_boolean() -> None:
    with pytest.raises(BrowserError, match="success was not a boolean"):
        NativeSession(native=RawResponseNative('{"id": "py1", "data": {}}')).execute("status")


def test_native_session_accepts_array_response_data() -> None:
    array_response = NativeSession(
        native=RawResponseNative('{"id": "py1", "success": true, "data": []}')
    ).execute("status")

    assert array_response.data == []


def test_native_session_command_raises_confirmation_with_native_token() -> None:
    native = DistinctConfirmationNative()
    session = NativeSession(native=native)

    with pytest.raises(ActionConfirmationRequired) as exc_info:
        session.command("click")

    assert exc_info.value.action == "click"
    assert exc_info.value.confirmation_id == "confirmation-token"


def test_native_session_confirm_forwards_token() -> None:
    native = DistinctConfirmationNative()
    session = NativeSession(native=native)
    with pytest.raises(ActionConfirmationRequired) as exc_info:
        session.command("click")

    session.command("confirm", confirmation_id=exc_info.value.confirmation_id)

    assert native.commands[-1]["confirmation_id"] == "confirmation-token"


def test_native_session_confirm_returns_nested_result_data() -> None:
    session = NativeSession(native=NestedConfirmationNative())
    with pytest.raises(ActionConfirmationRequired) as exc_info:
        session.command("click")

    assert session.command("confirm", confirmation_id=exc_info.value.confirmation_id) == {
        "clicked": "#danger"
    }


def test_native_session_confirm_without_pending_token_uses_native_confirmation() -> None:
    assert NativeSession(native=ConfirmationNative()).command("confirm") == {"clicked": "#danger"}


def test_native_session_confirm_unwraps_nested_failure_as_command_error() -> None:
    with pytest.raises(BrowserError) as failed:
        NativeSession(native=FailingConfirmationNative()).command("confirm")

    assert failed.value.action == "click"
    assert "confirmed click failed" in str(failed.value)


def test_session_async_skips_cancelled_commands_before_native_dispatch() -> None:
    async def run() -> None:
        native = BlockingNative()
        session = AsyncNativeSession(native=native)

        first = asyncio.create_task(session.command("block"))
        assert await asyncio.to_thread(native.started.wait, 1.0)

        second = asyncio.create_task(session.command("cancelled"))
        await asyncio.sleep(0)
        second.cancel()
        with pytest.raises(asyncio.CancelledError):
            await second

        native.release.set()
        assert await first == {"ok": True}
        await session.aclose(timeout=1.0)

        assert not any(command["action"] == "cancelled" for command in native.commands)

    asyncio.run(run())


def test_session_async_close_dispatches_internal_shutdown() -> None:
    async def run() -> None:
        explicit_native = EchoNative()
        explicit = AsyncNativeSession(native=explicit_native)
        await explicit.command("status")
        await explicit.aclose(timeout=1.0)
        assert any(
            command["action"] == INTERNAL_SHUTDOWN_ACTION for command in explicit_native.commands
        )

    asyncio.run(run())


def test_session_async_rejects_reuse_after_close() -> None:
    async def run() -> None:
        explicit = AsyncNativeSession(native=EchoNative())
        await explicit.command("status")
        await explicit.aclose(timeout=1.0)
        with pytest.raises(RuntimeError, match="closed"):
            await explicit.command("status")

    asyncio.run(run())


def test_session_async_finalizer_dispatches_internal_shutdown() -> None:
    async def run() -> None:
        dropped_native = EchoNative()
        dropped = AsyncNativeSession(native=dropped_native)
        await dropped.command("status")
        session_ref = weakref.ref(dropped)
        del dropped
        for _ in range(20):
            gc.collect()
            if any(
                command["action"] == INTERNAL_SHUTDOWN_ACTION for command in dropped_native.commands
            ):
                break
            await asyncio.sleep(0.05)
        assert session_ref() is None
        assert any(
            command["action"] == INTERNAL_SHUTDOWN_ACTION for command in dropped_native.commands
        )

    asyncio.run(run())
