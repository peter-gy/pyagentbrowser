from __future__ import annotations

import subprocess
import sys
import weakref
from collections.abc import Iterator
from gc import collect
from pathlib import Path
from typing import Any

import agent_plugins
import pytest

import agentbrowser.agent as browser_agent
from agentbrowser import (
    CloseResult,
    SessionOptions,
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


def test_agent_module_directory_exposes_the_supported_surface() -> None:
    operations = {
        "create",
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
