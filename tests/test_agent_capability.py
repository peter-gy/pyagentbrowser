from __future__ import annotations

import subprocess
import sys
import weakref
from collections.abc import Iterator
from gc import collect
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import agent_plugins
import pytest

import agentbrowser.agent as browser_agent
from agentbrowser import (
    AttachedTarget,
    Browser,
    BrowserError,
    CallbackHost,
    CDPTarget,
    CloseResult,
    ConfirmationRequired,
    ExecutionContext,
    ImageContent,
    ImageDelivery,
    OpenTarget,
    SessionOptions,
    TabInfo,
    bind_host,
    current_host,
    reset_host,
)
from agentbrowser.transport.sync import NativeSession
from tests.fakes import ConfirmationNative

pytestmark = pytest.mark.sdk_dx
ROOT = Path(__file__).resolve().parents[1]


class _Pending:
    def __init__(self, action: str, outcome: object, *, browser: object | None = None) -> None:
        self.action = action
        self.confirmation_id = f"confirm-{action}"
        self.details = {"action": action}
        self._outcome = outcome
        self._controller = browser
        self.denied = False

    def confirm(self) -> object:
        if isinstance(self._outcome, BaseException):
            raise self._outcome
        return self._outcome

    def deny(self) -> None:
        self.denied = True


def _required(action: str, pending: object) -> ConfirmationRequired[Any]:
    error = ConfirmationRequired(
        action,
        {"confirmation_id": f"confirm-{action}"},
        {"id": f"confirm-{action}"},
    )
    error.pending = pending
    return error


@pytest.fixture(autouse=True)
def close_agent_controllers() -> Iterator[None]:
    browser_agent.close_all()
    yield
    browser_agent.close_all()


def test_root_import_keeps_agent_capability_dependencies_lazy() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
import agentbrowser

assert agentbrowser.Ref
assert agentbrowser.Snapshot
assert agentbrowser.StaleRefError
assert "agentbrowser.agent" not in sys.modules
assert "agent_plugins" not in sys.modules
""",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_create_and_get_keep_one_controller_across_scratchpad_locals() -> None:
    first = browser_agent.create("test-persistence")
    reference = weakref.ref(first)
    del first
    collect()

    second = browser_agent.get("test-persistence")

    assert reference() is second
    assert browser_agent.close("test-persistence").closed


def test_create_rejects_duplicate_names_and_get_rejects_missing_names() -> None:
    browser_agent.create("test-options", session=SessionOptions(allowed_domains=("example.com",)))

    with pytest.raises(ValueError, match="already registered"):
        browser_agent.create("test-options")
    with pytest.raises(KeyError, match="not registered"):
        browser_agent.get("missing")
    with pytest.raises(KeyError, match="not registered"):
        browser_agent.close("missing")


def test_create_fills_session_id_for_custom_options(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[SessionOptions] = []

    class FakeBrowser:
        closed = False

        def close(self) -> CloseResult:
            self.closed = True
            return CloseResult(closed=True)

    def create_browser(*, session: SessionOptions) -> FakeBrowser:
        captured.append(session)
        return FakeBrowser()

    monkeypatch.setattr(browser_agent, "Browser", create_browser)
    browser_agent.create("first", session=SessionOptions(allowed_domains=("example.com",)))

    assert captured == [SessionOptions(session_id="first", allowed_domains=("example.com",))]


def test_open_uses_host_application_url(monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[str] = []

    class FakeBrowser:
        closed = False
        page = SimpleNamespace(open=opened.append)

        def close(self) -> CloseResult:
            self.closed = True
            return CloseResult(closed=True)

    monkeypatch.setattr(browser_agent, "Browser", lambda *, session: FakeBrowser())

    browser = browser_agent.open("application", OpenTarget("http://127.0.0.1:4312/app"))

    assert opened == ["http://127.0.0.1:4312/app"]
    assert browser_agent.get("application") is browser


def test_attach_selects_the_exact_page(monkeypatch: pytest.MonkeyPatch) -> None:
    selected: list[str] = []

    class FakeTabs:
        page = object()

        def switch(self, *, id: str) -> None:
            selected.append(id)

        def get(self, *, id: str) -> object:
            selected.append(f"get:{id}")
            return self.page

    class FakeBrowser:
        closed = False
        tabs = FakeTabs()

        def close(self) -> CloseResult:
            self.closed = True
            return CloseResult(closed=True)

    attached: list[CDPTarget] = []

    def attach(target: CDPTarget, **_kwargs: object) -> FakeBrowser:
        attached.append(target)
        return FakeBrowser()

    monkeypatch.setattr(browser_agent.Browser, "attach", attach)
    target = AttachedTarget(CDPTarget(port=9222), "0123456789ABCDEF")

    browser = browser_agent.attach("application", target)

    assert attached == [target.connection]
    assert selected == [target.target_id]
    assert browser_agent.get("application") is browser


def test_attach_confirmation_completes_launch_switch_registration_and_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = AttachedTarget(CDPTarget(port=9222), "A" * 16)
    active = TabInfo(
        id="t1",
        target_id=target.target_id,
        url="https://example.com/app",
        active=True,
    )
    selected: list[str] = []

    class FakeTabs:
        def switch(self, *, id: str) -> None:
            selected.append(id)
            raise _required("tab_switch", _Pending("tab_switch", None))

        def list(self) -> tuple[TabInfo, ...]:
            raise _required("tab_list", _Pending("tab_list", (active,)))

    class FakeBrowser:
        closed = False
        is_launched = True
        tabs = FakeTabs()
        _page_target_id: str | None = None

        def close(self) -> CloseResult:
            self.closed = True
            return CloseResult(closed=True)

    browser = FakeBrowser()

    def attach(*_args: object, **_kwargs: object) -> FakeBrowser:
        raise _required("launch", _Pending("launch", browser, browser=browser))

    monkeypatch.setattr(browser_agent.Browser, "attach", attach)

    with pytest.raises(ConfirmationRequired) as launch_required:
        browser_agent.attach("confirmed", target)
    assert browser_agent.names() == ()

    with pytest.raises(ConfirmationRequired) as switch_required:
        launch_required.value.pending.confirm()
    assert browser_agent.names() == ()

    confirmed = switch_required.value.pending.confirm()
    assert confirmed is browser
    assert selected == [target.target_id]
    assert browser._page_target_id == target.target_id
    assert browser_agent.get("confirmed") is browser

    with pytest.raises(ConfirmationRequired) as status_required:
        browser_agent.status("confirmed")
    confirmed_status = status_required.value.pending.confirm()
    assert confirmed_status.ownership == "attached"
    assert confirmed_status.target_id == target.target_id
    assert confirmed_status.url == active.url


@pytest.mark.parametrize("decision", ["deny", "failed_confirm"])
def test_attach_rejection_closes_the_pending_controller(
    monkeypatch: pytest.MonkeyPatch, decision: str
) -> None:
    native = ConfirmationNative(action="launch")
    browser = Browser(_native_session=NativeSession(native=native))
    monkeypatch.setattr(
        browser_agent.Browser,
        "_from_configuration",
        lambda *_args, **_kwargs: browser,
    )

    with pytest.raises(ConfirmationRequired) as required:
        browser_agent.attach("rejected", AttachedTarget(CDPTarget(port=9222), "A" * 16))

    if decision == "deny":
        required.value.pending.deny()
    else:
        native.confirmation_id = "expired-confirmation"
        with pytest.raises(BrowserError, match="confirmation id mismatch"):
            required.value.pending.confirm()

    assert browser.closed
    assert browser_agent.names() == ()
    assert native.commands[-1]["action"] == "__agent_browser_internal_shutdown"


def test_open_confirmation_failure_closes_and_forgets_controller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakePage:
        def __init__(self, browser: object) -> None:
            self.browser = browser

        def open(self, _url: str) -> None:
            pending = _Pending(
                "navigate",
                RuntimeError("navigation failed"),
                browser=self.browser,
            )
            raise _required("navigate", pending)

    class FakeBrowser:
        closed = False

        def __init__(self) -> None:
            self.page = FakePage(self)

        def close(self) -> CloseResult:
            self.closed = True
            return CloseResult(closed=True)

    browser = FakeBrowser()
    monkeypatch.setattr(browser_agent, "Browser", lambda *, session: browser)

    with pytest.raises(ConfirmationRequired) as required:
        browser_agent.open("failing", OpenTarget("https://example.com"))
    assert browser_agent.get("failing") is browser

    with pytest.raises(RuntimeError, match="navigation failed"):
        required.value.pending.confirm()
    assert browser.closed
    assert browser_agent.names() == ()


def test_names_and_close_all_cover_registered_controllers() -> None:
    first = browser_agent.create("inventory-b")
    second = browser_agent.create("inventory-a")

    assert browser_agent.names() == ("inventory-a", "inventory-b")

    results = browser_agent.close_all()

    assert results.keys() == {"inventory-a", "inventory-b"}
    assert all(result.closed for result in results.values())
    assert first.closed and second.closed
    assert browser_agent.names() == ()


def test_close_all_continues_after_one_controller_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controllers: dict[str, Any] = {}

    class FakeBrowser:
        closed = False

        def __init__(self, name: str) -> None:
            self.name = name

        def close(self) -> CloseResult:
            self.closed = True
            if self.name == "bad":
                raise RuntimeError("close failed")
            return CloseResult(closed=True)

    def create_browser(*, session: SessionOptions) -> FakeBrowser:
        browser = FakeBrowser(str(session.session_id))
        controllers[str(session.session_id)] = browser
        return browser

    monkeypatch.setattr(browser_agent, "Browser", create_browser)
    browser_agent.create("bad")
    browser_agent.create("good")

    with pytest.raises(browser_agent.CloseAllError) as failed:
        browser_agent.close_all()

    assert failed.value.results["good"].closed
    assert set(failed.value.errors) == {"bad"}
    assert all(browser.closed for browser in controllers.values())
    assert browser_agent.names() == ()


def test_host_contract_values_validate_model_facing_boundaries() -> None:
    content = ImageContent(b"png", "image/png", Path("capture.png"))

    assert content.source == Path("capture.png")
    assert ImageDelivery("submitted", "image-1").status == "submitted"
    context = ExecutionContext(timeout_ms=30_000, cancellation=True)
    assert context.cancellation
    with pytest.raises(ValueError, match="image MIME type"):
        ImageContent(b"png", "text/plain")
    with pytest.raises(ValueError, match="non-negative"):
        ExecutionContext(timeout_ms=-1)
    with pytest.raises(ValueError, match="accepted, queued, or submitted"):
        ImageDelivery(cast(Any, "seen"))


def test_agent_host_binding_follows_the_execution_context() -> None:
    class Host:
        image_delivery = True

        def current_target(self) -> OpenTarget:
            return OpenTarget("https://example.com")

        def emit_image(self, content: ImageContent) -> ImageDelivery:
            del content
            return ImageDelivery("submitted")

        def execution_context(self) -> ExecutionContext:
            return ExecutionContext(timeout_ms=30_000)

    token = bind_host(Host())
    try:
        assert current_host().current_target() == OpenTarget("https://example.com")
    finally:
        reset_host(token)

    with pytest.raises(RuntimeError, match="no AgentHost"):
        current_host()


def test_callback_host_delivers_exact_image_bytes() -> None:
    received: list[ImageContent] = []

    def emit(content: ImageContent) -> ImageDelivery:
        received.append(content)
        return ImageDelivery("submitted", "image-1")

    host = CallbackHost(OpenTarget("https://example.com"), emit)
    content = ImageContent(b"png", "image/png")

    delivery = host.emit_image(content)

    assert received == [content]
    assert delivery == ImageDelivery("submitted", "image-1")


def test_agent_status_exposes_process_scope_and_ownership() -> None:
    browser_agent.create("status")

    status = browser_agent.status("status")

    assert status.name == "status"
    assert status.ownership == "owned"
    assert status.session_id == "status"
    assert not status.browser_launched


def test_agent_module_directory_exposes_the_supported_surface() -> None:
    operations = {
        "create",
        "open",
        "attach",
        "get",
        "names",
        "status",
        "close",
        "close_all",
    }

    assert operations <= set(dir(browser_agent))
    assert all(callable(getattr(browser_agent, name)) for name in operations)


@pytest.mark.parametrize("name", ["", "has space", "path/name", "x" * 65])
def test_create_rejects_invalid_connection_names(name: str) -> None:
    with pytest.raises(ValueError, match="connection name"):
        browser_agent.create(name)


def test_agent_capability_loads_and_renders_help_in_a_fresh_process() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
from importlib.metadata import distribution

capabilities = [
    entry
    for entry in distribution("pyagentbrowser").entry_points
    if entry.group == "marimo.agent.capability"
]
assert [(entry.name, entry.value) for entry in capabilities] == [
    ("pyagentbrowser", "agentbrowser.agent")
]
module = capabilities[0].load()
assert 'browser = browser_agent.create("research")' in module.help()
""",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_agent_plugin_exposes_the_packaged_pyagentbrowser_skill() -> None:
    plugin = browser_agent.agent_plugin()
    skill = browser_agent.agent_skill()
    source = agent_plugins.Plugin.from_project(ROOT)

    assert plugin.manifest.name == "pyagentbrowser"
    assert plugin.skill("pyagentbrowser") == skill
    assert skill.file("SKILL.md").is_file()
    source_files = {path.relative_to(source.path): path.read_bytes() for path in source.files}
    installed_files = {path.relative_to(plugin.path): path.read_bytes() for path in plugin.files}
    assert installed_files == source_files


def test_agent_module_help_points_to_sdk_and_installed_resources() -> None:
    rendered = browser_agent.help()

    assert str(browser_agent.agent_skill().file("SKILL.md")) in rendered
    assert "https://peter-gy.github.io/pyagentbrowser/llms.txt" in rendered
    assert "resize viewport" in rendered
    assert len(rendered) < 6000
