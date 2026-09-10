from __future__ import annotations

import inspect
from typing import Any

import pytest
from fakes import ScriptedNative
from support.sdk import _browser

import agentbrowser
from agentbrowser import (
    AsyncBrowser,
    AsyncFrame,
    AsyncPage,
    AsyncQuery,
    AsyncRef,
    AsyncSnapshot,
    Browser,
    Frame,
    Page,
    Query,
    Ref,
    Snapshot,
)
from agentbrowser.transport.async_ import AsyncNativeSession

pytestmark = pytest.mark.sdk_dx


def _public_methods(target: type[Any]) -> set[str]:
    methods: set[str] = set()
    for name in dir(target):
        if name.startswith("_"):
            continue
        value = inspect.getattr_static(target, name)
        if callable(value) or isinstance(value, classmethod | staticmethod):
            methods.add(name)
    return methods


@pytest.mark.parametrize(
    "name",
    [
        "AccessibilityAudit",
        "AccessibilityCounts",
        "AccessibilityIssue",
        "AccessibilityNode",
        "ConsoleMessage",
        "Cookie",
        "CloseResult",
        "HarContentMode",
        "NetworkRequest",
        "ProxyConfig",
        "RequestDetail",
        "RestoreSaveError",
        "RouteResponse",
        "SessionId",
        "SessionStatus",
        "TabCloseResult",
        "TabInfo",
        "TabSwitchResult",
    ],
)
def test_public_contract_types_are_package_exports(name: str) -> None:
    assert name in agentbrowser.__all__
    assert getattr(agentbrowser, name) is not None


def test_sync_and_async_public_surfaces_keep_method_and_signature_parity() -> None:
    type_pairs = (
        (Browser, AsyncBrowser),
        (Page, AsyncPage),
        (Frame, AsyncFrame),
        (Query, AsyncQuery),
        (Ref, AsyncRef),
        (Snapshot, AsyncSnapshot),
    )
    for sync_type, async_type in type_pairs:
        sync_methods = _public_methods(sync_type)
        async_methods = _public_methods(async_type)
        assert async_methods == sync_methods, sync_type.__name__
        for name in sync_methods:
            sync_parameters = inspect.signature(getattr(sync_type, name)).parameters
            async_parameters = inspect.signature(getattr(async_type, name)).parameters
            if sync_type is Browser and name == "close":
                assert tuple(sync_parameters) == ("self",)
                assert tuple(async_parameters) == ("self", "timeout")
                continue
            normalized_async = {
                key: parameter.replace(
                    annotation=(
                        parameter.annotation.replace("AsyncExecutor", "Executor")
                        if isinstance(parameter.annotation, str)
                        else parameter.annotation
                    )
                )
                for key, parameter in async_parameters.items()
            }
            assert normalized_async == sync_parameters, f"{sync_type.__name__}.{name}"

    sync_browser = _browser(ScriptedNative(default={}))
    async_browser = AsyncBrowser(
        _native_session=AsyncNativeSession(native=ScriptedNative(default={})),
    )
    sync_namespaces = {
        name: getattr(sync_browser, name)
        for name, value in vars(Browser).items()
        if not name.startswith("_")
        and isinstance(value, property)
        and name not in {"closed", "is_launched"}
    }
    async_namespaces = {
        name: getattr(async_browser, name)
        for name, value in vars(AsyncBrowser).items()
        if not name.startswith("_")
        and isinstance(value, property)
        and name not in {"closed", "is_launched"}
    }
    assert async_namespaces.keys() == sync_namespaces.keys()
    for name, sync_namespace in sync_namespaces.items():
        async_namespace = async_namespaces[name]
        sync_methods = _public_methods(type(sync_namespace))
        async_methods = _public_methods(type(async_namespace))
        assert async_methods == sync_methods, name
        for method in sync_methods:
            sync_parameters = inspect.signature(getattr(sync_namespace, method)).parameters
            async_parameters = inspect.signature(getattr(async_namespace, method)).parameters
            async_parameters = {
                key: parameter.replace(
                    annotation=(
                        parameter.annotation.replace("AsyncExecutor", "Executor")
                        if isinstance(parameter.annotation, str)
                        else parameter.annotation
                    )
                )
                for key, parameter in async_parameters.items()
            }
            assert async_parameters == sync_parameters, f"{name}.{method}"

    sync_frame_capture = Frame(
        sync_browser.extension(lambda executor: executor), frame_id="frame"
    ).capture
    async_frame_capture = AsyncFrame(
        async_browser.extension(lambda executor: executor), frame_id="frame"
    ).capture
    assert _public_methods(type(sync_frame_capture)) == {"screenshot"}
    assert _public_methods(type(async_frame_capture)) == {"screenshot"}
    assert (
        inspect.signature(sync_frame_capture.screenshot).parameters
        == inspect.signature(async_frame_capture.screenshot).parameters
    )
