from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest
from fakes import ScriptedNative

from agentbrowser import (
    AsyncBrowser,
    Browser,
    NativeParseError,
    WebMCPInvocation,
    WebMCPTool,
)
from agentbrowser.session import NativeSession
from agentbrowser.session_async import AsyncNativeSession

pytestmark = pytest.mark.sdk_dx


def _command_without_id(command: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in command.items() if key != "id"}


def _webmcp_replies() -> dict[str, dict[str, Any]]:
    return {
        "webmcp_list": {
            "experimental": True,
            "tools": [
                {
                    "name": "search",
                    "description": "Search the current catalog",
                    "inputSchema": {"type": "object"},
                    "annotations": {"readOnlyHint": True},
                    "origin": "https://example.com",
                    "frameId": "frame-1",
                    "backendNodeId": 42,
                }
            ],
        },
        "webmcp_invoke": {
            "invocationId": "invocation-1",
            "toolName": "search",
            "frameId": "frame-1",
            "origin": "https://example.com",
            "status": "pending",
            "durationMs": 3,
        },
        "webmcp_result": {
            "invocationId": "invocation-1",
            "toolName": "search",
            "frameId": "frame-1",
            "origin": "https://example.com",
            "status": "completed",
            "rawStatus": "Completed",
            "durationMs": 9,
            "output": {"matches": 2},
        },
        "webmcp_cancel": {
            "invocationId": "invocation-2",
            "toolName": "wait",
            "frameId": "frame-1",
            "origin": "https://example.com",
            "status": "canceled",
            "rawStatus": "Canceled",
            "durationMs": 4,
        },
    }


def test_webmcp_typed_namespace_preserves_sync_async_command_parity() -> None:
    sync_native = ScriptedNative(_webmcp_replies(), default={})
    browser = Browser(_native_session=NativeSession(native=sync_native))

    assert browser.webmcp.list() == (
        WebMCPTool(
            name="search",
            description="Search the current catalog",
            input_schema={"type": "object"},
            annotations={"readOnlyHint": True},
            origin="https://example.com",
            frame_id="frame-1",
            backend_node_id=42,
        ),
    )
    pending = browser.webmcp.invoke(
        "search",
        {"query": "agents"},
        frame_id="frame-1",
        detach=True,
        timeout_ms=5000,
    )
    completed = browser.webmcp.result("invocation-1", timeout_ms=250)
    canceled = browser.webmcp.cancel("invocation-2")

    assert pending == WebMCPInvocation(
        invocation_id="invocation-1",
        tool_name="search",
        frame_id="frame-1",
        origin="https://example.com",
        status="pending",
        duration_ms=3,
    )
    assert completed.output == {"matches": 2}
    assert completed.raw_status == "Completed"
    assert canceled.status == "canceled"
    sync_commands = [_command_without_id(command) for command in sync_native.commands]
    assert sync_commands == [
        {"action": "webmcp_list"},
        {
            "action": "webmcp_invoke",
            "tool": "search",
            "params": {"query": "agents"},
            "frameId": "frame-1",
            "detach": True,
            "timeout": 5000,
        },
        {
            "action": "webmcp_result",
            "invocationId": "invocation-1",
            "timeout": 250,
        },
        {"action": "webmcp_cancel", "invocationId": "invocation-2"},
    ]

    async def run() -> list[dict[str, Any]]:
        async_native = ScriptedNative(_webmcp_replies(), default={})
        async_browser = AsyncBrowser(_native_session=AsyncNativeSession(native=async_native))
        assert await async_browser.webmcp.list() == browser.webmcp.list()
        assert (
            await async_browser.webmcp.invoke(
                "search",
                {"query": "agents"},
                frame_id="frame-1",
                detach=True,
                timeout_ms=5000,
            )
            == pending
        )
        assert await async_browser.webmcp.result("invocation-1", timeout_ms=250) == completed
        assert await async_browser.webmcp.cancel("invocation-2") == canceled
        await async_browser.close()
        return [
            _command_without_id(command)
            for command in async_native.commands
            if command["action"] != "__agent_browser_internal_shutdown"
        ]

    assert asyncio.run(run()) == sync_commands
    browser.close()


def test_webmcp_validates_inputs_and_native_result_shapes() -> None:
    browser = Browser(
        _native_session=NativeSession(
            native=ScriptedNative(
                {
                    "webmcp_list": {"experimental": True, "tools": "invalid"},
                }
            )
        )
    )

    with pytest.raises(TypeError, match="params must be a mapping"):
        browser.webmcp.invoke("search", cast(Any, ["invalid"]))
    with pytest.raises(ValueError, match="tool must not be empty"):
        browser.webmcp.invoke(" ")
    with pytest.raises(ValueError, match="timeout_ms must be non-negative"):
        browser.webmcp.invoke("search", timeout_ms=-1)
    with pytest.raises(NativeParseError, match="webmcp_list field 'tools'"):
        browser.webmcp.list()
