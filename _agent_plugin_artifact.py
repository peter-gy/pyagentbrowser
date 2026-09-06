"""Agent Plugin attachment for wheels built outside PEP 517."""

from pathlib import Path

from agent_plugins import build_plan
from agent_plugins._build.wheel import write_wheel_plugin

_PROJECT_ROOT = Path(__file__).resolve().parent


def attach_wheel(wheel: Path) -> None:
    """Attach this project's Agent Plugin to one direct Maturin wheel."""
    # maturin-action invokes the executable outside PEP 517. Keep its wheel on
    # the same pinned agent-plugins writer used by BuildBackend.
    write_wheel_plugin(wheel, build_plan(_PROJECT_ROOT))
