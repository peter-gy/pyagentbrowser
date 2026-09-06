from __future__ import annotations

import argparse
from pathlib import Path

from _agent_plugin_artifact import attach_wheel


def attach_agent_plugin(wheel: Path) -> None:
    """Add the authored Agent Plugin to one wheel built by Maturin."""
    attach_wheel(wheel)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add pyagentbrowser Agent Plugin resources to built wheels."
    )
    parser.add_argument("dist", type=Path)
    args = parser.parse_args()
    wheels = sorted(args.dist.glob("pyagentbrowser-*.whl"))
    if len(wheels) != 1:
        raise SystemExit(
            f"expected one pyagentbrowser wheel in {args.dist}, "
            f"found {[wheel.name for wheel in wheels]}"
        )
    attach_agent_plugin(wheels[0])
    print(wheels[0])


if __name__ == "__main__":
    main()
