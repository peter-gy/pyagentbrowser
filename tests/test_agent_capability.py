from __future__ import annotations

import pydoc
import subprocess
import sys
import weakref
from collections.abc import Iterator
from gc import collect
from pathlib import Path
from types import SimpleNamespace

import agent_plugins
import pytest

import agentbrowser.agent as browser_agent
from agentbrowser import (
    AttachedTarget,
    CDPTarget,
    CloseResult,
    ExecutionContext,
    ImageContent,
    ImageDelivery,
    OpenTarget,
    Ref,
    SessionOptions,
    Snapshot,
    StaleRefError,
)

pytestmark = pytest.mark.sdk_dx
ROOT = Path(__file__).resolve().parents[1]


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
assert "agentbrowser.agent" not in sys.modules
assert "agent_plugins" not in sys.modules
""",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_agent_module_preserves_direct_evidence_imports() -> None:
    assert browser_agent.Ref is Ref
    assert browser_agent.Snapshot is Snapshot
    assert browser_agent.StaleRefError is StaleRefError


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

        def open(self, url: str) -> None:
            opened.append(url)

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
        page = SimpleNamespace(find=object(), capture=object())

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
    assert selected == [target.page_id, f"get:{target.page_id}"]
    assert browser_agent.get("application") is browser


def test_names_and_close_all_cover_registered_controllers() -> None:
    first = browser_agent.create("inventory-b")
    second = browser_agent.create("inventory-a")

    assert browser_agent.names() == ("inventory-a", "inventory-b")

    results = browser_agent.close_all()

    assert results.keys() == {"inventory-a", "inventory-b"}
    assert all(result.closed for result in results.values())
    assert first.closed and second.closed
    assert browser_agent.names() == ()


def test_host_contract_values_validate_model_facing_boundaries() -> None:
    content = ImageContent(b"png", "image/png", Path("capture.png"))

    assert content.source == Path("capture.png")
    assert ImageDelivery("submitted", "image-1").status == "submitted"
    context = ExecutionContext(timeout_ms=30_000, cancellation=True)
    assert context.cancellation
    assert context.limit(60_000) == 29_000
    with pytest.raises(ValueError, match="image MIME type"):
        ImageContent(b"png", "text/plain")
    with pytest.raises(ValueError, match="non-negative"):
        ExecutionContext(timeout_ms=-1)


def test_agent_module_directory_exposes_the_supported_surface() -> None:
    operations = {"create", "open", "attach", "get", "names", "close", "close_all"}

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
import pydoc
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
assert 'browser = browser_agent.create("research")' in pydoc.render_doc(module)
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
    rendered = pydoc.render_doc(browser_agent)

    assert str(browser_agent.agent_skill().file("SKILL.md")) in rendered
    assert "https://peter-gy.github.io/pyagentbrowser/llms.txt" in rendered
    assert "resize viewport" in rendered
    assert len(rendered) < 6000
