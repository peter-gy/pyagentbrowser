from __future__ import annotations

import pydoc
import subprocess
import sys
import weakref
from gc import collect
from pathlib import Path

import agent_plugins
import pytest

import agentbrowser.agent as browser_agent
from agentbrowser import CloseResult, Ref, SessionOptions, Snapshot, StaleRefError

pytestmark = pytest.mark.sdk_dx
ROOT = Path(__file__).resolve().parents[1]


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


def test_connect_keeps_one_browser_alive_across_scratchpad_locals() -> None:
    first = browser_agent.connect("test-persistence")
    reference = weakref.ref(first)
    del first
    collect()

    second = browser_agent.connect("test-persistence")

    assert reference() is second
    assert browser_agent.disconnect("test-persistence").closed
    assert browser_agent.disconnect("test-persistence").closed


def test_connect_rejects_changed_options_for_a_live_connection() -> None:
    first_options = SessionOptions(allowed_domains=("example.com",))
    other_options = SessionOptions(allowed_domains=("example.org",))
    first = browser_agent.connect("test-options", session=first_options)
    try:
        assert browser_agent.connect("test-options") is first
        with pytest.raises(
            ValueError,
            match=r"Call disconnect\('test-options'\).*new options",
        ):
            browser_agent.connect("test-options", session=other_options)
    finally:
        browser_agent.disconnect("test-options")


def test_connect_fills_session_ids_for_custom_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    browser_agent.connect(
        "first",
        session=SessionOptions(allowed_domains=("example.com",)),
    )
    browser_agent.connect(
        "second",
        session=SessionOptions(allowed_domains=("example.org",)),
    )
    try:
        assert [options.session_id for options in captured] == ["first", "second"]
    finally:
        browser_agent.disconnect("first")
        browser_agent.disconnect("second")


def test_connect_preserves_session_options_after_direct_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[SessionOptions] = []

    class FakeBrowser:
        closed = False
        is_launched = False

        def close(self) -> CloseResult:
            self.closed = True
            return CloseResult(closed=True)

    def create_browser(*, session: SessionOptions) -> FakeBrowser:
        captured.append(session)
        return FakeBrowser()

    monkeypatch.setattr(browser_agent, "Browser", create_browser)
    options = SessionOptions(
        allowed_domains=("example.com",),
        confirm_actions=("click",),
    )
    first = browser_agent.connect("preserved-policy", session=options)
    first.close()
    second = browser_agent.connect("preserved-policy")
    try:
        assert second is not first
        assert captured == [
            SessionOptions(
                session_id="preserved-policy",
                allowed_domains=("example.com",),
                confirm_actions=("click",),
            ),
            SessionOptions(
                session_id="preserved-policy",
                allowed_domains=("example.com",),
                confirm_actions=("click",),
            ),
        ]
    finally:
        browser_agent.disconnect("preserved-policy")


def test_connections_and_disconnect_all_cover_named_controllers() -> None:
    first = browser_agent.connect("inventory-b")
    second = browser_agent.connect("inventory-a")

    assert browser_agent.connections() == {
        "inventory-a": second,
        "inventory-b": first,
    }

    results = browser_agent.disconnect_all()

    assert results.keys() == {"inventory-a", "inventory-b"}
    assert all(result.closed for result in results.values())
    assert first.closed and second.closed
    assert browser_agent.connections() == {}


def test_agent_module_directory_exposes_the_supported_surface() -> None:
    operations = {"connect", "connections", "disconnect", "disconnect_all"}

    assert operations <= set(dir(browser_agent))
    assert all(callable(getattr(browser_agent, name)) for name in operations)


@pytest.mark.parametrize("name", ["", "has space", "path/name", "x" * 65])
def test_connect_rejects_invalid_connection_names(name: str) -> None:
    with pytest.raises(ValueError, match="connection name"):
        browser_agent.connect(name)


def test_agent_capability_loads_and_renders_help_in_a_fresh_process() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import pydoc
import sys
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
import agentbrowser.agent

assert module is agentbrowser.agent
assert 'browser = browser_agent.connect("research")' in pydoc.render_doc(module)
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
    assert skill.file("references/api-map.md").is_file()
    assert skill.file("references/lifecycle-and-safety.md").is_file()
    assert source.skill("pyagentbrowser").source == skill.source
    source_files = {path.relative_to(source.path): path.read_bytes() for path in source.files}
    installed_files = {path.relative_to(plugin.path): path.read_bytes() for path in plugin.files}
    assert installed_files == source_files


def test_agent_module_help_points_to_sdk_and_installed_resources() -> None:
    plugin = browser_agent.agent_plugin()
    skill = browser_agent.agent_skill()
    rendered = pydoc.render_doc(browser_agent)

    assert str(plugin.path) in rendered
    assert str(skill.file("SKILL.md")) in rendered
    assert "https://peter-gy.github.io/pyagentbrowser/llms.txt" in rendered
    assert len(rendered) < 6000


def test_agent_module_help_preserves_sdk_guidance_when_plugin_lookup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail() -> agent_plugins.Plugin:
        raise agent_plugins.AgentPluginError("marker unavailable")

    monkeypatch.setattr(browser_agent, "agent_plugin", fail)
    rendered = pydoc.render_doc(browser_agent)

    assert 'browser = browser_agent.connect("research")' in rendered
    assert "marker unavailable" in rendered
    assert "Reinstall pyagentbrowser" in rendered
